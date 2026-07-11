"""Project configuration: adp.yaml load/save with env interpolation.

Precedence: defaults < adp.yaml < environment variables (via ${VAR} interpolation).
Secrets are never stored in adp.yaml — connectors read `${ENV_VAR}` references
or use `api_key_env` indirection.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_data_platform.core.env import SECRET_SHAPED as _SECRET_SHAPED
from ai_data_platform.core.env import interpolate_env  # re-exported for callers/tests

__all__ = [
    "CONFIG_FILENAME",
    "CONFIG_VERSION",
    "DestinationConfig",
    "ExplorerConfig",
    "GenerationConfig",
    "LoadConfig",
    "ModelProviderConfig",
    "ProjectConfig",
    "SemanticConfig",
    "SourceConfig",
    "SourceType",
    "config_path",
    "default_config",
    "interpolate_env",
    "load_config",
    "save_config",
]
from ai_data_platform.core.exceptions import ConfigError, ProjectNotInitializedError
from ai_data_platform.load.config_models import DestinationConfig, LoadConfig

CONFIG_FILENAME = "adp.yaml"
CONFIG_VERSION = 1

SourceType = Literal[
    "csv", "parquet", "duckdb", "postgres", "mysql", "snowflake", "trino", "bigquery"
]


class SourceConfig(BaseModel):
    """One configured data source."""

    model_config = ConfigDict(extra="forbid")

    name: str
    type: SourceType
    path: str | None = None  # csv/parquet/duckdb
    dsn: str | None = None  # postgres/mysql — use ${ENV_VAR} for credentials
    schema_name: str | None = Field(default=None, alias="schema")
    options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("dsn")
    @classmethod
    def _no_plaintext_secrets(cls, v: str | None) -> str | None:
        if v and _SECRET_SHAPED.search(v):
            raise ValueError(
                "dsn appears to contain a plaintext secret; use ${ENV_VAR} interpolation instead"
            )
        return v

    def resolved_dsn(self) -> str | None:
        """DSN with ${VAR} references replaced from the environment."""
        if self.dsn is None:
            return None
        return interpolate_env(self.dsn)


class ModelProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["minimax", "openai", "anthropic", "gemini", "local"] = "minimax"
    base_url: str = "https://api.minimax.io/v1"
    model: str = "MiniMax-Text-01"
    api_key_env: str = "MINIMAX_API_KEY"
    timeout_seconds: float = 60.0

    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)


class GenerationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_rows: int = 1000
    seed: int = 42
    chunk_rows: int = 100_000
    output_format: Literal["csv", "parquet", "duckdb", "sql"] = "parquet"
    # Parallel chunk builders: 0 = auto (min(cpu_count, 8)), 1 = disabled.
    parallel_workers: int = Field(default=0, ge=0, le=64)
    # Executor: python (default), go (external binary), auto (go when available + threshold met).
    executor: Literal["python", "go", "auto"] = "python"
    go_executor_threshold_rows: int = Field(default=10_000_000, ge=1)
    # Calendar-feature defaults (used when a spec's `calendar` block omits them).
    fiscal_year_start_month: int = Field(default=1, ge=1, le=12)
    hemisphere: Literal["north", "south"] = "north"
    holiday_country: str | None = None  # ISO code, e.g. "IN" — for calendar is_holiday


class SemanticConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["generic", "cube"] = "generic"


class ExplorerConfig(BaseModel):
    """MCP Data Explorer: DuckDB-backed exploration of generated datasets.

    All limits are enforced defensively (read-only connection + SQL guard +
    LIMIT wrap + query timeout). `metadata_dsn` lets the dataset catalog live in
    Postgres instead of the default project-local SQLite.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    # Register generated files into DuckDB automatically after generate-data.
    auto_register: bool = True
    # Persistent DuckDB database file, relative to the project's .adp/ dir.
    db_filename: str = "explorer.duckdb"
    # Hard cap on rows returned by execute_sql / export (result is truncated,
    # `truncated: true` is flagged, and large outputs may be sampled).
    max_result_rows: int = Field(default=1000, ge=1, le=1_000_000)
    # Best-effort per-query wall-clock timeout (DuckDB interrupt watchdog).
    query_timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    # Best-effort guard: refuse queries whose EXPLAIN estimates exceed this many
    # scanned rows. None disables the check.
    max_scan_rows: int | None = Field(default=50_000_000, ge=1)
    # Return a uniform sample (USING SAMPLE) when a result exceeds max_result_rows
    # instead of a head() truncation.
    sample_large_results: bool = True
    # Optional external metadata store, e.g. "postgresql+psycopg://user@host/adp".
    # Credentials must use ${ENV_VAR} interpolation. None => project-local SQLite.
    metadata_dsn: str | None = None

    @field_validator("metadata_dsn")
    @classmethod
    def _no_plaintext_secrets(cls, v: str | None) -> str | None:
        if v and _SECRET_SHAPED.search(v):
            raise ValueError(
                "metadata_dsn appears to contain a plaintext secret; "
                "use ${ENV_VAR} interpolation instead"
            )
        return v

    def resolved_metadata_dsn(self) -> str | None:
        return interpolate_env(self.metadata_dsn) if self.metadata_dsn else None


class ProjectConfig(BaseModel):
    """The adp.yaml schema. `version` guards future migrations."""

    model_config = ConfigDict(extra="forbid")

    version: int = CONFIG_VERSION
    project: str
    type: str | None = None  # e.g. pipeline, workflow — informational
    tags: list[str] = Field(default_factory=list)
    environment: str = "dev"
    output_dir: str = "output"
    sources: list[SourceConfig] = Field(default_factory=list)
    model_provider: ModelProviderConfig = Field(default_factory=ModelProviderConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    semantic: SemanticConfig = Field(default_factory=SemanticConfig)
    explorer: ExplorerConfig = Field(default_factory=ExplorerConfig)
    destinations: list[DestinationConfig] = Field(default_factory=list)
    load: LoadConfig = Field(default_factory=LoadConfig)

    def source(self, name: str) -> SourceConfig:
        for s in self.sources:
            if s.name == name:
                return s
        from ai_data_platform.core.exceptions import SourceNotFoundError

        raise SourceNotFoundError(name, [s.name for s in self.sources])

    def destination(self, name: str) -> DestinationConfig:
        for d in self.destinations:
            if d.name == name:
                return d
        from ai_data_platform.core.exceptions import DestinationNotFoundError

        raise DestinationNotFoundError(name, [d.name for d in self.destinations])


def config_path(root: str | Path = ".") -> Path:
    return Path(root).expanduser().resolve() / CONFIG_FILENAME


def load_config(root: str | Path = ".") -> ProjectConfig:
    """Load and validate adp.yaml; loads .env from the project root first."""
    root = Path(root).expanduser().resolve()
    load_dotenv(root / ".env", override=False)
    path = config_path(root)
    if not path.exists():
        raise ProjectNotInitializedError(str(root))
    try:
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"adp.yaml is not valid YAML: {e}") from e
    from ai_data_platform.config_normalize import normalize_adp_yaml

    try:
        return ProjectConfig.model_validate(normalize_adp_yaml(raw))
    except Exception as e:
        raise ConfigError(f"adp.yaml failed validation: {e}") from e


def save_config(cfg: ProjectConfig, root: str | Path = ".") -> Path:
    path = config_path(root)
    data = cfg.model_dump(mode="json", by_alias=True, exclude_none=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def default_config(project_name: str) -> ProjectConfig:
    return ProjectConfig(project=project_name)
