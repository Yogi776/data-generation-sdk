"""Load destination configuration models (adp.yaml destinations + load blocks)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_data_platform.core.env import SECRET_SHAPED as _SECRET_SHAPED
from ai_data_platform.core.env import interpolate_env

IncrementalStrategy = Literal["replace", "append", "merge", "delete+insert"]
StagingFormat = Literal["parquet", "csv", "duckdb"]


class StreamConfig(BaseModel):
    """CDC / streaming options — passed as explicit ingestr flags (not ingestr_options)."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    flush_interval: str | None = None  # e.g. "30s", "1m"
    flush_records: int | None = None  # e.g. 50000
    metrics_addr: str | None = None  # e.g. "127.0.0.1:6060"
    interval_start: str | None = None  # ISO datetime or date string
    interval_end: str | None = None  # ISO datetime or date string


class SourceConfig(BaseModel):
    """Live database source for CDC-style ingestion.

    When a source is configured on a destination, ADP uses the live DB as the
    ingestr source instead of local parquet files. This enables:
      - Initial load from an existing production DB into Snowflake
      - Incremental CDC by combining source.incremental_key with
        destination.incremental_strategy (merge / append / delete+insert)

    The source URI follows the same scheme rules as destinations.
    """

    model_config = ConfigDict(extra="forbid")

    uri: str
    table: str | None = None
    sql: str | None = None
    incremental_key: str | None = None
    ingestr_options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("uri")
    @classmethod
    def _uri_has_scheme(cls, v: str) -> str:
        if "${" in v:
            return v
        if "://" not in v:
            raise ValueError("source uri must contain a scheme (e.g. postgresql://, mysql://)")
        if _SECRET_SHAPED.search(v):
            raise ValueError(
                "source uri appears to contain a plaintext secret; "
                "use ${ENV_VAR} interpolation instead"
            )
        return v

    def resolved_uri(self) -> str:
        resolved = interpolate_env(self.uri)
        if "://" not in resolved:
            raise ValueError(f"resolved source uri missing scheme: {resolved!r}")
        return resolved


class DestinationConfig(BaseModel):
    """One configured load destination (ingestr dest-uri)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    uri: str
    table_prefix: str = "main"
    tables: dict[str, str] = Field(default_factory=dict)
    incremental_strategy: IncrementalStrategy = "replace"
    primary_key: str | None = None
    incremental_key: str | None = None
    ingestr_options: dict[str, Any] = Field(default_factory=dict)
    table_ingestr_options: dict[str, dict[str, Any]] = Field(default_factory=dict)
    auto_extract_partition: bool = False
    stream: StreamConfig | None = None
    source: SourceConfig | None = None

    @field_validator("uri")
    @classmethod
    def _uri_has_scheme(cls, v: str) -> str:
        if "${" in v:
            return v
        if "://" not in v:
            raise ValueError("uri must contain a scheme (e.g. snowflake://, duckdb:///)")
        if _SECRET_SHAPED.search(v):
            raise ValueError(
                "uri appears to contain a plaintext secret; use ${ENV_VAR} interpolation instead"
            )
        return v

    def resolved_uri(self) -> str:
        resolved = interpolate_env(self.uri)
        if "://" not in resolved:
            raise ValueError(f"resolved uri missing scheme: {resolved!r}")
        return resolved

    def dest_table(self, spec_table: str) -> str:
        return self.tables.get(spec_table, f"{self.table_prefix}.{spec_table}")


class LoadConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_destination: str | None = None
    require_quality_pass: bool = True
    min_quality_score: float = Field(default=95.0, ge=0, le=100)
    staging_format: StagingFormat | None = None
    parallel_tables: int = Field(default=2, ge=1, le=8)
