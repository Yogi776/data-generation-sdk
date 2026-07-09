"""Catalog service: the single gateway to metadata storage.

All modules read/write metadata through this class — swapping SQLite for the
platform's PostgreSQL is an adapter change, not a caller change.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, joinedload, sessionmaker

from ai_data_platform.connectors.base import TableSchema
from ai_data_platform.core.exceptions import CatalogError, TableNotFoundError
from ai_data_platform.core.paths import catalog_path
from ai_data_platform.metadata.models import (
    CATALOG_SCHEMA_VERSION,
    Base,
    ColumnRecord,
    MetaKV,
    ProfileRecord,
    QualityRuleRecord,
    RelationshipRecord,
    SemanticModelRecord,
    SourceRecord,
    TableRecord,
)


class Catalog:
    """Local metadata catalog backed by SQLite."""

    def __init__(self, root: str | Path = ".", db_path: str | Path | None = None) -> None:
        self.root = Path(root).expanduser().resolve()
        if db_path:
            path = Path(db_path)
        elif os.environ.get("ADP_CATALOG_DIR"):
            # Escape hatch for filesystems where SQLite locking fails
            # (network mounts, some containers): relocate the catalog.
            base = Path(os.environ["ADP_CATALOG_DIR"]).expanduser()
            digest = hashlib.sha256(str(self.root).encode()).hexdigest()[:12]
            path = base / f"{self.root.name}-{digest}" / "catalog.db"
        else:
            path = catalog_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{path}")
        try:
            Base.metadata.create_all(self.engine)
            self._session_factory = sessionmaker(self.engine, expire_on_commit=False)
            self._ensure_schema_version()
        except OperationalError as e:
            raise CatalogError(
                f"Cannot open the metadata catalog at {path} ({e.orig}).",
                hint="SQLite often fails on network-mounted filesystems. Set "
                "ADP_CATALOG_DIR to a local directory, e.g. "
                "`export ADP_CATALOG_DIR=~/.adp-catalogs`, and retry.",
            ) from e

    def _ensure_schema_version(self) -> None:
        with self.session() as s:
            row = s.get(MetaKV, "schema_version")
            if row is None:
                s.add(MetaKV(key="schema_version", value=str(CATALOG_SCHEMA_VERSION)))
                s.commit()

    def session(self) -> Session:
        return self._session_factory()

    # -- sources -------------------------------------------------------------
    def upsert_source(self, name: str, type_: str) -> int:
        with self.session() as s:
            src = s.scalar(select(SourceRecord).where(SourceRecord.name == name))
            if src is None:
                src = SourceRecord(name=name, type=type_)
                s.add(src)
            else:
                src.type = type_
            s.commit()
            return src.id

    def list_sources(self) -> list[dict[str, Any]]:
        with self.session() as s:
            rows = s.scalars(select(SourceRecord).order_by(SourceRecord.name)).all()
            return [
                {
                    "name": r.name,
                    "type": r.type,
                    "tables": len(r.tables),
                    "last_scanned_at": r.last_scanned_at.isoformat() if r.last_scanned_at else None,
                }
                for r in rows
            ]

    def mark_scanned(self, source_name: str, fingerprint: str) -> None:
        with self.session() as s:
            src = s.scalar(select(SourceRecord).where(SourceRecord.name == source_name))
            if src:
                src.last_scanned_at = datetime.now(UTC)
                src.schema_fingerprint = fingerprint
                s.commit()

    # -- tables & columns ------------------------------------------------------
    def upsert_table(self, source_name: str, schema: TableSchema) -> int:
        with self.session() as s:
            src = s.scalar(select(SourceRecord).where(SourceRecord.name == source_name))
            if src is None:
                raise TableNotFoundError(source_name)
            tbl = s.scalar(
                select(TableRecord).where(
                    TableRecord.source_id == src.id, TableRecord.name == schema.name
                )
            )
            if tbl is None:
                tbl = TableRecord(source_id=src.id, name=schema.name)
                s.add(tbl)
                s.flush()
            tbl.schema_name = schema.schema_name
            tbl.row_count = schema.row_count
            existing = {c.name: c for c in tbl.columns}
            seen = set()
            for col in schema.columns:
                seen.add(col.name)
                rec = existing.get(col.name)
                if rec is None:
                    s.add(
                        ColumnRecord(
                            table_id=tbl.id,
                            name=col.name,
                            data_type=col.data_type,
                            nullable=col.nullable,
                            ordinal=col.ordinal,
                        )
                    )
                else:
                    rec.data_type = col.data_type
                    rec.nullable = col.nullable
                    rec.ordinal = col.ordinal
            for name, rec in existing.items():
                if name not in seen:
                    s.delete(rec)
            s.commit()
            return tbl.id

    def list_tables(self, source: str | None = None) -> list[dict[str, Any]]:
        with self.session() as s:
            q = select(TableRecord).options(joinedload(TableRecord.source))
            if source:
                q = q.join(SourceRecord).where(SourceRecord.name == source)
            rows = s.scalars(q.order_by(TableRecord.name)).unique().all()
            return [
                {
                    "table": r.name,
                    "source": r.source.name,
                    "columns": len(r.columns),
                    "row_count": r.row_count,
                    "kind": r.table_kind or "unknown",
                    "description": r.description,
                }
                for r in rows
            ]

    def get_table(self, table: str, source: str | None = None) -> dict[str, Any]:
        with self.session() as s:
            q = (
                select(TableRecord)
                .options(joinedload(TableRecord.columns), joinedload(TableRecord.source))
                .where(TableRecord.name == table)
            )
            if source:
                q = q.join(SourceRecord).where(SourceRecord.name == source)
            rec = s.scalars(q).unique().first()
            if rec is None:
                raise TableNotFoundError(table)
            return self._table_dict(rec)

    def primary_keys_for_tables(self, tables: list[str]) -> dict[str, str]:
        """Return primary-key column name per table (single query)."""
        if not tables:
            return {}
        with self.session() as s:
            rows = s.scalars(
                select(TableRecord)
                .options(joinedload(TableRecord.columns))
                .where(TableRecord.name.in_(tables))
            ).unique().all()
            out: dict[str, str] = {}
            for rec in rows:
                for col in rec.columns:
                    if col.is_primary_key:
                        out[rec.name] = col.name
                        break
            return out

    @staticmethod
    def _table_dict(rec: TableRecord) -> dict[str, Any]:
        return {
            "id": rec.id,
            "table": rec.name,
            "source": rec.source.name,
            "schema": rec.schema_name,
            "row_count": rec.row_count,
            "kind": rec.table_kind or "unknown",
            "description": rec.description,
            "columns": [
                {
                    "name": c.name,
                    "type": c.data_type,
                    "nullable": c.nullable,
                    "primary_key": c.is_primary_key,
                    "pii": c.pii_level,
                    "description": c.description,
                }
                for c in rec.columns
            ],
        }

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Substring search over table/column names and descriptions."""
        pattern = f"%{query.lower()}%"
        with self.session() as s:
            tables = (
                s.scalars(
                    select(TableRecord)
                    .options(joinedload(TableRecord.source))
                    .where(
                        or_(
                            func.lower(TableRecord.name).like(pattern),
                            func.lower(func.coalesce(TableRecord.description, "")).like(pattern),
                        )
                    )
                    .limit(limit)
                )
                .unique()
                .all()
            )
            cols = (
                s.scalars(
                    select(ColumnRecord)
                    .options(joinedload(ColumnRecord.table).joinedload(TableRecord.source))
                    .where(
                        or_(
                            func.lower(ColumnRecord.name).like(pattern),
                            func.lower(func.coalesce(ColumnRecord.description, "")).like(pattern),
                        )
                    )
                    .limit(limit)
                )
                .unique()
                .all()
            )
        results: list[dict[str, Any]] = [
            {
                "match": "table",
                "table": t.name,
                "source": t.source.name,
                "description": t.description,
            }
            for t in tables
        ]
        results += [
            {
                "match": "column",
                "table": c.table.name,
                "column": c.name,
                "source": c.table.source.name,
                "type": c.data_type,
            }
            for c in cols
        ]
        return results[:limit]

    # -- column annotations ---------------------------------------------------
    def set_primary_key(self, table_id: int, column_names: list[str]) -> None:
        with self.session() as s:
            cols = s.scalars(select(ColumnRecord).where(ColumnRecord.table_id == table_id)).all()
            for c in cols:
                c.is_primary_key = c.name in column_names
            s.commit()

    def set_pii(self, table_id: int, column: str, level: str, category: str | None) -> None:
        with self.session() as s:
            c = s.scalar(
                select(ColumnRecord).where(
                    ColumnRecord.table_id == table_id, ColumnRecord.name == column
                )
            )
            if c:
                c.pii_level = level
                c.pii_category = category
                s.commit()

    def set_table_kind(self, table_id: int, kind: str) -> None:
        with self.session() as s:
            t = s.get(TableRecord, table_id)
            if t:
                t.table_kind = kind
                s.commit()

    # -- relationships ---------------------------------------------------------
    def add_relationship(
        self,
        child_table: str,
        child_column: str,
        parent_table: str,
        parent_column: str,
        *,
        kind: str = "many_to_one",
        confidence: float = 1.0,
        provenance: str = "inferred",
        evidence: str | None = None,
    ) -> None:
        with self.session() as s:
            child = s.scalar(select(TableRecord).where(TableRecord.name == child_table))
            parent = s.scalar(select(TableRecord).where(TableRecord.name == parent_table))
            if child is None or parent is None:
                raise TableNotFoundError(child_table if child is None else parent_table)
            existing = s.scalar(
                select(RelationshipRecord).where(
                    RelationshipRecord.child_table_id == child.id,
                    RelationshipRecord.child_column == child_column,
                    RelationshipRecord.parent_table_id == parent.id,
                    RelationshipRecord.parent_column == parent_column,
                )
            )
            if existing:
                if provenance == "user_stated" or confidence > existing.confidence:
                    existing.confidence = confidence
                    existing.provenance = provenance
                    existing.evidence = evidence
                    existing.kind = kind
            else:
                s.add(
                    RelationshipRecord(
                        kind=kind,
                        child_table_id=child.id,
                        child_column=child_column,
                        parent_table_id=parent.id,
                        parent_column=parent_column,
                        confidence=confidence,
                        provenance=provenance,
                        evidence=evidence,
                    )
                )
            s.commit()

    def get_relationships(self) -> list[dict[str, Any]]:
        with self.session() as s:
            rows = s.scalars(select(RelationshipRecord)).all()
            table_names = {t.id: t.name for t in s.scalars(select(TableRecord)).all()}
            return [
                {
                    "child_table": table_names.get(r.child_table_id, "?"),
                    "child_column": r.child_column,
                    "parent_table": table_names.get(r.parent_table_id, "?"),
                    "parent_column": r.parent_column,
                    "kind": r.kind,
                    "confidence": r.confidence,
                    "provenance": r.provenance,
                }
                for r in rows
            ]

    # -- profiles ---------------------------------------------------------------
    def save_profile(self, table: str, payload: dict[str, Any]) -> None:
        with self.session() as s:
            rec = s.scalar(select(TableRecord).where(TableRecord.name == table))
            if rec is None:
                raise TableNotFoundError(table)
            s.add(ProfileRecord(table_id=rec.id, payload=payload))
            s.commit()

    def get_latest_profile(self, table: str) -> dict[str, Any] | None:
        with self.session() as s:
            rec = s.scalar(select(TableRecord).where(TableRecord.name == table))
            if rec is None:
                raise TableNotFoundError(table)
            prof = s.scalars(
                select(ProfileRecord)
                .where(ProfileRecord.table_id == rec.id)
                .order_by(ProfileRecord.created_at.desc(), ProfileRecord.id.desc())
            ).first()
            return prof.payload if prof else None

    # -- quality rules ------------------------------------------------------------
    def replace_quality_rules(self, table: str, rules: list[dict[str, Any]]) -> None:
        with self.session() as s:
            rec = s.scalar(select(TableRecord).where(TableRecord.name == table))
            if rec is None:
                raise TableNotFoundError(table)
            for old in s.scalars(
                select(QualityRuleRecord).where(QualityRuleRecord.table_id == rec.id)
            ):
                s.delete(old)
            for r in rules:
                s.add(
                    QualityRuleRecord(
                        table_id=rec.id,
                        rule_type=r["rule_type"],
                        params=r.get("params", {}),
                        provenance=r.get("provenance", "inferred"),
                    )
                )
            s.commit()

    def get_quality_rules(self, table: str) -> list[dict[str, Any]]:
        with self.session() as s:
            rec = s.scalar(select(TableRecord).where(TableRecord.name == table))
            if rec is None:
                raise TableNotFoundError(table)
            rows = s.scalars(
                select(QualityRuleRecord).where(
                    QualityRuleRecord.table_id == rec.id, QualityRuleRecord.enabled
                )
            ).all()
            return [
                {"rule_type": r.rule_type, "params": r.params, "provenance": r.provenance}
                for r in rows
            ]

    # -- semantic models -------------------------------------------------------------
    def save_semantic_model(self, name: str, payload: dict[str, Any]) -> None:
        with self.session() as s:
            rec = s.scalar(select(SemanticModelRecord).where(SemanticModelRecord.name == name))
            if rec is None:
                s.add(SemanticModelRecord(name=name, payload=payload))
            else:
                rec.payload = payload
            s.commit()

    def get_semantic_model(self, name: str) -> dict[str, Any] | None:
        with self.session() as s:
            rec = s.scalar(select(SemanticModelRecord).where(SemanticModelRecord.name == name))
            return rec.payload if rec else None


def schema_fingerprint(schemas: list[TableSchema]) -> str:
    """Deterministic fingerprint over table/column/type lists (incremental sync)."""
    h = hashlib.sha256()
    for t in sorted(schemas, key=lambda x: x.name):
        h.update(t.name.encode())
        for c in t.columns:
            h.update(f"{c.name}:{c.data_type}:{c.nullable}".encode())
    return h.hexdigest()
