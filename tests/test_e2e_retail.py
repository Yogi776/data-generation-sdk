"""End-to-end retail e-commerce regression: 4-table FK chain, fidelity, determinism.

Mirrors examples/retail-ecommerce. Guards the production-readiness claims:
FK integrity across a 3-level chain, moment-matched numeric fidelity,
categorical fidelity (TVD), no source-value leakage, seeded determinism.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from ai_data_platform.config import SourceConfig
from ai_data_platform.sdk import ADPClient

TABLES = ["customers", "products", "orders", "transactions"]


@pytest.fixture(scope="module")
def retail_project(tmp_path_factory: pytest.TempPathFactory) -> ADPClient:
    root = tmp_path_factory.mktemp("retail")
    data = root / "data"
    data.mkdir()
    rng = np.random.default_rng(11)
    n_cust, n_prod, n_ord = 500, 80, 3000

    pl.DataFrame(
        {
            "customer_id": np.arange(1, n_cust + 1),
            "full_name": [f"Customer {i}" for i in range(n_cust)],
            "email": [f"c{i}@example.com" for i in range(n_cust)],
            "city": rng.choice(["Pune", "Mumbai", "Delhi"], n_cust, p=[0.3, 0.4, 0.3]),
            "segment": rng.choice(["regular", "premium", "vip"], n_cust, p=[0.7, 0.25, 0.05]),
        }
    ).write_csv(data / "customers.csv")
    price = np.round(rng.lognormal(7.0, 0.8, n_prod), 2)
    pl.DataFrame(
        {
            "product_id": np.arange(1, n_prod + 1),
            "product_name": [f"Product {i}" for i in range(n_prod)],
            "category": rng.choice(["electronics", "apparel", "home"], n_prod),
            "unit_price": price,
        }
    ).write_csv(data / "products.csv")
    prod_idx = rng.integers(0, n_prod, n_ord)
    qty = rng.poisson(1.5, n_ord) + 1
    amounts = np.round(price[prod_idx] * qty, 2)
    pl.DataFrame(
        {
            "order_id": np.arange(1, n_ord + 1),
            "customer_id": rng.integers(1, n_cust + 1, n_ord),
            "product_id": prod_idx + 1,
            "quantity": qty,
            "total_amount": amounts,
            "status": rng.choice(
                ["delivered", "cancelled", "returned"], n_ord, p=[0.85, 0.1, 0.05]
            ),
        }
    ).write_csv(data / "orders.csv")
    ok = rng.random(n_ord) > 0.05
    pl.DataFrame(
        {
            "transaction_id": np.arange(1, int(ok.sum()) + 1),
            "order_id": np.arange(1, n_ord + 1)[ok],
            "payment_method": rng.choice(["upi", "card", "cod"], int(ok.sum())),
            "amount": amounts[ok],
        }
    ).write_csv(data / "transactions.csv")

    client = ADPClient(root)
    client.init("retail-e2e")
    client.add_source(SourceConfig(name="shop", type="csv", path=str(data)))
    client.scan()
    client.profile(sample_rows=5000)
    return client


@pytest.fixture(scope="module")
def generated(retail_project: ADPClient) -> dict[str, pl.DataFrame]:
    result = retail_project.generate_data(rows=5000, output_format="parquet")
    return {t: pl.read_parquet(result["tables"][t]["path"]) for t in TABLES}


def test_all_tables_generated(generated: dict[str, pl.DataFrame]) -> None:
    for t in TABLES:
        assert len(generated[t]) == 5000


def test_fk_chain_zero_orphans(generated: dict[str, pl.DataFrame]) -> None:
    pairs = [
        ("orders", "customer_id", "customers", "customer_id"),
        ("orders", "product_id", "products", "product_id"),
        ("transactions", "order_id", "orders", "order_id"),
    ]
    for ct, cc, pt, pc in pairs:
        orphans = generated[ct].join(
            generated[pt].select(pl.col(pc)), left_on=cc, right_on=pc, how="anti"
        )
        assert len(orphans) == 0, f"{ct}.{cc} has {len(orphans)} orphans"


def test_numeric_fidelity_moment_matched(
    retail_project: ADPClient, generated: dict[str, pl.DataFrame]
) -> None:
    src = pl.read_csv(Path(retail_project.root) / "data" / "orders.csv")
    for col in ("total_amount", "quantity"):
        sm, gm = float(src[col].mean()), float(generated["orders"][col].mean())
        ss, gs = float(src[col].std()), float(generated["orders"][col].std())
        assert abs(gm - sm) / sm < 0.2, f"{col} mean drift"
        assert abs(gs - ss) / max(ss, 1e-9) < 0.4, f"{col} std drift"


def test_categorical_fidelity_tvd(
    retail_project: ADPClient, generated: dict[str, pl.DataFrame]
) -> None:
    src = pl.read_csv(Path(retail_project.root) / "data" / "orders.csv")
    s = src["status"].value_counts(normalize=True).rename({"status": "v"})
    g = (
        generated["orders"]["status"]
        .cast(pl.String)
        .value_counts(normalize=True)
        .rename({"status": "v"})
    )
    j = s.join(g, on="v", how="full", coalesce=True).fill_null(0)
    tvd = 0.5 * float((j["proportion"] - j["proportion_right"]).abs().sum())
    assert tvd < 0.06, f"status TVD {tvd}"


def test_no_source_values_copied(
    retail_project: ADPClient, generated: dict[str, pl.DataFrame]
) -> None:
    src = pl.read_csv(Path(retail_project.root) / "data" / "customers.csv")
    leak = generated["customers"].join(src.select("email"), on="email", how="semi")
    assert len(leak) == 0


def test_quality_score_production_grade(
    retail_project: ADPClient, generated: dict[str, pl.DataFrame]
) -> None:
    report = retail_project.quality_check()
    assert report["quality_score"] >= 95, report["category_scores"]


def test_determinism_four_tables(retail_project: ADPClient) -> None:
    r1 = retail_project.generate_data(rows=500, seed=7, output_format="csv", output_dir="da")
    r2 = retail_project.generate_data(rows=500, seed=7, output_format="csv", output_dir="db")
    for t in TABLES:
        a = pl.read_csv(r1["tables"][t]["path"])
        b = pl.read_csv(r2["tables"][t]["path"])
        assert a.equals(b), f"{t} not deterministic"
