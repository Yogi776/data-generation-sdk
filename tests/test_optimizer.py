"""Execution planner / complexity analyzer: estimates, partitioning, warnings."""

from __future__ import annotations

from pathlib import Path

from ai_data_platform.generator.engine import GenerationPlan
from ai_data_platform.optimizer import analyze_complexity, estimate_memory, plan_execution
from ai_data_platform.optimizer.batch_strategy import runtime_class
from ai_data_platform.optimizer.memory_estimator import OVERHEAD, column_bytes
from ai_data_platform.sdk import ADPClient

SEASONAL_SPEC = """
version: 1
tables:
  - name: dim_customer
    rows: 100000
    columns:
      - {name: customer_id, type: uuid, primary_key: true}
      - {name: full_name, type: string}
      - {name: email, type: string}
  - name: fact_orders
    seasonality:
      anchor: order_ts
      weekly: {Sat: 1.6}
      events: [{name: bf, start: 2024-11-28, end: 2024-11-30, multiplier: 5.0}]
    columns:
      - {name: order_id, type: uuid, primary_key: true}
      - {name: customer_id, type: uuid, references: dim_customer.customer_id}
      - {name: order_ts, type: datetime, start: 2024-01-01, end: 2025-12-31}
      - {name: amount, type: float, mean: 1000, std: 300}
      - {name: notes, type: string}
"""

FLAT_SPEC = """
version: 1
tables:
  - name: metrics
    columns:
      - {name: id, type: int, primary_key: true}
      - {name: value, type: float, mean: 10, std: 3}
      - {name: score, type: int, min: 0, max: 100}
"""


def _plan(tmp_path: Path, spec: str, rows: int) -> tuple[ADPClient, GenerationPlan]:
    c = ADPClient(tmp_path)
    c.init("opt")
    (tmp_path / "spec.yaml").write_text(spec, encoding="utf-8")
    c.apply_spec("spec.yaml")
    return c, GenerationPlan.model_validate(c.build_plan(rows=rows, seed=42))


# -- pure estimator ------------------------------------------------------------
def test_column_bytes_by_sampler() -> None:
    from ai_data_platform.generator.engine import ColumnPlan

    assert column_bytes(ColumnPlan(name="x", sampler="uuid")) == 36
    assert column_bytes(ColumnPlan(name="x", sampler="bool")) == 1
    assert column_bytes(ColumnPlan(name="x", sampler="normal")) == 8
    assert column_bytes(ColumnPlan(name="x", sampler="template", params={"pattern": "SKU-#####"})) == 9
    assert column_bytes(ColumnPlan(name="x", sampler="words", params={"k": 3})) == 19


def test_memory_estimate_matches_formula(tmp_path: Path) -> None:
    # single standalone table (no children => no key_pool contribution)
    _, plan = _plan(tmp_path, FLAT_SPEC, rows=1_000_000)
    mem = estimate_memory(plan, workers=4)
    tp = plan.tables[0]
    row_bytes = 8 + 8 + 8  # int PK(seq) + float + int
    expected_mb = row_bytes * tp.rows * OVERHEAD / 1e6
    assert abs(mem["peak_mb"] - expected_mb) < 0.5
    assert mem["contributors"]["key_pool_mb"] == 0.0


def test_memory_scales_with_rows(tmp_path: Path) -> None:
    _, small = _plan(tmp_path / "a", FLAT_SPEC, rows=1_000_000)
    _, big = _plan(tmp_path / "b", FLAT_SPEC, rows=100_000_000)
    assert estimate_memory(big)["peak_mb"] > 50 * estimate_memory(small)["peak_mb"]


# -- execution plan ------------------------------------------------------------
def test_plan_has_prompt_schema_keys(tmp_path: Path) -> None:
    c, plan = _plan(tmp_path, SEASONAL_SPEC, rows=1000)
    ep = plan_execution(plan, c.config.generation)
    for key in (
        "estimated_rows", "recommended_batch_size", "recommended_format", "partition_by",
        "parallelism", "memory_estimate_mb", "expected_runtime_class", "optimization_warnings",
    ):
        assert key in ep


def test_partition_by_prefers_seasonal_anchor(tmp_path: Path) -> None:
    # fact_orders (1M) is the largest table (dim_customer pinned at 100k)
    c, plan = _plan(tmp_path, SEASONAL_SPEC, rows=1_000_000)
    ep = plan_execution(plan, c.config.generation)
    assert ep["partition_by"] == ["order_ts"]


def test_no_partition_when_no_date_or_categorical(tmp_path: Path) -> None:
    c, plan = _plan(tmp_path, FLAT_SPEC, rows=1000)
    ep = plan_execution(plan, c.config.generation)
    assert ep["partition_by"] == []


def test_runtime_class_thresholds() -> None:
    assert runtime_class(500_000) == "small"
    assert runtime_class(5_000_000) == "medium"
    assert runtime_class(50_000_000) == "large"
    assert runtime_class(500_000_000) == "xlarge"


def test_warnings_fire_at_scale(tmp_path: Path) -> None:
    c, plan = _plan(tmp_path, SEASONAL_SPEC, rows=100_000_000)
    ep = plan_execution(plan, c.config.generation, memory_budget_mb=4096)
    warns = " ".join(ep["optimization_warnings"]).lower()
    assert "exceeds budget" in warns  # 100M over 4GB
    assert "gil-bound" in warns or "python string" in warns  # string samplers
    assert ep["expected_runtime_class"] == "xlarge"
    assert ep["recommended_format"] == "parquet"


def test_tiny_budget_triggers_over_budget(tmp_path: Path) -> None:
    c, plan = _plan(tmp_path, FLAT_SPEC, rows=10_000_000)
    ep = plan_execution(plan, c.config.generation, memory_budget_mb=1.0)
    assert any("exceeds budget" in w for w in ep["optimization_warnings"])


# -- complexity ----------------------------------------------------------------
def test_analyze_complexity_flags_string_samplers(tmp_path: Path) -> None:
    c, plan = _plan(tmp_path, SEASONAL_SPEC, rows=50_000_000)
    rep = analyze_complexity(plan)
    assert rep["modules"] and all({"module", "time", "space"} <= set(m) for m in rep["modules"])
    orders = next(t for t in rep["tables"] if t["table"] == "fact_orders")
    assert "order_id" in orders["python_string_columns"]  # uuid PK
    assert any("gil-bound" in w.lower() for w in rep["warnings"])


# -- generate --optimized wiring ----------------------------------------------
def test_generate_optimized_applies_plan(tmp_path: Path) -> None:
    import polars as pl

    c, _ = _plan(tmp_path, FLAT_SPEC, rows=5000)
    res = c.generate_data(rows=5000, output_format="parquet", register=False, optimized=True)
    df = pl.read_parquet(res["tables"]["metrics"]["path"])
    assert len(df) == 5000
