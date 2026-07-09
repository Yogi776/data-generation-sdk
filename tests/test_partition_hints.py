"""Tests for partition hint detection and load-plan integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import polars as pl
import pytest

from ai_data_platform.config import LoadConfig, save_config
from ai_data_platform.load.config_models import DestinationConfig
from ai_data_platform.load.partition_hints import (
    auto_extract_options,
    partition_column_for_table,
)
from ai_data_platform.load.plan import build_load_plan
from ai_data_platform.sdk import ADPClient


@pytest.fixture()
def load_project(profiled_project: ADPClient, monkeypatch) -> ADPClient:
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
    save_config(cfg, client.root)
    return client


def test_partition_column_prefers_order_date() -> None:
    catalog = MagicMock()
    catalog.get_table.return_value = {
        "columns": [
            {"name": "id", "type": "integer"},
            {"name": "created_at", "type": "timestamp"},
            {"name": "order_date", "type": "date"},
        ],
    }
    assert partition_column_for_table(catalog, "fact_order_item") == "order_date"


def test_auto_extract_options_skips_small_tables() -> None:
    catalog = MagicMock()
    catalog.get_table.return_value = {
        "columns": [{"name": "order_date", "type": "date"}],
    }
    assert auto_extract_options(catalog, "fact_order_item", row_count=500_000) == {}


def test_auto_extract_options_large_table() -> None:
    catalog = MagicMock()
    catalog.get_table.return_value = {
        "columns": [{"name": "order_date", "type": "date"}],
    }
    opts = auto_extract_options(catalog, "fact_order_item", row_count=10_000_000)
    assert opts == {
        "extract_partition_by": "order_date",
        "extract_partition_interval": "auto",
    }


def test_build_load_plan_auto_partition_merge_strategy(load_project, tmp_path: Path) -> None:
    cfg = load_project.config
    dest = DestinationConfig(
        name="local",
        uri="duckdb:///${DUCKDB_PATH}",
        table_prefix="main",
        incremental_strategy="merge",
        primary_key="id",
        auto_extract_partition=True,
    )
    catalog = load_project.catalog
    catalog.get_table = MagicMock(
        side_effect=lambda t: {
            "columns": [
                {"name": "id", "type": "integer"},
                {"name": "order_date", "type": "date"},
            ],
            "row_count": 5_000_000,
        }
    )
    plan = build_load_plan(
        cfg,
        catalog,
        dest,
        data_dir=load_project.root / "output",
    )
    spec = plan.waves[-1][-1]
    assert spec.ingestr_options.get("extract_partition_by") == "order_date"


def test_build_load_plan_skips_auto_partition_on_replace(load_project) -> None:
    cfg = load_project.config
    dest = DestinationConfig(
        name="local",
        uri="duckdb:///${DUCKDB_PATH}",
        table_prefix="main",
        incremental_strategy="replace",
        auto_extract_partition=True,
    )
    catalog = load_project.catalog
    catalog.get_table = MagicMock(
        return_value={
            "columns": [{"name": "order_date", "type": "date"}],
            "row_count": 10_000_000,
        }
    )
    plan = build_load_plan(
        cfg,
        catalog,
        dest,
        data_dir=load_project.root / "output",
    )
    for wave in plan.waves:
        for spec in wave:
            assert "extract_partition_by" not in spec.ingestr_options
