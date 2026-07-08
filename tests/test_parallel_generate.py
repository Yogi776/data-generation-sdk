"""Tests for parallel chunk generation."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from ai_data_platform.generator.engine import (
    ColumnPlan,
    ForeignKeyPlan,
    GenerationPlan,
    TablePlan,
    generate,
)


def test_parallel_matches_sequential(tmp_path: Path) -> None:
    plan = GenerationPlan(
        seed=99,
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
    seq = generate(plan, tmp_path / "seq", output_format="parquet", parallel_workers=1)
    par = generate(plan, tmp_path / "par", output_format="parquet", parallel_workers=4)
    for table in ("customers", "orders"):
        a = pl.read_parquet(seq[table]["path"])
        b = pl.read_parquet(par[table]["path"])
        assert a.equals(b), f"{table} differs between sequential and parallel"
