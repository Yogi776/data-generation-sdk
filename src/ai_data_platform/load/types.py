"""Load layer types and transport protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from ai_data_platform.load.config_models import IncrementalStrategy


class TableLoadSpec(BaseModel):
    table: str
    source_uri: str
    source_table: str
    dest_uri: str
    dest_table: str
    incremental_strategy: IncrementalStrategy = "replace"
    primary_key: str | None = None
    incremental_key: str | None = None
    ingestr_options: dict[str, Any] = Field(default_factory=dict)
    stream: bool = False
    flush_interval: str | None = None
    flush_records: int | None = None
    metrics_addr: str | None = None
    interval_start: str | None = None
    interval_end: str | None = None
    # When a live source is configured, these override the local parquet source.
    is_live_source: bool = False
    source_sql: str | None = None


class LoadPlan(BaseModel):
    destination_name: str
    staging_format: str
    data_dir: str
    waves: list[list[TableLoadSpec]]


@dataclass(frozen=True)
class TableLoadResult:
    table: str
    dest_table: str
    status: Literal["ok", "failed", "dry_run"]
    elapsed_ms: float
    rows_estimate: int | None = None
    error: str | None = None


@dataclass
class LoadReport:
    destination: str
    staging_format: str
    quality_score: float | None
    tables: list[TableLoadResult] = field(default_factory=list)
    elapsed_ms: float = 0.0

    @property
    def ok(self) -> bool:
        return all(t.status in ("ok", "dry_run") for t in self.tables)


class LoadTransport(Protocol):
    def load_table(self, spec: TableLoadSpec, *, dry_run: bool) -> TableLoadResult: ...
