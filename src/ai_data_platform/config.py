"""Project configuration: adp.yaml load/save with env interpolation.

Precedence: defaults < adp.yaml < environment variables (via ${VAR} interpolation).
Secrets are never stored in adp.yaml — connectors read `${ENV_VAR}` references
or use `api_key_env` indirection.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_data_platform.core.exceptions import ConfigError, ProjectNotInitializedError

CONFIG_FILENAME = "adp.yaml"
CONFIG_VERSION = 1

_ENV_REF = re.compile(r"\$\{(?P<name>[A-Z0-9_]+)\}")
_SECRET_SHAPED = re.compile(r"(sk-[A-Za-z0-9\-_]{16,}|[A-Za-z0-9\-_]{48,})")

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


class SemanticConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["generic", "cube"] = "generic"


class ProjectConfig(BaseModel):
    """The adp.yaml schema. `version` guards future migrations."""

    model_config = ConfigDict(extra="forbid")

    version: int = CONFIG_VERSION
    project: str
    environment: str = "dev"
    output_dir: str = "output"
    sources: list[SourceConfig] = Field(default_factory=list)
    model_provider: ModelProviderConfig = Field(default_factory=ModelProviderConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    semantic: SemanticConfig = Field(default_factory=SemanticConfig)

    def source(self, name: str) -> SourceConfig:
        for s in self.sources:
            if s.name == name:
                return s
        from ai_data_platform.core.exceptions import SourceNotFoundError

        raise SourceNotFoundError(name, [s.name for s in self.sources])


def interpolate_env(value: str) -> str:
    """Replace ${VAR} with environment values; missing vars raise ConfigError."""

    def _sub(m: re.Match[str]) -> str:
        name = m.group("name")
        val = os.environ.get(name)
        if val is None:
            raise ConfigError(
                f"Environment variable {name!r} referenced in adp.yaml is not set.",
                hint=f"export {name}=... or add it to your .env file.",
            )
        return val

    return _ENV_REF.sub(_sub, value)


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
    try:
        return ProjectConfig.model_validate(raw)
    except Exception as e:
        raise ConfigError(f"adp.yaml failed validation: {e}") from e


def save_config(cfg: ProjectConfig, root: str | Path = ".") -> Path:
    path = config_path(root)
    data = cfg.model_dump(mode="json", by_alias=True, exclude_none=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def default_config(project_name: str) -> ProjectConfig:
    return ProjectConfig(project=project_name)
