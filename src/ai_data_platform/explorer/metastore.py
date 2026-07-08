"""Explorer metadata catalog.

Tracks registered datasets, their tables/columns (with source file + format),
and an append-only query log. Defaults to a project-local SQLite database
(``.adp/explorer_catalog.db``); set ``explorer.metadata_dsn`` in adp.yaml to use
an external Postgres store instead (the ORM is dialect-agnostic).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
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
    create_engine,
    delete,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from ai_data_platform.core.exceptions import (
    DatasetNotFoundError,
    ExplorerTableNotFoundError,
)
from ai_data_platform.core.paths import adp_dir

EXPLORER_SCHEMA_VERSION = 1


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class DatasetRecord(Base):
    __tablename__ = "explorer_datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    db_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    tables: Mapped[list[RegTableRecord]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class RegTableRecord(Base):
    __tablename__ = "explorer_tables"
    __table_args__ = (UniqueConstraint("dataset_id", "name", name="uq_explorer_table"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("explorer_datasets.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    file_format: Mapped[str] = mapped_column(String(20))
    path: Mapped[str] = mapped_column(Text)
    row_count: Mapped[int | None] = mapped_column(Integer)
    partitioned: Mapped[bool] = mapped_column(Boolean, default=False)
    partition_keys: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    dataset: Mapped[DatasetRecord] = relationship(back_populates="tables")
    columns: Mapped[list[RegColumnRecord]] = relationship(
        back_populates="table",
        cascade="all, delete-orphan",
        order_by="RegColumnRecord.ordinal",
    )


class RegColumnRecord(Base):
    __tablename__ = "explorer_columns"
    __table_args__ = (UniqueConstraint("table_id", "name", name="uq_explorer_column"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("explorer_tables.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    data_type: Mapped[str] = mapped_column(String(50))
    nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)

    table: Mapped[RegTableRecord] = relationship(back_populates="columns")


class QueryLogRecord(Base):
    __tablename__ = "explorer_query_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset: Mapped[str | None] = mapped_column(String(255))
    sql: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))  # ok | error | rejected | timeout
    row_count: Mapped[int | None] = mapped_column(Integer)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    elapsed_ms: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ExplorerMetastore:
    """Gateway to explorer metadata; SQLite locally, Postgres via metadata_dsn."""

    def __init__(self, root: str | Path = ".", *, metadata_dsn: str | None = None) -> None:
        self.root = Path(root).expanduser().resolve()
        if metadata_dsn:
            url = metadata_dsn
        else:
            path = adp_dir(self.root) / "explorer_catalog.db"
            url = f"sqlite:///{path}"
        self.engine = create_engine(url)
        Base.metadata.create_all(self.engine)
        self._sf = sessionmaker(self.engine, expire_on_commit=False)

    def session(self) -> Session:
        return self._sf()

    # -- writes --------------------------------------------------------------
    def upsert_dataset(self, name: str, db_path: str) -> int:
        with self.session() as s:
            rec = s.scalar(select(DatasetRecord).where(DatasetRecord.name == name))
            if rec is None:
                rec = DatasetRecord(name=name, db_path=db_path)
                s.add(rec)
            else:
                rec.db_path = db_path
                rec.updated_at = _utcnow()
            s.commit()
            return rec.id

    def upsert_table(
        self,
        dataset: str,
        *,
        name: str,
        file_format: str,
        path: str,
        row_count: int | None,
        partitioned: bool,
        partition_keys: list[str],
        columns: list[dict[str, Any]],
    ) -> None:
        with self.session() as s:
            ds = s.scalar(select(DatasetRecord).where(DatasetRecord.name == dataset))
            if ds is None:
                ds = DatasetRecord(name=dataset, db_path="")
                s.add(ds)
                s.flush()
            existing = s.scalar(
                select(RegTableRecord).where(
                    RegTableRecord.dataset_id == ds.id, RegTableRecord.name == name
                )
            )
            if existing is not None:
                s.execute(delete(RegColumnRecord).where(RegColumnRecord.table_id == existing.id))
                tbl = existing
                tbl.file_format = file_format
                tbl.path = path
                tbl.row_count = row_count
                tbl.partitioned = partitioned
                tbl.partition_keys = partition_keys
                tbl.updated_at = _utcnow()
            else:
                tbl = RegTableRecord(
                    dataset_id=ds.id,
                    name=name,
                    file_format=file_format,
                    path=path,
                    row_count=row_count,
                    partitioned=partitioned,
                    partition_keys=partition_keys,
                )
                s.add(tbl)
                s.flush()
            for i, c in enumerate(columns):
                s.add(
                    RegColumnRecord(
                        table_id=tbl.id,
                        name=c["name"],
                        data_type=c["type"],
                        nullable=bool(c.get("nullable", True)),
                        ordinal=i,
                    )
                )
            s.commit()

    def log_query(
        self,
        *,
        dataset: str | None,
        sql: str,
        status: str,
        row_count: int | None = None,
        truncated: bool = False,
        elapsed_ms: float | None = None,
        error: str | None = None,
    ) -> None:
        with self.session() as s:
            s.add(
                QueryLogRecord(
                    dataset=dataset,
                    sql=sql[:4000],
                    status=status,
                    row_count=row_count,
                    truncated=truncated,
                    elapsed_ms=elapsed_ms,
                    error=(error or "")[:2000] or None,
                )
            )
            s.commit()

    # -- reads ---------------------------------------------------------------
    def list_datasets(self) -> list[dict[str, Any]]:
        with self.session() as s:
            out = []
            for ds in s.scalars(select(DatasetRecord).order_by(DatasetRecord.name)):
                rows = [t.row_count for t in ds.tables if t.row_count is not None]
                out.append(
                    {
                        "dataset": ds.name,
                        "created_at": ds.created_at.isoformat(),
                        "table_count": len(ds.tables),
                        "total_rows": sum(rows) if rows else None,
                        "db_path": ds.db_path,
                        "tables": sorted(t.name for t in ds.tables),
                    }
                )
            return out

    def get_dataset(self, dataset: str) -> dict[str, Any]:
        with self.session() as s:
            ds = s.scalar(select(DatasetRecord).where(DatasetRecord.name == dataset))
            if ds is None:
                raise DatasetNotFoundError(dataset, self._dataset_names(s))
            return {"dataset": ds.name, "db_path": ds.db_path}

    def list_tables(self, dataset: str) -> list[dict[str, Any]]:
        with self.session() as s:
            ds = s.scalar(select(DatasetRecord).where(DatasetRecord.name == dataset))
            if ds is None:
                raise DatasetNotFoundError(dataset, self._dataset_names(s))
            return [self._table_dict(t) for t in sorted(ds.tables, key=lambda x: x.name)]

    def get_table(self, dataset: str, table: str) -> dict[str, Any]:
        with self.session() as s:
            ds = s.scalar(select(DatasetRecord).where(DatasetRecord.name == dataset))
            if ds is None:
                raise DatasetNotFoundError(dataset, self._dataset_names(s))
            rec = s.scalar(
                select(RegTableRecord).where(
                    RegTableRecord.dataset_id == ds.id, RegTableRecord.name == table
                )
            )
            if rec is None:
                raise ExplorerTableNotFoundError(table, [t.name for t in ds.tables])
            d = self._table_dict(rec)
            d["columns"] = [
                {
                    "name": c.name,
                    "type": c.data_type,
                    "nullable": c.nullable,
                    "primary_key": False,
                    "pii": None,
                }
                for c in rec.columns
            ]
            return d

    def db_path_for(self, dataset: str) -> str:
        return self.get_dataset(dataset)["db_path"]

    @staticmethod
    def _table_dict(t: RegTableRecord) -> dict[str, Any]:
        return {
            "table": t.name,
            "format": t.file_format,
            "path": t.path,
            "row_count": t.row_count,
            "column_count": len(t.columns),
            "partitioned": t.partitioned,
            "partition_keys": list(t.partition_keys or []),
        }

    @staticmethod
    def _dataset_names(s: Session) -> list[str]:
        return [r for r in s.scalars(select(DatasetRecord.name))]
