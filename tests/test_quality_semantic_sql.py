"""Quality checks, semantic model output, SQL guardrails."""

from __future__ import annotations

import pytest
import yaml

from ai_data_platform.core.exceptions import UnsafeSQLError
from ai_data_platform.sdk import ADPClient
from ai_data_platform.sql.assistant import guard_sql


def test_quality_of_generated_data(profiled_project: ADPClient) -> None:
    profiled_project.generate_data(rows=500, output_format="parquet")
    report = profiled_project.quality_check()
    assert report["quality_score"] >= 95, report
    assert set(report["category_scores"]) >= {"integrity", "completeness"}


def test_quality_catches_orphans(profiled_project: ADPClient) -> None:
    import polars as pl

    from ai_data_platform.core.paths import safe_resolve

    profiled_project.generate_data(rows=200, output_format="parquet")
    out = safe_resolve(profiled_project.root, "output")
    orders = pl.read_parquet(out / "orders.parquet")
    corrupted = orders.with_columns(pl.lit(999_999).alias("customer_id"))
    corrupted.write_parquet(out / "orders.parquet")
    report = profiled_project.quality_check()
    fk_checks = [
        c
        for t in report["tables"]
        if t["table"] == "orders"
        for c in t["checks"]
        if c["rule_type"] == "foreign_key"
    ]
    assert fk_checks and not fk_checks[0]["passed"]


def test_semantic_model_generic_and_cube(profiled_project: ADPClient) -> None:
    generic = profiled_project.create_semantic_model(fmt="generic")
    model = yaml.safe_load(generic["rendered"])
    entities = {e["name"]: e for e in model["entities"]}
    assert entities["orders"]["kind"] == "fact"
    assert entities["customers"]["kind"] == "dimension"
    assert any(m["agg"] == "sum" for m in entities["orders"]["measures"])
    assert model["joins"] and model["joins"][0]["relationship"] == "many_to_one"

    cube = profiled_project.create_semantic_model(fmt="cube")
    parsed = yaml.safe_load(cube["rendered"])
    names = {c["name"] for c in parsed["cubes"]}
    assert names == {"customers", "orders"}
    orders_cube = next(c for c in parsed["cubes"] if c["name"] == "orders")
    assert "joins" in orders_cube and "customers" in orders_cube["joins"]


def test_guard_sql_allows_select() -> None:
    assert guard_sql("SELECT * FROM t LIMIT 5;") == "SELECT * FROM t LIMIT 5"
    assert guard_sql("WITH x AS (SELECT 1) SELECT * FROM x").startswith("WITH")


@pytest.mark.parametrize(
    "bad",
    [
        "DROP TABLE users",
        "DELETE FROM t",
        "INSERT INTO t VALUES (1)",
        "SELECT 1; DROP TABLE t",
        "update t set a=1",
        "",
        "PRAGMA database_list",
    ],
)
def test_guard_sql_rejects(bad: str) -> None:
    with pytest.raises(UnsafeSQLError):
        guard_sql(bad)


def test_sql_local_provider_end_to_end(profiled_project: ADPClient) -> None:
    """Offline stub provider exercises grounding + guard without a network key."""

    from ai_data_platform.config import load_config, save_config

    cfg = load_config(profiled_project.root)
    cfg.model_provider.provider = "local"
    save_config(cfg, profiled_project.root)
    result = profiled_project.generate_sql("show me some rows")
    assert result["sql"].lower().startswith("select")
    assert result["tables_used"]


def test_docs_generation(profiled_project: ADPClient) -> None:
    md = profiled_project.generate_docs()
    assert "# Data Dictionary" in md
    assert "## orders" in md and "## customers" in md
    assert "Relationships" in md
