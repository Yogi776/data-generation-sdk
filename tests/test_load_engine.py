"""Load plan and engine integration tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import polars as pl
import pytest

from ai_data_platform.load.config_models import DestinationConfig, LoadConfig
from ai_data_platform.load.engine import LoadEngine
from ai_data_platform.load.plan import build_load_plan
from ai_data_platform.load.types import TableLoadResult
from ai_data_platform.sdk import ADPClient


@pytest.fixture()
def load_project(profiled_project: ADPClient, tmp_path: Path, monkeypatch) -> ADPClient:
    monkeypatch.setenv("DUCKDB_PATH", str(profiled_project.root / "wh.duckdb"))
    client = profiled_project
    out = client.root / "output"
    out.mkdir(exist_ok=True)
    for table in ("customers", "orders"):
        pl.DataFrame({"id": [1, 2], "customer_id": [1, 1]}).write_parquet(out / f"{table}.parquet")
    cfg = client.config
    cfg.destinations = [
        DestinationConfig(name="local", uri="duckdb:///${DUCKDB_PATH}", table_prefix="main")
    ]
    cfg.load = LoadConfig(default_destination="local", require_quality_pass=False)
    from ai_data_platform.config import save_config

    save_config(cfg, client.root)
    return client


def test_build_load_plan_waves(load_project: ADPClient) -> None:
    cfg = load_project.config
    dest = cfg.destination("local")
    plan = build_load_plan(
        cfg,
        load_project.catalog,
        dest,
        data_dir=load_project.root / "output",
    )
    assert plan.waves
    assert plan.waves[0][0].source_table.endswith("#parquet")


def test_load_dry_run(load_project: ADPClient, monkeypatch) -> None:
    monkeypatch.setenv("DUCKDB_PATH", str(load_project.root / "wh.duckdb"))
    res = load_project.load_data(dry_run=True, skip_quality=True)
    assert res["ok"]
    assert all(t["status"] == "dry_run" for t in res["tables"])


def test_load_engine_with_mock_transport(load_project: ADPClient, monkeypatch) -> None:
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
        "ai_data_platform.load.engine.get_transport",
        lambda name="ingestr": transport,
    )
    engine = LoadEngine(load_project.root, load_project.catalog, load_project.config)
    report = engine.load(skip_quality=True)
    assert report.ok
    assert transport.load_table.call_count >= 1
    transport.ensure_available.assert_called_once()


def test_primary_keys_for_tables(load_project: ADPClient) -> None:
    pks = load_project.catalog.primary_keys_for_tables(["customers", "orders"])
    assert "customers" in pks or "orders" in pks or pks == {}
