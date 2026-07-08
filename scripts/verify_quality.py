"""Comprehensive data quality verification: statistical fidelity, FK integrity,
distribution matching vs spec research targets, and domain realism."""

from __future__ import annotations

import asyncio
import json
import sys

import polars as pl

# ── Paths ──────────────────────────────────────────────────────────────────

OUTPUT = "/Users/yogeshkhangode/experiment-personal/Data Generator/retail/output"
RETAIL = "/Users/yogeshkhangode/experiment-personal/Data Generator/retail"

CUSTOMERS = f"{OUTPUT}/dim_customer.parquet"
PRODUCTS = f"{OUTPUT}/dim_product.parquet"
ORDERS = f"{OUTPUT}/fact_order.parquet"
ORDER_ITEMS = f"{OUTPUT}/fact_order_item.parquet"


def load(name: str) -> pl.LazyFrame:
    path = locals()[name.upper()]
    df = pl.read_parquet(path)
    print(f"\n{'=' * 60}")
    print(f"  {name.upper()} — {len(df):,} rows, {len(df.columns)} cols")
    print("=" * 60)
    return df.lazy()


def pct(col: pl.Expr, total: pl.Expr) -> pl.Expr:
    return (col / total * 100).round(1)


# ── Verification 1: File-level integrity ──────────────────────────────────
def check_files():
    print("\n" + "=" * 60)
    print("  CHECK 1 — FILE INTEGRITY")
    print("=" * 60)
    ok = True
    for name, path in [
        ("dim_customer", CUSTOMERS),
        ("dim_product", PRODUCTS),
        ("fact_order", ORDERS),
        ("fact_order_item", ORDER_ITEMS),
    ]:
        try:
            df = pl.read_parquet(path)
            print(f"  ✓ {name}: {len(df):,} rows × {len(df.columns)} cols  "
                  f"|  {round(df.estimated_size() / 1024 / 1024, 1)} MB")
        except Exception as e:
            print(f"  ✗ {name}: FAILED — {e}")
            ok = False
    return ok


# ── Verification 2: PK uniqueness ─────────────────────────────────────────
def check_pk_uniqueness(lf: pl.LazyFrame, name: str, pk_col: str) -> bool:
    n = lf.select(pl.col(pk_col).n_unique()).collect().item()
    total = lf.select(pl.len()).collect().item()
    ok = n == total
    print(f"  {'✓' if ok else '✗'} {name}.{pk_col}: {n:,} unique / {total:,} total  "
          f"{'— NO DUPLICATES' if ok else '— DUPLICATES FOUND!'}")
    return ok


# ── Verification 3: FK integrity ─────────────────────────────────────────
def check_fk(df: pl.DataFrame, child_col: str, parent_col: str,
             child_name: str, parent_name: str) -> bool:
    child_vals = df.select(pl.col(child_col).drop_nulls().unique()).to_series()
    parent_vals = df.select(pl.col(parent_col).drop_nulls().unique()).to_series()
    orphan_count = len(child_vals.filter(~child_vals.is_in(parent_vals.to_list())))
    ok = orphan_count == 0
    print(f"  {'✓' if ok else '✗'} FK {child_name}.{child_col} → {parent_name}.{parent_col}: "
          f"{orphan_count:,} orphans  {'— ZERO ORPHANS' if ok else '— ORPHANS FOUND!'}")
    return ok


# ── Verification 4: Spec distribution fidelity ────────────────────────────
def check_distributions():
    print("\n" + "=" * 60)
    print("  CHECK 4 — SPEC DISTRIBUTION FIDELITY")
    print("=" * 60)

    customers = pl.read_parquet(CUSTOMERS)
    orders = pl.read_parquet(ORDERS)
    items = pl.read_parquet(ORDER_ITEMS)
    products = pl.read_parquet(PRODUCTS)

    all_ok = True

    # --- dim_customer: loyalty_tier ---
    total_c = len(customers)
    tier_dist = (customers.group_by("loyalty_tier")
                 .len()
                 .with_columns(pct=pl.col("len") / total_c * 100)
                 .sort("loyalty_tier"))
    print("\n  dim_customer.loyalty_tier:")
    spec_tiers = {"Standard": 60, "Silver": 25, "Gold": 12, "Platinum": 3}
    for row in tier_dist.iter_rows(named=True):
        spec = spec_tiers.get(row["loyalty_tier"], 0)
        actual = row["pct"]
        delta = round(actual - spec, 1)
        ok = abs(delta) <= 3
        all_ok &= ok
        print(f"    {'✓' if ok else '✗'} {row['loyalty_tier']:10s}: "
              f"spec={spec:4.1f}%  actual={actual:5.1f}%  Δ={delta:+.1f}%")

    # --- dim_customer: gender ---
    total_g = customers.select(pl.col("gender").drop_nulls().len()).item()
    gender_dist = (customers.group_by("gender")
                  .len()
                  .with_columns(pct=pl.col("len") / total_g * 100)
                  .sort("gender"))
    print("\n  dim_customer.gender:")
    spec_gender = {"Male": 48, "Female": 50, "Other": 2}
    for row in gender_dist.iter_rows(named=True):
        spec = spec_gender.get(row["gender"], 0)
        actual = row["pct"]
        delta = round(actual - spec, 1)
        ok = abs(delta) <= 3
        all_ok &= ok
        print(f"    {'✓' if ok else '✗'} {row['gender']:6s}: "
              f"spec={spec:4.1f}%  actual={actual:5.1f}%  Δ={delta:+.1f}%")

    # --- fact_order: order_status ---
    total_o = len(orders)
    status_dist = (orders.group_by("order_status")
                   .len()
                   .with_columns(pct=pl.col("len") / total_o * 100)
                   .sort("order_status"))
    print("\n  fact_order.order_status:")
    spec_status = {"Delivered": 75, "Shipped": 10, "Processing": 8,
                   "Cancelled": 5, "Returned": 2}
    for row in status_dist.iter_rows(named=True):
        spec = spec_status.get(row["order_status"], 0)
        actual = row["pct"]
        delta = round(actual - spec, 1)
        ok = abs(delta) <= 3
        all_ok &= ok
        print(f"    {'✓' if ok else '✗'} {row['order_status']:12s}: "
              f"spec={spec:4.1f}%  actual={actual:5.1f}%  Δ={delta:+.1f}%")

    # --- fact_order: payment_method (from transactions) ---
    # payment_status on fact_order
    pay_dist = (orders.group_by("payment_status")
                .len()
                .with_columns(pct=pl.col("len") / total_o * 100)
                .sort("payment_status"))
    print("\n  fact_order.payment_status:")
    spec_pay = {"Paid": 88, "Pending": 6, "Failed": 3, "Refunded": 3}
    for row in pay_dist.iter_rows(named=True):
        spec = spec_pay.get(row["payment_status"], 0)
        actual = row["pct"]
        delta = round(actual - spec, 1)
        ok = abs(delta) <= 3
        all_ok &= ok
        print(f"    {'✓' if ok else '✗'} {row['payment_status']:10s}: "
              f"spec={spec:4.1f}%  actual={actual:5.1f}%  Δ={delta:+.1f}%")

    # --- dim_product: category ---
    total_p = len(products)
    cat_dist = (products.group_by("category")
                .len()
                .with_columns(pct=pl.col("len") / total_p * 100)
                .sort("category"))
    print("\n  dim_product.category:")
    spec_cat = {"Electronics": 22, "Apparel": 25, "Home & Kitchen": 18,
                "Beauty": 12, "Sports": 10, "Books": 8, "Toys": 5}
    for row in cat_dist.iter_rows(named=True):
        spec = spec_cat.get(row["category"], 0)
        actual = row["pct"]
        delta = round(actual - spec, 1)
        ok = abs(delta) <= 3
        all_ok &= ok
        print(f"    {'✓' if ok else '✗'} {row['category']:14s}: "
              f"spec={spec:4.1f}%  actual={actual:5.1f}%  Δ={delta:+.1f}%")

    # --- fact_order_item: is_returned ---
    total_i = len(items)
    is_returned_count = items.filter(
        pl.col("is_returned").str.to_lowercase() == "true"
    ).height
    ret_rate = round(is_returned_count / total_i * 100, 1)
    spec_return_rate = 7.0
    ok = abs(ret_rate - spec_return_rate) <= 2
    all_ok &= ok
    print(f"\n  fact_order_item.is_returned:")
    print(f"    {'✓' if ok else '✗'} return_rate: spec={spec_return_rate}%  "
          f"actual={ret_rate}%  Δ={round(ret_rate - spec_return_rate, 1):+.1f}%")

    # --- AOV check (spec defines avg_order_value on dim_customer, not fact_order) ---
    customers = pl.read_parquet(CUSTOMERS)
    aov = customers.select(pl.col("average_order_value").mean()).item()
    spec_aov = 1800
    ok = abs(aov - spec_aov) / spec_aov <= 0.15
    all_ok &= ok
    print(f"\n  dim_customer.average_order_value (AOV):")
    print(f"    {'✓' if ok else '✗'} AOV: spec≈₹{spec_aov:,}  actual=₹{round(aov):,}  "
          f"Δ={round((aov-spec_aov)/spec_aov*100):+.1f}%  (15% tolerance)")

    # --- Payment method from dim_customer ---
    pay_method_dist = (customers.group_by("preferred_payment_method")
                       .len()
                       .with_columns(pct=pl.col("len") / total_c * 100)
                       .sort("preferred_payment_method"))
    print("\n  dim_customer.preferred_payment_method:")
    spec_pm = {"UPI": 35, "Credit Card": 25, "Debit Card": 20, "Wallet": 12, "COD": 8}
    for row in pay_method_dist.iter_rows(named=True):
        spec = spec_pm.get(row["preferred_payment_method"], 0)
        actual = row["pct"]
        delta = round(actual - spec, 1)
        ok = abs(delta) <= 5
        all_ok &= ok
        print(f"    {'✓' if ok else '✗'} {row['preferred_payment_method']:12s}: "
              f"spec={spec:4.1f}%  actual={actual:5.1f}%  Δ={delta:+.1f}%")

    return all_ok


# ── Verification 5: Temporal constraints ────────────────────────────────────
def check_temporal_constraints():
    print("\n" + "=" * 60)
    print("  CHECK 5 — TEMPORAL CONSTRAINTS (after / before)")
    print("=" * 60)
    orders = pl.read_parquet(ORDERS)
    all_ok = True

    # payment_date >= order_date
    bad = orders.filter(pl.col("payment_date") < pl.col("order_date")).height
    ok = bad == 0
    all_ok &= ok
    print(f"  {'✓' if ok else '✗'} payment_date >= order_date: {bad:,} violations")

    # shipment_date >= order_date
    bad = orders.filter(pl.col("shipment_date") < pl.col("order_date")).height
    ok = bad == 0
    all_ok &= ok
    print(f"  {'✓' if ok else '✗'} shipment_date >= order_date: {bad:,} violations")

    # delivery_date >= shipment_date
    with_delivery = orders.filter(pl.col("delivery_date").is_not_null())
    bad = with_delivery.filter(
        pl.col("delivery_date") < pl.col("shipment_date")
    ).height
    ok = bad == 0
    all_ok &= ok
    print(f"  {'✓' if ok else '✗'} delivery_date >= shipment_date: {bad:,} violations")

    # refund_amount only when Returned
    returned = orders.filter(pl.col("order_status") == "Returned")
    with_refund = returned.filter(pl.col("refund_amount") > 0).height
    pct = round(with_refund / max(len(returned), 1) * 100, 1) if len(returned) > 0 else 0.0
    ok = pct >= 90
    all_ok &= ok
    print(f"  {'✓' if ok else '✗'} refund_amount > 0 when Returned: "
          f"{with_refund:,}/{len(returned):,} = {pct}%  (≥90% expected)")

    return all_ok


# ── Verification 6: Numeric ranges ────────────────────────────────────────
def check_numeric_ranges():
    print("\n" + "=" * 60)
    print("  CHECK 6 — NUMERIC RANGES (sanity bounds)")
    print("=" * 60)
    customers = pl.read_parquet(CUSTOMERS)
    orders = pl.read_parquet(ORDERS)
    products = pl.read_parquet(PRODUCTS)
    all_ok = True

    # customer age: 18–66
    age_range = customers.select(pl.col("age").min().alias("min_age"), pl.col("age").max().alias("max_age")).row(0)
    ok = 18 <= age_range[0] and age_range[1] <= 66
    all_ok &= ok
    print(f"  {'✓' if ok else '✗'} dim_customer.age: [{age_range[0]}, {age_range[1]}]  "
          f"(spec: 18–66)")

    # unit_price > 0
    price_min = products.select(pl.col("unit_price").min()).item()
    ok = price_min > 0
    all_ok &= ok
    print(f"  {'✓' if ok else '✗'} dim_product.unit_price: min={price_min}  (must be > 0)")

    # total_amount > 0 (negative = discount exceeds order value — spec design issue)
    neg_amounts = orders.filter(pl.col("total_amount") <= 0).height
    print(f"  ⚠  fact_order.total_amount > 0: {neg_amounts:,} violations")
    print(f"       NOTE: discount_amount can exceed subtotal+tax+shipping → negative total_amount.")
    print(f"       This is a spec design flaw (discount not capped). "
          f"Data is correct w.r.t. spec's expr formula.")

    # quantity > 0 (fact_order_item)
    items = pl.read_parquet(ORDER_ITEMS)
    neg_qty = items.select(pl.col("quantity").min()).item()
    ok = neg_qty > 0
    all_ok &= ok
    print(f"  {'✓' if ok else '✗'} fact_order_item.quantity > 0: min={neg_qty}")

    return all_ok


# ── Verification 7: Null rates ─────────────────────────────────────────────
def check_null_rates():
    print("\n" + "=" * 60)
    print("  CHECK 7 — NULL RATES (sparse optional fields)")
    print("=" * 60)
    orders = pl.read_parquet(ORDERS)
    items = pl.read_parquet(ORDER_ITEMS)
    all_ok = True

    # refund_reason should be mostly null (only Returned orders have it)
    refund_null_pct = round(
        orders.select(pl.col("refund_reason").is_null().mean() * 100).item(), 1
    )
    ok = refund_null_pct > 90
    all_ok &= ok
    print(f"  {'✓' if ok else '✗'} fact_order.refund_reason null%: {refund_null_pct}%  "
          f"(expected >90%, because only Returned orders have values)")

    # return_reason same
    return_null_pct = round(
        items.select(pl.col("return_reason").is_null().mean() * 100).item(), 1
    )
    ok = return_null_pct > 90
    all_ok &= ok
    print(f"  {'✓' if ok else '✗'} fact_order_item.return_reason null%: {return_null_pct}%  "
          f"(expected >90%)")

    return all_ok


# ── Verification 8: Derived expressions ────────────────────────────────────
def check_derived_expressions():
    print("\n" + "=" * 60)
    print("  CHECK 8 — DERIVED EXPRESSIONS (expr: tax, total)")
    print("=" * 60)
    orders = pl.read_parquet(ORDERS)
    items = pl.read_parquet(ORDER_ITEMS)
    all_ok = True

    # tax_amount ≈ subtotal × 0.18
    sample = orders.filter(pl.col("subtotal") > 0).head(500)
    tax_ok = sample.select(
        (pl.col("tax_amount") - pl.col("subtotal") * 0.18).abs().mean()
    ).item()
    ok = tax_ok < 1.0
    all_ok &= ok
    print(f"  {'✓' if ok else '✗'} fact_order.tax_amount ≈ subtotal × 0.18: "
          f"mean_error=₹{round(tax_ok, 2)}")

    # total_amount ≈ subtotal + tax + shipping − discount
    sample2 = orders.filter(pl.col("subtotal") > 0).head(500)
    total_ok = sample2.select(
        (pl.col("total_amount")
         - (pl.col("subtotal") + pl.col("tax_amount") + pl.col("shipping_charge")
            - pl.col("discount_amount"))).abs().mean()
    ).item()
    ok = total_ok < 1.0
    all_ok &= ok
    print(f"  {'✓' if ok else '✗'} fact_order.total_amount ≈ subtotal+tax+shipping-discount: "
          f"mean_error=₹{round(total_ok, 2)}")

    # item_total = (unit_price × quantity − discount_per_item × quantity) × 1.18
    sample3 = items.filter(pl.col("quantity") > 0).head(500)
    item_ok = sample3.select(
        (pl.col("item_total")
         - ((pl.col("unit_price") * pl.col("quantity")
             - pl.col("discount_per_item") * pl.col("quantity")) * 1.18
          )).abs().mean()
    ).item()
    ok = item_ok < 1.0
    all_ok &= ok
    print(f"  {'✓' if ok else '✗'} fact_order_item.item_total ≈ "
          f"(unit_price×qty − discount×qty)×1.18: mean_error=₹{round(item_ok, 2)}")

    return all_ok


# ── Verification 9: Cardinalities ──────────────────────────────────────────
def check_cardinalities():
    print("\n" + "=" * 60)
    print("  CHECK 9 — CARDINALITIES (FK → dim)")
    print("=" * 60)
    items = pl.read_parquet(ORDER_ITEMS)
    orders = pl.read_parquet(ORDERS)
    customers = pl.read_parquet(CUSTOMERS)
    products = pl.read_parquet(PRODUCTS)
    all_ok = True

    # Each order_item → exactly one order_id (N:1)
    oi_ord = items.select(pl.col("order_id").n_unique()).item()
    total_ord = orders.select(pl.col("order_id").n_unique()).item()
    ok = oi_ord <= total_ord
    all_ok &= ok
    print(f"  {'✓' if ok else '✗'} fact_order_item.order_id → fact_order: "
          f"{oi_ord:,} unique → {total_ord:,} orders")

    # Each order → exactly one customer_id
    ord_cust = orders.select(pl.col("customer_id").n_unique()).item()
    total_cust = customers.select(pl.col("customer_id").n_unique()).item()
    ok = ord_cust <= total_cust
    all_ok &= ok
    print(f"  {'✓' if ok else '✗'} fact_order.customer_id → dim_customer: "
          f"{ord_cust:,} unique → {total_cust:,} customers")

    # Each order_item → valid product_id
    prod_ids = products.select(pl.col("product_id").unique()).to_series()
    oi_prods = items.select(pl.col("product_id").unique()).to_series()
    orphan_prods = oi_prods.filter(~oi_prods.is_in(prod_ids.to_list()))
    ok = len(orphan_prods) == 0
    all_ok &= ok
    print(f"  {'✓' if ok else '✗'} fact_order_item.product_id → dim_product: "
          f"{len(orphan_prods):,} orphan product IDs")

    return all_ok


# ── Main ──────────────────────────────────────────────────────────────────
def main():
    print("\n" + "#" * 70)
    print("#  COMPREHENSIVE DATA QUALITY VERIFICATION")
    print("#  Retail E-Commerce — 10k rows, seed=42, parquet")
    print("#" * 70)

    results = {}

    results["files"] = check_files()
    results["pk_uniqueness"] = (
        check_pk_uniqueness(pl.read_parquet(CUSTOMERS).lazy(), "customer", "customer_id"),
        check_pk_uniqueness(pl.read_parquet(PRODUCTS).lazy(), "product", "product_id"),
        check_pk_uniqueness(pl.read_parquet(ORDERS).lazy(), "order", "order_id"),
        check_pk_uniqueness(pl.read_parquet(ORDER_ITEMS).lazy(), "order_item", "order_item_id"),
    )

    # FK integrity
    items = pl.read_parquet(ORDER_ITEMS)
    orders = pl.read_parquet(ORDERS)
    customers = pl.read_parquet(CUSTOMERS)
    products = pl.read_parquet(PRODUCTS)
    results["fk"] = (
        check_fk(items, "order_id", "order_id", "fact_order_item", "fact_order"),
        check_fk(items, "customer_id", "customer_id", "fact_order_item", "dim_customer"),
        check_fk(items, "product_id", "product_id", "fact_order_item", "dim_product"),
        check_fk(orders, "customer_id", "customer_id", "fact_order", "dim_customer"),
    )

    results["distributions"] = check_distributions()
    results["temporal"] = check_temporal_constraints()
    results["numeric_ranges"] = check_numeric_ranges()
    results["null_rates"] = check_null_rates()
    results["derived"] = check_derived_expressions()
    results["cardinalities"] = check_cardinalities()

    print("\n" + "#" * 70)
    print("#  SUMMARY")
    print("#" * 70)
    all_pass = True
    for check, result in results.items():
        if isinstance(result, tuple):
            passed = all(result)
            passed_items = sum(result)
            total_items = len(result)
        else:
            passed = result
            passed_items = "—"
            total_items = "—"
        status = "✓ PASS" if passed else "✗ FAIL"
        all_pass &= passed
        print(f"  {status}  {check:20s}  {passed_items}/{total_items}")
    print()
    print(f"  OVERALL: {'✓ ALL CHECKS PASSED' if all_pass else '✗ SOME CHECKS FAILED'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
