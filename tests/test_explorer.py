"""MCP Data Explorer: registration, governed queries, security guard, insights."""

from __future__ import annotations

import pytest

from ai_data_platform.core.exceptions import (
    ExplorerTableNotFoundError,
    UnsafeSQLError,
)
from ai_data_platform.explorer.security import guard_select, wrap_with_limit
from ai_data_platform.sdk import ADPClient


@pytest.fixture()
def generated_project(profiled_project: ADPClient) -> ADPClient:
    """Profiled project with parquet data generated (auto-registered into DuckDB)."""
    profiled_project.generate_data(rows=200, output_format="parquet")
    return profiled_project


# -- registration ----------------------------------------------------------
def test_auto_register_on_generate(profiled_project: ADPClient) -> None:
    out = profiled_project.generate_data(rows=150, output_format="parquet")
    assert "explorer" in out
    assert set(out["explorer"]["registered"]) >= {"customers", "orders"}


def test_list_datasets_and_tables(generated_project: ADPClient) -> None:
    datasets = generated_project.list_datasets()
    assert any(d["dataset"] == "default" for d in datasets)
    tables = generated_project.list_explorer_tables("default")
    names = {t["table"] for t in tables}
    assert {"customers", "orders"} <= names
    for t in tables:
        assert t["row_count"] and t["row_count"] > 0
        assert t["column_count"] > 0


def test_describe_and_schema(generated_project: ADPClient) -> None:
    desc = generated_project.describe_dataset_table("orders")
    assert desc["table"] == "orders"
    assert any(c["name"] == "total_amount" for c in desc["columns"])
    schema = generated_project.show_table_schema("orders")
    assert "CREATE VIEW" in schema["ddl"]


def test_missing_table_raises(generated_project: ADPClient) -> None:
    with pytest.raises(ExplorerTableNotFoundError):
        generated_project.describe_dataset_table("nope")


# -- querying --------------------------------------------------------------
def test_preview_and_count(generated_project: ADPClient) -> None:
    prev = generated_project.preview_dataset_table("customers", limit=5)
    assert prev["showing"] <= 5
    assert prev["columns"]
    count = generated_project.get_table_row_count("customers")
    assert count["row_count"] > 0


def test_execute_sql_ok(generated_project: ADPClient) -> None:
    res = generated_project.execute_explorer_sql(
        "SELECT status, count(*) AS n FROM orders GROUP BY status ORDER BY n DESC"
    )
    assert res["columns"][:1] == ["status"]
    assert res["row_count"] >= 1
    assert res["elapsed_ms"] >= 0


def test_row_limit_truncation(generated_project: ADPClient) -> None:
    res = generated_project.execute_explorer_sql("SELECT * FROM orders", max_rows=10)
    assert res["row_count"] == 10
    assert res["truncated"] is True


def test_explain(generated_project: ADPClient) -> None:
    res = generated_project.explain_explorer_sql("SELECT * FROM orders")
    assert isinstance(res["plan"], str) and res["plan"]


def test_profile_table(generated_project: ADPClient) -> None:
    prof = generated_project.profile_dataset_table("orders")
    cols = {c["column"]: c for c in prof["columns"]}
    assert "total_amount" in cols
    assert cols["total_amount"]["mean"] is not None
    assert cols["total_amount"]["null_fraction"] >= 0.0


def test_export_result(generated_project: ADPClient, tmp_path) -> None:
    res = generated_project.export_explorer_result("SELECT * FROM customers", "cust.csv", fmt="csv")
    assert res["row_count"] > 0
    from pathlib import Path

    assert Path(res["path"]).exists()


# -- security guard --------------------------------------------------------
@pytest.mark.parametrize(
    "bad",
    [
        "DROP TABLE orders",
        "DELETE FROM orders",
        "UPDATE orders SET x=1",
        "INSERT INTO orders VALUES (1)",
        "SELECT 1; SELECT 2",
        "COPY orders TO '/tmp/x.csv'",
        "ATTACH 'evil.db'",
        "PRAGMA database_list",
        "SET memory_limit='1GB'",
        "SELECT * FROM read_csv_auto('/etc/passwd')",
        "SELECT * FROM read_parquet('/secret/*.parquet')",
    ],
)
def test_guard_rejects(bad: str) -> None:
    with pytest.raises(UnsafeSQLError):
        guard_select(bad)


@pytest.mark.parametrize(
    "good", ["SELECT 1", "  select * from t  ", "WITH a AS (SELECT 1) SELECT * FROM a"]
)
def test_guard_allows_select(good: str) -> None:
    assert guard_select(good)


def test_execute_sql_blocks_mutation(generated_project: ADPClient) -> None:
    with pytest.raises(UnsafeSQLError):
        generated_project.execute_explorer_sql("DELETE FROM orders")


def test_wrap_with_limit_forms() -> None:
    assert "LIMIT 11" in wrap_with_limit("SELECT 1", max_rows=10, sample=False)
    assert "USING SAMPLE reservoir(11 ROWS)" in wrap_with_limit(
        "SELECT 1", max_rows=10, sample=True
    )


# -- insights --------------------------------------------------------------
def test_suggest_queries(generated_project: ADPClient) -> None:
    sug = generated_project.suggest_analytics_queries("default")
    assert sug["suggestions"]
    assert all("sql" in s for s in sug["suggestions"])


def test_business_insights(generated_project: ADPClient) -> None:
    ins = generated_project.generate_business_insights(
        "SELECT status, count(*) AS n FROM orders GROUP BY status"
    )
    assert ins["summary"]
    assert ins["result_preview"]["row_count"] >= 1
    assert isinstance(ins["dashboard_metrics"], list)


def test_validate_questions(generated_project: ADPClient) -> None:
    res = generated_project.validate_business_questions(
        ["How many orders per status?", "What is the airspeed of a swallow?"]
    )
    verdicts = {v["question"]: v for v in res["verdicts"]}
    assert verdicts["How many orders per status?"]["answerable"] is True
