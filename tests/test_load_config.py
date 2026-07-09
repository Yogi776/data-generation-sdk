"""Tests for load config models and ProjectConfig integration."""

from __future__ import annotations

import pytest

from ai_data_platform.config import ProjectConfig, load_config, save_config
from ai_data_platform.core.exceptions import ConfigError, DestinationNotFoundError
from ai_data_platform.load.config_models import DestinationConfig, LoadConfig


def test_destination_config_uri_scheme_required() -> None:
    with pytest.raises(ValueError, match="scheme"):
        DestinationConfig(name="x", uri="not-a-uri")


def test_project_config_destinations_roundtrip(tmp_path) -> None:
    cfg = ProjectConfig(
        project="t",
        destinations=[
            DestinationConfig(
                name="duck",
                uri="duckdb:///${DUCKDB_PATH}",
                table_prefix="main",
            )
        ],
        load=LoadConfig(default_destination="duck"),
    )
    save_config(cfg, tmp_path)
    loaded = load_config(tmp_path)
    assert loaded.destinations[0].name == "duck"
    assert loaded.load.default_destination == "duck"


def test_destination_lookup(tmp_path) -> None:
    cfg = ProjectConfig(
        project="t",
        destinations=[DestinationConfig(name="a", uri="duckdb:///x.db")],
    )
    assert cfg.destination("a").name == "a"
    with pytest.raises(DestinationNotFoundError):
        cfg.destination("missing")


def test_resolved_uri_interpolation(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WAREHOUSE_URI", "duckdb:///tmp/w.db")
    d = DestinationConfig(name="w", uri="${WAREHOUSE_URI}")
    assert d.resolved_uri() == "duckdb:///tmp/w.db"


def test_resolved_uri_missing_env() -> None:
    d = DestinationConfig(name="w", uri="${MISSING_LOAD_URI_XYZ}")
    with pytest.raises(ConfigError):
        d.resolved_uri()
