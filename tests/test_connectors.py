"""Connector contract: CSV, Parquet, DuckDB; placeholders; registry."""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl
import pytest

from ai_data_platform.config import SourceConfig
from ai_data_platform.connectors import REGISTRY, get_connector
from ai_data_platform.connectors.base import SampleBudget
from ai_data_platform.core.exceptions import (
    ConnectorError,
    ConnectorNotAvailableError,
    TableNotFoundError,
)


def test_registry_covers_all_config_types() -> None:
    from typing import get_args

    from ai_data_platform.config import SourceType

    assert set(get_args(SourceType)) == set(REGISTRY)


def test_csv_connector(sample_data_dir: Path) -> None:
    conn = get_connector(SourceConfig(name="s", type="csv", path=str(sample_data_dir)))
    assert conn.test_connection().ok
    assert sorted(conn.list_tables()) == ["customers", "orders"]
    schema = conn.get_table_schema("orders")
    names = [c.name for c in schema.columns]
    assert "order_id" in names and "total_amount" in names
    df = conn.sample_data("orders", SampleBudget(rows=50))
    assert len(df) == 50


def test_csv_missing_path() -> None:
    conn = get_connector(SourceConfig(name="s", type="csv", path="/nonexistent/dir"))
    assert not conn.test_connection().ok
    with pytest.raises(ConnectorError):
        conn.list_tables()


def test_csv_unknown_table(sample_data_dir: Path) -> None:
    conn = get_connector(SourceConfig(name="s", type="csv", path=str(sample_data_dir)))
    with pytest.raises(TableNotFoundError):
        conn.get_table_schema("nope")


def test_parquet_connector(tmp_path: Path) -> None:
    pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]}).write_parquet(tmp_path / "t.parquet")
    conn = get_connector(SourceConfig(name="s", type="parquet", path=str(tmp_path)))
    assert conn.test_connection().ok
    assert conn.list_tables() == ["t"]
    assert len(conn.sample_data("t")) == 3


def test_duckdb_connector(tmp_path: Path) -> None:
    db = tmp_path / "test.duckdb"
    with duckdb.connect(str(db)) as con:
        con.execute("create table items as select range as id, 'x' as val from range(100)")
    conn = get_connector(SourceConfig(name="s", type="duckdb", path=str(db)))
    result = conn.test_connection()
    assert result.ok, result.message
    assert conn.list_tables() == ["items"]
    schema = conn.get_table_schema("items")
    assert schema.row_count == 100
    assert len(conn.sample_data("items", SampleBudget(rows=10))) == 10


def test_placeholders_raise_with_guidance() -> None:
    for t in ("snowflake", "trino", "bigquery"):
        conn = get_connector(SourceConfig(name="s", type=t))  # type: ignore[arg-type]
        with pytest.raises(ConnectorNotAvailableError):
            conn.list_tables()
        assert not conn.test_connection().ok


def test_profile_table_default(sample_data_dir: Path) -> None:
    conn = get_connector(SourceConfig(name="s", type="csv", path=str(sample_data_dir)))
    prof = conn.profile_table("customers")
    assert prof["table"] == "customers"
    assert any(c["name"] == "customer_id" for c in prof["columns"])
