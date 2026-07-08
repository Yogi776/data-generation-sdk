"""Pydantic IO contracts for the MCP Data Explorer tools.

These models are the single source of truth for every explorer tool's request
and response shape. They are consumed by the SDK, the REST API (FastAPI request
bodies), and are mirrored in the MCP tool docstrings. Keeping them here means
the JSON Schema for each tool can be produced with ``Model.model_json_schema()``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Shared / catalog                                                            #
# --------------------------------------------------------------------------- #


class ColumnInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False
    pii: str | None = None


class RegisteredTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table: str
    format: Literal["parquet", "csv", "json"]
    path: str
    row_count: int | None = None
    column_count: int = 0
    partitioned: bool = False
    partition_keys: list[str] = Field(default_factory=list)


class DatasetInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str
    created_at: str
    table_count: int
    total_rows: int | None = None
    db_path: str
    tables: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Registration                                                                #
# --------------------------------------------------------------------------- #


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str = Field(default="default", description="Logical dataset name.")
    data_dir: str | None = Field(
        default=None,
        description="Directory of generated files. Defaults to the project output_dir.",
    )
    replace: bool = Field(
        default=True, description="Replace existing views for tables of the same name."
    )


class RegisterResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str
    db_path: str
    registered: list[RegisteredTable]
    skipped: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Metadata exploration                                                        #
# --------------------------------------------------------------------------- #


class TableRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table: str
    dataset: str = "default"


class DescribeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table: str
    dataset: str
    format: str
    path: str
    row_count: int | None
    columns: list[ColumnInfo]
    partition_keys: list[str] = Field(default_factory=list)


class SchemaResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table: str
    ddl: str
    columns: list[ColumnInfo]


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table: str
    dataset: str = "default"
    limit: int = Field(default=20, ge=1, le=200)


class PreviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table: str
    columns: list[str]
    rows: list[dict[str, Any]]
    showing: int


class RowCountResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table: str
    row_count: int


class ColumnProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str
    type: str
    null_count: int
    null_fraction: float
    distinct: int | None = None
    min: Any | None = None
    max: Any | None = None
    mean: float | None = None
    stddev: float | None = None
    top_values: list[dict[str, Any]] = Field(default_factory=list)


class ProfileResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table: str
    row_count: int
    sampled: bool
    columns: list[ColumnProfile]


# --------------------------------------------------------------------------- #
# SQL                                                                         #
# --------------------------------------------------------------------------- #


class SqlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sql: str = Field(description="A single read-only SELECT/WITH statement (DuckDB dialect).")
    dataset: str = "default"
    max_rows: int | None = Field(
        default=None, description="Override the configured row cap (still bounded by config)."
    )


class SqlResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    sampled: bool
    elapsed_ms: float


class ExplainResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: str
    estimated_rows: int | None = None


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sql: str
    dataset: str = "default"
    format: Literal["csv", "parquet", "json"] = "csv"
    filename: str = Field(description="Output file name (written inside the project export dir).")


class ExportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    format: str
    row_count: int


# --------------------------------------------------------------------------- #
# Insights                                                                    #
# --------------------------------------------------------------------------- #


class SuggestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str = "default"
    table: str | None = None
    limit: int = Field(default=8, ge=1, le=25)


class SuggestedQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    sql: str
    rationale: str
    category: str


class SuggestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str
    suggestions: list[SuggestedQuery]
    source: Literal["deterministic", "llm", "hybrid"]


class InsightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sql: str
    dataset: str = "default"


class Insight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["finding", "anomaly", "trend", "data_quality"]
    message: str


class InsightResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    insights: list[Insight]
    dashboard_metrics: list[dict[str, Any]] = Field(default_factory=list)
    recommended_queries: list[SuggestedQuery] = Field(default_factory=list)
    result_preview: SqlResult | None = None
    source: Literal["deterministic", "llm", "hybrid"]


class ValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[str]
    dataset: str = "default"


class QuestionVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    answerable: bool
    reason: str
    suggested_sql: str | None = None
    tables_needed: list[str] = Field(default_factory=list)


class ValidateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str
    verdicts: list[QuestionVerdict]
