"""Universal seasonality engine: pure math, volume/value shaping, calendar,
cross-table propagation, determinism, streaming, and public surfaces."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from ai_data_platform.generator import seasonality as S
from ai_data_platform.sdk import ADPClient

SEASONAL_SPEC = """
version: 1
tables:
  - name: fact_orders
    seasonality:
      anchor: order_ts
      trend: {kind: linear, annual_growth: 0.6}
      weekly: {Sat: 2.5, Sun: 2.0, Mon: 0.5}
      events: [{name: bf, start: 2024-11-28, end: 2024-11-30, multiplier: 6.0}]
    columns:
      - {name: order_id, type: uuid, primary_key: true}
      - {name: order_ts, type: datetime, start: 2024-01-01, end: 2025-12-31}
      - name: revenue
        type: float
        mean: 1000
        std: 150
        seasonal_scale: {anchor: order_ts, trend: {kind: linear, annual_growth: 2.0}}
      - name: cal
        type: string
        calendar: {anchor: order_ts, parts: [day_of_week, is_weekend, quarter, season]}
  - name: fact_payments
    columns:
      - {name: payment_id, type: uuid, primary_key: true}
      - name: order_id
        type: uuid
        references: fact_orders.order_id
        inherit: "order_ts as parent_order_ts"
      - name: payment_ts
        type: datetime
        start: 2024-01-01
        end: 2025-12-31
        after: {column: parent_order_ts, min_minutes: 5, max_minutes: 720}
  - name: fact_shipments
    columns:
      - {name: shipment_id, type: uuid, primary_key: true}
      - name: payment_id
        type: uuid
        references: fact_payments.payment_id
        inherit: "payment_ts as parent_payment_ts"
      - name: shipped_ts
        type: datetime
        start: 2024-01-01
        end: 2025-12-31
        after: {column: parent_payment_ts, min_minutes: 60, max_minutes: 2880}
"""


@pytest.fixture()
def seasonal_project(tmp_path: Path) -> ADPClient:
    client = ADPClient(tmp_path)
    client.init("seasonal-test")
    (tmp_path / "spec.yaml").write_text(SEASONAL_SPEC, encoding="utf-8")
    client.apply_spec("spec.yaml")
    return client


def _read(result: dict, table: str) -> pl.DataFrame:
    return pl.read_parquet(result["tables"][table]["path"])


# -- pure math -----------------------------------------------------------------
def test_build_day_weights_normalized_with_spikes() -> None:
    cfg = {
        "_start": "2024-01-01",
        "_end": "2025-12-31",
        "weekly": {"Sat": 2.0, "Mon": 0.5},
        "yearly": {"peaks": [{"month": 11, "day": 29, "strength": 5.0, "width_days": 3}]},
        "events": [{"name": "x", "start": "2024-06-01", "end": "2024-06-05", "multiplier": 3.0}],
    }
    start, end = date(2024, 1, 1), date(2025, 12, 31)
    w = S.build_day_weights(start, end, cfg)
    assert abs(float(w.sum()) - 1.0) < 1e-9
    days = S._range_dates(start, end)
    med = float(np.median(w))
    bf = float(w[[i for i, d in enumerate(days) if d.month == 11 and 27 <= d.day <= 30]].mean())
    assert bf > 3 * med  # yearly peak present
    sat = w[[i for i, d in enumerate(days) if d.weekday() == 5]].mean()
    mon = w[[i for i, d in enumerate(days) if d.weekday() == 0]].mean()
    assert sat > 3 * mon  # weekly pattern (2.0 / 0.5)


def test_multiplier_and_calendar_features() -> None:
    m = S.multiplier_for(
        [date(2024, 1, 1), date(2025, 1, 1)],
        {"_start": "2024-01-01", "_end": "2025-12-31", "trend": {"annual_growth": 1.0}},
    )
    assert m[1] > m[0]  # trend grows year over year
    feats = S.calendar_features(
        [date(2025, 11, 29), date(2025, 3, 10)],
        ["day_of_week", "is_weekend", "quarter", "fiscal_quarter", "season"],
        fiscal_year_start_month=4,
    )
    assert feats["day_of_week"] == [6, 1]  # Sat, Mon (ISO)
    assert feats["is_weekend"] == [True, False]
    assert feats["quarter"] == [4, 1]
    assert feats["season"] == ["Autumn", "Spring"]


# -- generation ----------------------------------------------------------------
def test_seasonal_determinism(seasonal_project: ADPClient) -> None:
    r1 = seasonal_project.generate_data(rows=8000, seed=7, output_format="parquet", output_dir="a")
    r2 = seasonal_project.generate_data(rows=8000, seed=7, output_format="parquet", output_dir="b")
    for t in r1["tables"]:
        assert _read(r1, t).equals(_read(r2, t)), f"{t} not reproducible"


def test_volume_event_spike(seasonal_project: ADPClient) -> None:
    o = _read(seasonal_project.generate_data(rows=25000, seed=1, output_format="parquet"), "fact_orders")
    daily = (
        o.with_columns(pl.col("order_ts").dt.date().alias("d"))
        .group_by("d")
        .len()
        .sort("d")
    )
    med = float(daily["len"].median())
    bf = daily.filter(
        (pl.col("d") >= date(2024, 11, 28)) & (pl.col("d") <= date(2024, 11, 30))
    )["len"].mean()
    assert bf >= 3 * med  # 6x declared, allow sampling slack


def test_weekly_pattern(seasonal_project: ADPClient) -> None:
    o = _read(seasonal_project.generate_data(rows=25000, seed=2, output_format="parquet"), "fact_orders")
    wd = o.with_columns(pl.col("order_ts").dt.weekday().alias("wd")).group_by("wd").len()
    counts = dict(zip(wd["wd"].to_list(), wd["len"].to_list()))
    assert counts[6] > 2 * counts[1]  # Sat (2.5) >> Mon (0.5)


def test_trend_growth(seasonal_project: ADPClient) -> None:
    o = _read(seasonal_project.generate_data(rows=25000, seed=3, output_format="parquet"), "fact_orders")
    yr = o.with_columns(pl.col("order_ts").dt.year().alias("y")).group_by("y").len().sort("y")
    counts = dict(zip(yr["y"].to_list(), yr["len"].to_list()))
    assert counts[2025] > counts[2024]  # positive trend


def test_value_scaling(seasonal_project: ADPClient) -> None:
    o = _read(seasonal_project.generate_data(rows=25000, seed=4, output_format="parquet"), "fact_orders")
    by_year = (
        o.with_columns(pl.col("order_ts").dt.year().alias("y"))
        .group_by("y")
        .agg(pl.col("revenue").mean().alias("m"))
        .sort("y")
    )
    m = dict(zip(by_year["y"].to_list(), by_year["m"].to_list()))
    assert m[2025] > 1.3 * m[2024]  # revenue scaled up by the growth trend


def test_calendar_columns(seasonal_project: ADPClient) -> None:
    o = _read(seasonal_project.generate_data(rows=5000, seed=5, output_format="parquet"), "fact_orders")
    for part in ("order_ts_day_of_week", "order_ts_is_weekend", "order_ts_quarter", "order_ts_season"):
        assert part in o.columns
    chk = o.with_columns(
        [
            (pl.col("order_ts_day_of_week") == pl.col("order_ts").dt.weekday()).alias("dow_ok"),
            (pl.col("order_ts_quarter") == pl.col("order_ts").dt.quarter()).alias("q_ok"),
            (pl.col("order_ts_is_weekend") == (pl.col("order_ts").dt.weekday() >= 6)).alias("we_ok"),
        ]
    )
    assert chk["dow_ok"].all() and chk["q_ok"].all() and chk["we_ok"].all()
    assert set(o["order_ts_season"].unique().to_list()) <= {"Winter", "Spring", "Summer", "Autumn"}


def test_propagation_and_fk_integrity(seasonal_project: ADPClient) -> None:
    res = seasonal_project.generate_data(rows=12000, seed=6, output_format="parquet")
    o, p, s = _read(res, "fact_orders"), _read(res, "fact_payments"), _read(res, "fact_shipments")
    # per-row ordering: payment after inherited order ts; shipment after payment
    assert "parent_order_ts" in p.columns
    assert (p["payment_ts"] < p["parent_order_ts"]).sum() == 0
    assert (s["shipped_ts"] < s["parent_payment_ts"]).sum() == 0
    # FK integrity across the chain
    assert p.join(o.select("order_id"), on="order_id", how="anti").height == 0
    assert s.join(p.select("payment_id"), on="payment_id", how="anti").height == 0
    # inherited timestamps are a subset of the parent's (proves same-idx gather)
    parent_ts = set(o["order_ts"].to_list())
    assert set(p["parent_order_ts"].to_list()) <= parent_ts


def test_streaming_across_chunks(seasonal_project: ADPClient) -> None:
    from ai_data_platform.generator.engine import GenerationPlan, generate

    plan_dict = seasonal_project.build_plan(rows=3000, seed=9)
    plan_dict["chunk_rows"] = 200  # force many chunks
    plan = GenerationPlan.model_validate(plan_dict)
    out = Path(seasonal_project.root) / "streamed"
    generate(plan, out, output_format="parquet")
    o = pl.read_parquet(out / "fact_orders.parquet")
    p = pl.read_parquet(out / "fact_payments.parquet")
    assert len(o) == len(p) == 3000
    # inheritance + ordering survive chunk boundaries
    assert (p["payment_ts"] < p["parent_order_ts"]).sum() == 0
    assert set(p["parent_order_ts"].to_list()) <= set(o["order_ts"].to_list())


def test_report_and_preview_surfaces(seasonal_project: ADPClient) -> None:
    seasonal_project.generate_data(rows=25000, seed=8, output_format="parquet")
    rep = seasonal_project.seasonality_check()
    assert rep["seasonality_score"] >= 70
    assert "correlation" in rep["category_scores"]
    orders = next(t for t in rep["tables"] if t["table"] == "fact_orders")
    assert orders["anchor"] == "order_ts"
    assert any(x["child"] == "fact_payments" for x in rep["cross_table"])
    # daily CSV round-trips
    from ai_data_platform.quality.seasonality_report import seasonality_daily_csv

    csv = seasonality_daily_csv(rep)
    df = pl.read_csv(csv.encode())
    assert set(df.columns) >= {"table", "date", "observed_count", "expected_intensity"}
    # preview needs no data
    pv = seasonal_project.preview_seasonality("fact_orders")
    assert pv["anchor"] == "order_ts" and len(pv["curve"]) > 0


def test_non_seasonal_spec_unaffected(tmp_path: Path) -> None:
    """A spec with no seasonality/inherit generates identically across runs
    (inheritance machinery must add no RNG draw)."""
    plain = """
version: 1
tables:
  - name: t
    columns:
      - {name: id, type: uuid, primary_key: true}
      - {name: amount, type: float, mean: 100, std: 20}
      - {name: ts, type: datetime, start: 2024-01-01, end: 2025-01-01}
"""
    c = ADPClient(tmp_path)
    c.init("plain")
    (tmp_path / "spec.yaml").write_text(plain, encoding="utf-8")
    c.apply_spec("spec.yaml")
    r1 = c.generate_data(rows=1000, seed=42, output_format="parquet", output_dir="p1")
    r2 = c.generate_data(rows=1000, seed=42, output_format="parquet", output_dir="p2")
    assert pl.read_parquet(r1["tables"]["t"]["path"]).equals(
        pl.read_parquet(r2["tables"]["t"]["path"])
    )
