"""Retail e-commerce seed dataset: customers, products, orders, transactions.

Realistic shapes: seasonal order volume, lognormal amounts, weighted categories,
payment-method mix, FK chain customers/products -> orders -> transactions.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

N_CUSTOMERS = 2_000
N_PRODUCTS = 300
N_ORDERS = 12_000
SEED = 11


def main() -> None:
    rng = np.random.default_rng(SEED)
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)

    # -- customers -----------------------------------------------------------
    cities = ["Pune", "Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad", "Kolkata"]
    pl.DataFrame(
        {
            "customer_id": np.arange(1, N_CUSTOMERS + 1),
            "full_name": [f"Customer {i}" for i in range(1, N_CUSTOMERS + 1)],
            "email": [f"customer{i}@example.com" for i in range(1, N_CUSTOMERS + 1)],
            "phone": [f"+91-98{rng.integers(10000000, 99999999)}" for _ in range(N_CUSTOMERS)],
            "city": rng.choice(cities, N_CUSTOMERS, p=[0.2, 0.25, 0.15, 0.2, 0.08, 0.07, 0.05]),
            "segment": rng.choice(["regular", "premium", "vip"], N_CUSTOMERS, p=[0.7, 0.25, 0.05]),
            "signup_date": [
                f"{y}-{m:02d}-{d:02d}"
                for y, m, d in zip(
                    rng.integers(2022, 2026, N_CUSTOMERS),
                    rng.integers(1, 13, N_CUSTOMERS),
                    rng.integers(1, 28, N_CUSTOMERS),
                )
            ],
            "is_active": rng.random(N_CUSTOMERS) < 0.85,
        }
    ).write_csv(out / "customers.csv")

    # -- products -----------------------------------------------------------
    categories = ["electronics", "apparel", "home", "beauty", "sports", "books", "grocery"]
    cat = rng.choice(categories, N_PRODUCTS, p=[0.15, 0.25, 0.15, 0.1, 0.1, 0.1, 0.15])
    base_price = {
        "electronics": 8000,
        "apparel": 1200,
        "home": 2500,
        "beauty": 600,
        "sports": 1800,
        "books": 400,
        "grocery": 250,
    }
    price = np.array([rng.lognormal(np.log(base_price[c]), 0.5) for c in cat]).round(2)
    pl.DataFrame(
        {
            "product_id": np.arange(1, N_PRODUCTS + 1),
            "product_name": [f"Product {i}" for i in range(1, N_PRODUCTS + 1)],
            "category": cat,
            "unit_price": price,
            "stock_quantity": rng.integers(0, 500, N_PRODUCTS),
            "is_discontinued": rng.random(N_PRODUCTS) < 0.05,
        }
    ).write_csv(out / "products.csv")

    # -- orders (seasonal: q4 heavy) ------------------------------------------
    month_p = np.array([6, 5, 6, 6, 7, 7, 7, 8, 8, 10, 14, 16], dtype=float)
    month_p /= month_p.sum()
    months = rng.choice(np.arange(1, 13), N_ORDERS, p=month_p)
    days = rng.integers(1, 28, N_ORDERS)
    product_idx = rng.zipf(1.3, N_ORDERS) % N_PRODUCTS  # popularity skew
    product_ids = product_idx + 1
    qty = rng.poisson(1.4, N_ORDERS) + 1
    amounts = (price[product_idx] * qty * rng.uniform(0.9, 1.05, N_ORDERS)).round(2)
    pl.DataFrame(
        {
            "order_id": np.arange(1, N_ORDERS + 1),
            "customer_id": (rng.zipf(1.5, N_ORDERS) % N_CUSTOMERS) + 1,  # repeat buyers
            "product_id": product_ids,
            "order_date": [f"2025-{m:02d}-{d:02d}" for m, d in zip(months, days)],
            "quantity": qty,
            "total_amount": amounts,
            "channel": rng.choice(["web", "mobile_app", "store"], N_ORDERS, p=[0.45, 0.4, 0.15]),
            "status": rng.choice(
                ["delivered", "shipped", "processing", "cancelled", "returned"],
                N_ORDERS,
                p=[0.72, 0.1, 0.08, 0.06, 0.04],
            ),
        }
    ).write_csv(out / "orders.csv")

    # -- transactions (1 per non-cancelled order, minor failures) ---------------
    ok = rng.random(N_ORDERS) > 0.06
    order_ids = np.arange(1, N_ORDERS + 1)[ok]
    n_tx = len(order_ids)
    pl.DataFrame(
        {
            "transaction_id": np.arange(1, n_tx + 1),
            "order_id": order_ids,
            "payment_method": rng.choice(
                ["upi", "credit_card", "debit_card", "cod", "wallet"],
                n_tx,
                p=[0.4, 0.2, 0.15, 0.15, 0.1],
            ),
            "amount": amounts[ok],
            "transaction_date": np.array([f"2025-{m:02d}-{d:02d}" for m, d in zip(months, days)])[
                ok
            ],
            "tx_status": rng.choice(["success", "failed", "refunded"], n_tx, p=[0.93, 0.04, 0.03]),
        }
    ).write_csv(out / "transactions.csv")

    print(
        f"wrote customers({N_CUSTOMERS}) products({N_PRODUCTS}) "
        f"orders({N_ORDERS}) transactions({n_tx}) -> {out}"
    )


if __name__ == "__main__":
    main()
