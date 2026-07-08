"""Declarative spec: generate with zero seed data (cold-start path)."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from ai_data_platform.core.exceptions import ConfigError
from ai_data_platform.sdk import ADPClient

SPEC = """
version: 1
tables:
  - name: dim_customer
    columns:
      - {name: customer_id, type: uuid, primary_key: true}
      - {name: gender, type: string, values: {Male: 48, Female: 50, Other: 2}}
      - {name: age, type: int, min: 18, max: 70}
      - {name: income, type: float, mean: 50000, std: 20000, min: 0}
      - {name: signup_date, type: date, start: 2022-01-01, end: 2026-01-01}
      - {name: referral_code, type: string, null_ratio: 0.7}
  - name: fact_transaction
    columns:
      - {name: transaction_id, type: uuid, primary_key: true}
      - {name: customer_id, type: uuid, references: dim_customer.customer_id}
      - {name: rating, type: int, values: {"5": 55, "4": 25, "3": 10, "2": 6, "1": 4}}
      - {name: payment_method, type: string, values: {UPI: 40, Card: 37, COD: 23}}
      - {name: amount, type: float, mean: 900, std: 700, min: 10}
"""


@pytest.fixture()
def spec_project(tmp_path: Path) -> ADPClient:
    client = ADPClient(tmp_path)
    client.init("spec-test")
    (tmp_path / "spec.yaml").write_text(SPEC, encoding="utf-8")
    return client


def test_apply_spec_registers_catalog(spec_project: ADPClient) -> None:
    result = spec_project.apply_spec("spec.yaml")
    assert result["tables"] == 2 and result["relationships"] == 1
    tables = {t["table"] for t in spec_project.list_tables()}
    assert tables == {"dim_customer", "fact_transaction"}
    cust = spec_project.get_table("dim_customer")
    assert [c["name"] for c in cust["columns"] if c["primary_key"]] == ["customer_id"]


def test_generate_from_spec_no_seed_data(spec_project: ADPClient) -> None:
    spec_project.apply_spec("spec.yaml")
    result = spec_project.generate_data(rows=3000, output_format="parquet")
    c = pl.read_parquet(result["tables"]["dim_customer"]["path"])
    t = pl.read_parquet(result["tables"]["fact_transaction"]["path"])
    assert len(c) == len(t) == 3000
    # FK integrity with zero seed rows
    orphans = t.join(c.select("customer_id"), on="customer_id", how="anti")
    assert len(orphans) == 0
    # declared weights respected (±4pp at n=3000)
    upi = (t["payment_method"] == "UPI").sum() / len(t) * 100
    assert abs(upi - 40) < 4
    five = (t["rating"] == 5).sum() / len(t) * 100
    assert abs(five - 55) < 4
    assert t["rating"].dtype == pl.Int64
    # declared sparsity
    nullr = c["referral_code"].null_count() / len(c)
    assert 0.6 < nullr < 0.8
    # numeric range respected
    assert int(c["age"].min()) >= 18 and int(c["age"].max()) <= 70


JOINS_DEPS_SPEC = """
version: 1
tables:
  - name: customer
    columns:
      - {name: customer_id, type: uuid, primary_key: true}
      - {name: segment, type: string, values: {a: 60, b: 40}}
  - name: kyc
    columns:
      - {name: kyc_id, type: uuid, primary_key: true}
      - {name: customer_id, type: uuid}
  - name: txn
    columns:
      - {name: txn_id, type: uuid, primary_key: true}
      - {name: customer_id, type: uuid}
      - {name: order_date, type: datetime, start: 2025-01-01, end: 2025-12-31}
      - name: payment_date
        type: datetime
        start: 2025-01-01
        end: 2025-12-31
        after: {column: order_date, min_minutes: 1, max_minutes: 60}
      - {name: qty, type: int, min: 1, max: 5}
      - {name: price, type: float, mean: 100, std: 30, min: 1}
      - {name: total, type: float, expr: "price * qty"}
      - {name: status, type: string, values: {done: 90, returned: 10}}
      - name: refund_reason
        type: string
        values: {damaged: 50, other: 50}
        null_unless: "status = 'returned'"
joins:
  - left: customer.customer_id
    right: txn.customer_id
    relationship: one_to_many
  - left: kyc.customer_id
    right: customer.customer_id
    relationship: one_to_one
"""


def test_joins_and_dependencies(tmp_path) -> None:  # type: ignore[no-untyped-def]
    client = ADPClient(tmp_path)
    client.init("joins-test")
    (tmp_path / "spec.yaml").write_text(JOINS_DEPS_SPEC, encoding="utf-8")
    result = client.apply_spec("spec.yaml")
    assert result["relationships"] == 2
    gen = client.generate_data(rows=2000, output_format="parquet")
    c = pl.read_parquet(gen["tables"]["customer"]["path"])
    k = pl.read_parquet(gen["tables"]["kyc"]["path"])
    t = pl.read_parquet(gen["tables"]["txn"]["path"])
    # one_to_one: FK values unique and a subset of parent keys
    assert k["customer_id"].n_unique() == len(k)
    assert len(k.join(c.select("customer_id"), on="customer_id", how="anti")) == 0
    # one_to_many: zero orphans, keys reused
    assert len(t.join(c.select("customer_id"), on="customer_id", how="anti")) == 0
    # temporal dependency holds for every row
    assert int((t["payment_date"] < t["order_date"]).sum()) == 0
    # arithmetic dependency exact
    assert float((t["price"] * t["qty"] - t["total"]).abs().max()) < 1e-9
    # conditional nullability
    returned = t.filter(pl.col("status") == "returned")
    others = t.filter(pl.col("status") != "returned")
    assert returned["refund_reason"].null_count() == 0
    assert others["refund_reason"].drop_nulls().len() == 0


CUBE_STYLE_SPEC = """
version: 1
tables:
  - name: device
    joins:
      - name: battery
        relationship: one_to_many
        sql: "{TABLE.device_id} = {battery.device_id}"
      - name: warranty
        relationship: one_to_one
        sql: "{TABLE.device_id} = {warranty.device_id}"
    columns:
      - {name: device_id, type: uuid, primary_key: true}
      - {name: country, type: string, values: {India: 80, UAE: 20}}
      - name: city
        type: string
        values_by:
          column: country
          mapping:
            India: {Mumbai: 60, Pune: 40}
            UAE: {Dubai: 100}
  - name: battery
    columns:
      - {name: battery_id, type: uuid, primary_key: true}
      - {name: device_id, type: uuid}
      - {name: charge_pct, type: int, min: 0, max: 100}
  - name: warranty
    columns:
      - {name: warranty_id, type: uuid, primary_key: true}
      - {name: device_id, type: uuid}
"""


def test_cube_style_joins_and_hierarchy(tmp_path) -> None:  # type: ignore[no-untyped-def]
    client = ADPClient(tmp_path)
    client.init("cube-joins")
    (tmp_path / "spec.yaml").write_text(CUBE_STYLE_SPEC, encoding="utf-8")
    result = client.apply_spec("spec.yaml")
    assert result["relationships"] == 2
    gen = client.generate_data(rows=1500, output_format="parquet")
    d = pl.read_parquet(gen["tables"]["device"]["path"])
    b = pl.read_parquet(gen["tables"]["battery"]["path"])
    w = pl.read_parquet(gen["tables"]["warranty"]["path"])
    # one_to_many via cube-style sql: battery holds FK, zero orphans
    assert len(b.join(d.select("device_id"), on="device_id", how="anti")) == 0
    # one_to_one via cube-style sql: warranty FK unique
    assert w["device_id"].n_unique() == len(w)
    # hierarchical values_by: city consistent with country in every row
    for country, city in zip(d["country"], d["city"]):
        if country == "UAE":
            assert city == "Dubai"
        else:
            assert city in ("Mumbai", "Pune")


def test_one_to_one_child_larger_than_parent_fails(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """1:1 requires child rows <= parent rows — asserted via distinct plans."""
    from ai_data_platform.core.exceptions import GenerationError
    from ai_data_platform.generator.engine import GenerationPlan, generate

    client = ADPClient(tmp_path)
    client.init("o2o-fail")
    (tmp_path / "spec.yaml").write_text(JOINS_DEPS_SPEC, encoding="utf-8")
    client.apply_spec("spec.yaml")
    plan = GenerationPlan.model_validate(client.build_plan(rows=100))
    for tp in plan.tables:
        if tp.name == "kyc":
            tp.rows = 500  # more kyc rows than customers
    with pytest.raises(GenerationError):
        generate(plan, tmp_path / "out", output_format="parquet")


def test_per_table_row_counts(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """20 products / 200 customers / 5000 transactions in one run, FK-safe."""
    client = ADPClient(tmp_path)
    client.init("scenario")
    (tmp_path / "spec.yaml").write_text(
        """
version: 1
tables:
  - name: products
    rows: 20
    columns:
      - {name: product_id, type: uuid, primary_key: true}
      - {name: category, type: string, values: {a: 50, b: 50}}
  - name: customers
    rows: 200
    columns:
      - {name: customer_id, type: uuid, primary_key: true}
  - name: transactions
    rows: 5000
    joins:
      - name: products
        relationship: many_to_one
        sql: "{TABLE.product_id} = {products.product_id}"
      - name: customers
        relationship: many_to_one
        sql: "{TABLE.customer_id} = {customers.customer_id}"
    columns:
      - {name: txn_id, type: uuid, primary_key: true}
      - {name: product_id, type: uuid}
      - {name: customer_id, type: uuid}
""",
        encoding="utf-8",
    )
    client.apply_spec("spec.yaml")
    gen = client.generate_data(output_format="parquet")  # spec rows apply
    p = pl.read_parquet(gen["tables"]["products"]["path"])
    c = pl.read_parquet(gen["tables"]["customers"]["path"])
    t = pl.read_parquet(gen["tables"]["transactions"]["path"])
    assert (len(p), len(c), len(t)) == (20, 200, 5000)
    # same products reused across many transactions, zero orphans
    assert t["product_id"].n_unique() == 20
    assert len(t.join(p.select("product_id"), on="product_id", how="anti")) == 0
    assert len(t.join(c.select("customer_id"), on="customer_id", how="anti")) == 0
    # explicit override beats spec rows
    gen2 = client.generate_data(rows_per_table={"transactions": 300}, output_dir="o2")
    t2 = pl.read_parquet(gen2["tables"]["transactions"]["path"])
    assert len(t2) == 300


def test_format_template_sampler(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import re

    client = ADPClient(tmp_path)
    client.init("fmt")
    (tmp_path / "spec.yaml").write_text(
        """
version: 1
tables:
  - name: orders
    columns:
      - {name: order_id, type: int, primary_key: true}
      - {name: order_number, type: string, format: "ORD-2025-######"}
      - {name: tracking, type: string, format: "??-#########"}
""",
        encoding="utf-8",
    )
    client.apply_spec("spec.yaml")
    gen = client.generate_data(rows=300, output_format="parquet")
    df = pl.read_parquet(gen["tables"]["orders"]["path"])
    assert all(re.fullmatch(r"ORD-2025-\d{6}", v) for v in df["order_number"])
    assert all(re.fullmatch(r"[A-Z]{2}-\d{9}", v) for v in df["tracking"])


def test_spec_bad_reference_rejected(spec_project: ADPClient) -> None:
    (spec_project.root / "bad.yaml").write_text(
        """
version: 1
tables:
  - name: child
    columns:
      - {name: id, type: int, primary_key: true}
      - {name: ghost_id, type: int, references: ghost.id}
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        spec_project.apply_spec("bad.yaml")


def test_spec_invalid_yaml_rejected(spec_project: ADPClient) -> None:
    (spec_project.root / "broken.yaml").write_text("tables: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError):
        spec_project.apply_spec("broken.yaml")
