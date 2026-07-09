"""Seed CSVs for sales-performance profiling: 3 calendar years of retail activity.

Run:  python make_data.py
Writes: data/customers.csv, products.csv, orders.csv, transactions.csv
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl

SEED = 11
START = date(2023, 1, 1)
END = date(2025, 12, 31)
N_CUSTOMERS = 2_500
N_PRODUCTS = 400
N_ORDERS = 18_000


def _seasonal_weight(d: date) -> float:
    """Retail-ish rhythm: weekends, Q4 peak, festival window."""
    w = 1.0
    if d.weekday() >= 5:
        w *= 1.35
    if d.month in (11, 12):
        w *= 1.8
    elif d.month == 10 and 15 <= d.day <= 25:
        w *= 1.5
    elif d.month in (6, 7):
        w *= 0.85
    return w


def _sample_order_dates(rng: np.random.Generator, n: int) -> list[date]:
    days = (END - START).days + 1
    weights = np.array(
        [_seasonal_weight(START + timedelta(days=i)) for i in range(days)], dtype=np.float64
    )
    weights /= weights.sum()
    offsets = rng.choice(days, size=n, p=weights)
    return [START + timedelta(days=int(i)) for i in offsets]


def main() -> None:
    rng = np.random.default_rng(SEED)
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)

    cities = ["Mumbai", "Delhi", "Bangalore", "Pune", "Chennai", "Hyderabad", "Kolkata"]
    regions = ["West", "North", "South", "East"]
    channels = ["web", "mobile", "marketplace"]
    categories = ["electronics", "apparel", "home", "beauty", "grocery"]
    statuses = ["delivered", "cancelled", "returned"]
    status_p = [0.82, 0.12, 0.06]
    payments = ["upi", "card", "cod", "wallet"]
    pay_p = [0.42, 0.28, 0.18, 0.12]

    pl.DataFrame(
        {
            "customer_id": np.arange(1, N_CUSTOMERS + 1),
            "full_name": [f"Customer {i}" for i in range(1, N_CUSTOMERS + 1)],
            "email": [f"c{i}@example.com" for i in range(1, N_CUSTOMERS + 1)],
            "city": rng.choice(cities, N_CUSTOMERS, p=[0.22, 0.2, 0.18, 0.12, 0.1, 0.1, 0.08]),
            "segment": rng.choice(["regular", "premium", "vip"], N_CUSTOMERS, p=[0.68, 0.27, 0.05]),
            "signup_date": [
                (START + timedelta(days=int(d))).isoformat()
                for d in rng.integers(0, 900, N_CUSTOMERS)
            ],
        }
    ).write_csv(out / "customers.csv")

    unit_price = np.round(rng.lognormal(6.8, 0.75, N_PRODUCTS), 2)
    pl.DataFrame(
        {
            "product_id": np.arange(1, N_PRODUCTS + 1),
            "product_name": [f"Product {i}" for i in range(1, N_PRODUCTS + 1)],
            "category": rng.choice(categories, N_PRODUCTS, p=[0.28, 0.26, 0.2, 0.14, 0.12]),
            "unit_price": unit_price,
        }
    ).write_csv(out / "products.csv")

    order_dates = _sample_order_dates(rng, N_ORDERS)
    prod_idx = rng.integers(0, N_PRODUCTS, N_ORDERS)
    qty = rng.poisson(1.4, N_ORDERS) + 1
    amounts = np.round(unit_price[prod_idx] * qty, 2)
    status = rng.choice(statuses, N_ORDERS, p=status_p)

    pl.DataFrame(
        {
            "order_id": np.arange(1, N_ORDERS + 1),
            "customer_id": rng.integers(1, N_CUSTOMERS + 1, N_ORDERS),
            "product_id": prod_idx + 1,
            "order_date": [d.isoformat() for d in order_dates],
            "region": rng.choice(regions, N_ORDERS, p=[0.3, 0.28, 0.27, 0.15]),
            "channel": rng.choice(channels, N_ORDERS, p=[0.45, 0.35, 0.2]),
            "quantity": qty,
            "total_amount": amounts,
            "status": status,
        }
    ).write_csv(out / "orders.csv")

    paid_mask = status != "cancelled"
    n_txn = int(paid_mask.sum())
    txn_order_ids = np.arange(1, N_ORDERS + 1)[paid_mask]
    txn_amounts = amounts[paid_mask]
    txn_dates = [order_dates[i] for i, ok in enumerate(paid_mask) if ok]

    pl.DataFrame(
        {
            "transaction_id": np.arange(1, n_txn + 1),
            "order_id": txn_order_ids,
            "payment_method": rng.choice(payments, n_txn, p=pay_p),
            "amount": txn_amounts,
            "transaction_date": [d.isoformat() for d in txn_dates],
        }
    ).write_csv(out / "transactions.csv")

    print(f"Wrote seed data to {out}/ ({START} → {END})")
    print(f"  customers={N_CUSTOMERS:,}  products={N_PRODUCTS:,}  orders={N_ORDERS:,}  transactions={n_txn:,}")


if __name__ == "__main__":
    main()
