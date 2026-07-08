"""Generate the example shop dataset (customers + orders CSVs)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl


def main() -> None:
    rng = np.random.default_rng(7)
    n_cust, n_ord = 500, 5000
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)

    pl.DataFrame(
        {
            "customer_id": np.arange(1, n_cust + 1),
            "full_name": [f"Customer {i}" for i in range(1, n_cust + 1)],
            "email": [f"customer{i}@example.com" for i in range(1, n_cust + 1)],
            "city": rng.choice(["Pune", "Mumbai", "Delhi", "Bangalore", "Chennai"], n_cust),
            "segment": rng.choice(["retail", "wholesale", "online"], n_cust, p=[0.5, 0.2, 0.3]),
        }
    ).write_csv(out / "customers.csv")

    months = rng.integers(1, 13, n_ord)
    days = rng.integers(1, 28, n_ord)
    pl.DataFrame(
        {
            "order_id": np.arange(1, n_ord + 1),
            "customer_id": rng.integers(1, n_cust + 1, n_ord),
            "order_date": [f"2025-{m:02d}-{d:02d}" for m, d in zip(months, days)],
            "total_amount": np.round(rng.lognormal(4.5, 0.6, n_ord), 2),
            "quantity": rng.poisson(2, n_ord) + 1,
            "status": rng.choice(["completed", "pending", "cancelled"], n_ord, p=[0.8, 0.15, 0.05]),
        }
    ).write_csv(out / "orders.csv")
    print(f"wrote {out}/customers.csv ({n_cust}) and {out}/orders.csv ({n_ord})")


if __name__ == "__main__":
    main()
