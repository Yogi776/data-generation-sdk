"""Metadata catalog ORM (SQLite locally; schema doubles as KnowledgeModel-lite v0).

Logical schema mirrors the platform catalog (ADR-0006 compatibility baseline):
sources, tables, columns, relationships, profiles, quality_rules, semantic_models.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

CATALOG_SCHEMA_VERSION = 1


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class SourceRecord(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    schema_fingerprint: Mapped[str | None] = mapped_column(String(64))

    tables: Mapped[list[TableRecord]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class TableRecord(Base):
    __tablename__ = "tables"
    __table_args__ = (UniqueConstraint("source_id", "name", name="uq_table_source_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    schema_name: Mapped[str | None] = mapped_column(String(255))
    row_count: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    table_kind: Mapped[str | None] = mapped_column(String(20))  # fact | dimension | unknown
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    source: Mapped[SourceRecord] = relationship(back_populates="tables")
    columns: Mapped[list[ColumnRecord]] = relationship(
        back_populates="table", cascade="all, delete-orphan", order_by="ColumnRecord.ordinal"
    )


class ColumnRecord(Base):
    __tablename__ = "columns"
    __table_args__ = (UniqueConstraint("table_id", "name", name="uq_column_table_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("tables.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    data_type: Mapped[str] = mapped_column(String(50))
    nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(Text)
    is_primary_key: Mapped[bool] = mapped_column(Boolean, default=False)
    pii_level: Mapped[str] = mapped_column(String(20), default="none")  # none|possible|likely
    pii_category: Mapped[str | None] = mapped_column(String(30))

    table: Mapped[TableRecord] = relationship(back_populates="columns")


class RelationshipRecord(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint(
            "child_table_id",
            "child_column",
            "parent_table_id",
            "parent_column",
            name="uq_relationship",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    child_table_id: Mapped[int] = mapped_column(ForeignKey("tables.id"), index=True)
    child_column: Mapped[str] = mapped_column(String(255))
    parent_table_id: Mapped[int] = mapped_column(ForeignKey("tables.id"), index=True)
    parent_column: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(20), default="many_to_one")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    provenance: Mapped[str] = mapped_column(String(20), default="inferred")
    evidence: Mapped[str | None] = mapped_column(Text)


class ProfileRecord(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("tables.id"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QualityRuleRecord(Base):
    __tablename__ = "quality_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("tables.id"), index=True)
    rule_type: Mapped[str] = mapped_column(String(50))
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    provenance: Mapped[str] = mapped_column(String(20), default="inferred")


class SemanticModelRecord(Base):
    __tablename__ = "semantic_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MetaKV(Base):
    """Catalog-level metadata (schema_version, etc.)."""

    __tablename__ = "meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))
