"""Config loading, env interpolation, secret hygiene, masked logging."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_data_platform.config import (
    ProjectConfig,
    SourceConfig,
    default_config,
    interpolate_env,
    load_config,
    save_config,
)
from ai_data_platform.core.exceptions import ConfigError, ProjectNotInitializedError
from ai_data_platform.core.logging import mask_secrets


def test_roundtrip(tmp_path: Path) -> None:
    cfg = default_config("demo")
    save_config(cfg, tmp_path)
    loaded = load_config(tmp_path)
    assert loaded.project == "demo"
    assert loaded.model_provider.provider == "minimax"
    assert loaded.version == 1


def test_missing_config_raises(tmp_path: Path) -> None:
    with pytest.raises(ProjectNotInitializedError):
        load_config(tmp_path)


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    (tmp_path / "adp.yaml").write_text("project: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_env_interpolation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PGPASSWORD", "s3cret")
    assert interpolate_env("pg://u:${PGPASSWORD}@h/db") == "pg://u:s3cret@h/db"
    with pytest.raises(ConfigError):
        interpolate_env("pg://u:${MISSING_VAR_XYZ}@h/db")


def test_plaintext_secret_in_dsn_rejected() -> None:
    with pytest.raises(ValueError):
        SourceConfig(
            name="bad",
            type="postgres",
            dsn="postgresql://u:sk-cp-abcdefghijklmnopqrstuvwx@h/db",
        )


def test_source_lookup() -> None:
    cfg = ProjectConfig(project="p", sources=[SourceConfig(name="a", type="csv", path="x")])
    assert cfg.source("a").name == "a"
    from ai_data_platform.core.exceptions import SourceNotFoundError

    with pytest.raises(SourceNotFoundError):
        cfg.source("nope")


def test_secret_masking() -> None:
    line = 'connecting api_key="sk-cp-1234567890abcdefghij" password=hunter2'
    masked = mask_secrets(line)
    assert "sk-cp-1234567890abcdefghij" not in masked
    assert "hunter2" not in masked
    assert "REDACTED" in masked
