"""Generation invariants: determinism, FK integrity, formats, plan shape."""

from __future__ import annotations

from pathlib import Path

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


def test_streaming_across_chunks(tmp_path: Path) -> None:
    """Generation streams chunk-by-chunk (bounded memory); keys and FK integrity
    must hold across chunk boundaries, not just within a single chunk."""
    from ai_data_platform.generator.engine import (
        ColumnPlan,
        ForeignKeyPlan,
        GenerationPlan,
        TablePlan,
        generate,
    )

    # chunk_rows=100 forces many chunks for both tables
    plan = GenerationPlan(
        seed=7,
        chunk_rows=100,
        tables=[
            TablePlan(
                name="customers",
                rows=550,
                columns=[ColumnPlan(name="customer_id", sampler="sequence", params={"start": 1})],
            ),
            TablePlan(
                name="orders",
                rows=1234,
                columns=[ColumnPlan(name="order_id", sampler="uuid")],
                foreign_keys=[
                    ForeignKeyPlan(
                        column="customer_id", parent_table="customers", parent_column="customer_id"
                    )
                ],
            ),
        ],
    )
    r1 = generate(plan, tmp_path / "a", output_format="parquet")
    cust = pl.read_parquet(r1["customers"]["path"])
    orders = pl.read_parquet(r1["orders"]["path"])

    assert r1["customers"]["rows"] == 550 and len(cust) == 550
    assert r1["orders"]["rows"] == 1234 and len(orders) == 1234
    # sequence PK contiguous across chunk boundaries (offset math)
    assert cust.get_column("customer_id").to_list() == list(range(1, 551))
    # uuid PK unique across all chunks
    assert orders.get_column("order_id").n_unique() == 1234
    # FK zero-orphans across chunks
    parent = set(cust.get_column("customer_id").to_list())
    assert set(orders.get_column("customer_id").to_list()) <= parent

    # same (seed, chunk_rows) is byte-identical across runs
    r2 = generate(plan, tmp_path / "b", output_format="parquet")
    assert pl.read_parquet(r1["orders"]["path"]).equals(pl.read_parquet(r2["orders"]["path"]))
