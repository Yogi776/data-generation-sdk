"""Generation invariants: determinism, FK integrity, formats, plan shape."""

from __future__ import annotations

import polars as pl

from ai_data_platform.sdk import ADPClient


def test_plan_is_ir_shaped(profiled_project: ADPClient) -> None:
    plan = profiled_project.build_plan(rows=100)
    assert plan["plan_ir_version"] == 1
    assert plan["seed"] == 42
    names = [t["name"] for t in plan["tables"]]
    # parents before children
    assert names.index("customers") < names.index("orders")
    orders = next(t for t in plan["tables"] if t["name"] == "orders")
    assert any(fk["parent_table"] == "customers" for fk in orders["foreign_keys"])


def test_generate_fk_integrity(profiled_project: ADPClient) -> None:
    result = profiled_project.generate_data(rows=500, output_format="parquet")
    out = {k: pl.read_parquet(v["path"]) for k, v in result["tables"].items()}
    child_keys = set(out["orders"].get_column("customer_id").to_list())
    parent_keys = set(out["customers"].get_column("customer_id").to_list())
    assert child_keys <= parent_keys  # zero orphans
    assert len(out["orders"]) == 500


def test_generate_deterministic(profiled_project: ADPClient) -> None:
    r1 = profiled_project.generate_data(rows=200, seed=123, output_format="csv", output_dir="out1")
    r2 = profiled_project.generate_data(rows=200, seed=123, output_format="csv", output_dir="out2")
    for t in r1["tables"]:
        a = pl.read_csv(r1["tables"][t]["path"])
        b = pl.read_csv(r2["tables"][t]["path"])
        assert a.equals(b), f"{t} not reproducible for same seed"


def test_different_seed_differs(profiled_project: ADPClient) -> None:
    r1 = profiled_project.generate_data(rows=200, seed=1, output_format="csv", output_dir="s1")
    r2 = profiled_project.generate_data(rows=200, seed=2, output_format="csv", output_dir="s2")
    a = pl.read_csv(r1["tables"]["orders"]["path"])
    b = pl.read_csv(r2["tables"]["orders"]["path"])
    assert not a.equals(b)


def test_profiled_categories_respected(profiled_project: ADPClient) -> None:
    result = profiled_project.generate_data(rows=300, output_format="parquet")
    orders = pl.read_parquet(result["tables"]["orders"]["path"])
    statuses = set(orders.get_column("status").drop_nulls().to_list())
    assert statuses <= {"completed", "pending", "cancelled"}


def test_sql_output_format(profiled_project: ADPClient) -> None:
    result = profiled_project.generate_data(rows=50, output_format="sql", tables=["customers"])
    from pathlib import Path

    text = Path(result["tables"]["customers"]["path"]).read_text(encoding="utf-8")
    assert 'INSERT INTO "customers"' in text
    assert text.count("(") >= 50
