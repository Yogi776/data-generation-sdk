"""Connector SDK: the contract every source connector implements.

Rules (see design docs):
- No full-data reads: `sample_data` is budgeted, `profile_table` works on samples.
- Capabilities declaration lets engines adapt per feature, never per connector name.
- All I/O errors surface as typed ConnectorError with remediation hints.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    import polars as pl

    from ai_data_platform.config import SourceConfig


@dataclass(frozen=True)
class ColumnSchema:
    name: str
    data_type: str  # normalized: int, float, string, bool, date, datetime, other
    nullable: bool = True
    ordinal: int = 0


@dataclass(frozen=True)
class TableSchema:
    name: str
    columns: tuple[ColumnSchema, ...]
    schema_name: str | None = None
    row_count: int | None = None  # estimate if cheap, else None


@dataclass(frozen=True)
class ConnectionResult:
    ok: bool
    message: str
    server_version: str | None = None


@dataclass(frozen=True)
class Capabilities:
    supports_incremental: bool = False
    supports_pushdown_profiling: bool = False
    supports_lineage: bool = False
    max_sample_rows: int = 100_000
    dialect: str = "ansi"


@dataclass
class SampleBudget:
    rows: int = 10_000
    method: str = "head"  # head | random


NORMALIZED_TYPES = {"int", "float", "string", "bool", "date", "datetime", "other"}


def normalize_dtype(raw: str) -> str:
    """Map a source/polars dtype string to the normalized type vocabulary."""
    r = raw.lower()
    if any(t in r for t in ("int", "serial", "bigserial")):
        return "int"
    if any(t in r for t in ("float", "double", "real", "numeric", "decimal")):
        return "float"
    if any(t in r for t in ("bool",)):
        return "bool"
    if "datetime" in r or "timestamp" in r:
        return "datetime"
    if r == "date" or r.startswith("date("):
        return "date"
    if any(
        t in r for t in ("char", "text", "string", "str", "utf8", "uuid", "enum", "categorical")
    ):
        return "string"
    return "other"


class Connector(ABC):
    """Abstract source connector."""

    type_name: str = "abstract"
    capabilities: Capabilities = Capabilities()

    def __init__(self, source: SourceConfig) -> None:
        self.source = source

    # -- contract -----------------------------------------------------------
    @abstractmethod
    def test_connection(self) -> ConnectionResult: ...

    @abstractmethod
    def list_schemas(self) -> list[str]: ...

    @abstractmethod
    def list_tables(self, schema: str | None = None) -> list[str]: ...

    @abstractmethod
    def get_table_schema(self, table: str) -> TableSchema: ...

    @abstractmethod
    def sample_data(self, table: str, budget: SampleBudget | None = None) -> pl.DataFrame: ...

    # -- shared default -----------------------------------------------------
    def profile_table(self, table: str, budget: SampleBudget | None = None) -> dict[str, Any]:
        """Default profiling: sample + in-memory profile. Pushdown-capable
        connectors may override to compute aggregates source-side."""
        from ai_data_platform.profiler.profiler import profile_dataframe

        df = self.sample_data(table, budget)
        schema = self.get_table_schema(table)
        return profile_dataframe(df, table_name=table, declared_schema=schema)


@dataclass
class ConnectorInfo:
    """Registry entry."""

    type_name: str
    module: str
    class_name: str
    extra: str | None = None  # pip extra needed, if any
    placeholder: bool = False
    notes: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
