"""Tests for generate-and-load orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import polars as pl
import pytest

from ai_data_platform.config import LoadConfig, save_config
from ai_data_platform.load.config_models import DestinationConfig
from ai_data_platform.load.generate_load import GenerateLoadEngine
from ai_data_platform.load.types import TableLoadResult
from ai_data_platform.sdk import ADPClient


@pytest.fixture()
def load_project(profiled_project: ADPClient, monkeypatch) -> ADPClient:
    monkeypatch.setenv("DUCKDB_PATH", str(profiled_project.root / "wh.duckdb"))
    client = profiled_project
    cfg = client.config
    cfg.destinations = [
        DestinationConfig(name="local", uri="duckdb:///${DUCKDB_PATH}", table_prefix="main")
    ]
    cfg.load = LoadConfig(default_destination="local", require_quality_pass=False)
    save_config(cfg, client.root)
    return client


def test_generate_load_dry_run(load_project: ADPClient) -> None:
    engine = GenerateLoadEngine(load_project.root, load_project.catalog, load_project.config)
    res = engine.run(dry_run=True)
    assert res["load"]["ok"]
    assert len(res["generated"]) >= 2
    assert all(t["status"] == "dry_run" for t in res["load"]["tables"])


def test_generate_load_with_mock_transport(load_project: ADPClient, monkeypatch) -> None:
    monkeypatch.setenv("DUCKDB_PATH", str(load_project.root / "wh.duckdb"))

    def fake_load(spec, *, dry_run=False):  # noqa: ANN001
        return TableLoadResult(
            table=spec.table,
            dest_table=spec.dest_table,
            status="dry_run" if dry_run else "ok",
            elapsed_ms=1.0,
        )

    transport = MagicMock()
    transport.load_table.side_effect = fake_load
    transport.ensure_available = MagicMock()
    monkeypatch.setattr(
        "ai_data_platform.load.generate_load.get_transport",
        lambda name="ingestr": transport,
    )
    engine = GenerateLoadEngine(load_project.root, load_project.catalog, load_project.config)
    res = engine.run()
    assert res["load"]["ok"]
    assert transport.load_table.call_count >= 2
    out = load_project.root / "output"
    assert any(out.glob("*.parquet"))
