"""Seed data for the dim_customer / fact_transaction scenario.

Implements the user's production-style spec: 48-column customer dimension,
50-column transaction fact, with the specified target distributions
(gender 48/50/2, segment 55/35/10, UPI 40%, delivered 82%, 5-star 55%,
coupon 35%, fraud ~0.5%, fulfillment 70/20/10, …).

The generator then LEARNS these distributions from the seed via `adp profile`
and reproduces them at any volume.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl

N_CUSTOMERS = 2_000
N_TX = 12_000
SEED = 42


def uuids(rng: np.random.Generator, n: int) -> list[str]:
    return [str(uuid.UUID(bytes=rng.bytes(16), version=4)) for _ in range(n)]


def dates(rng: np.random.Generator, n: int, start: str, end: str) -> np.ndarray:
    s = datetime.fromisoformat(start)
    span = int((datetime.fromisoformat(end) - s).total_seconds())
    return np.array([s + timedelta(seconds=int(x)) for x in rng.integers(0, span, n)])


def main() -> None:
    rng = np.random.default_rng(SEED)
    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)

    # ---------------- dim_customer (48 columns) ----------------
    n = N_CUSTOMERS
    customer_ids = uuids(rng, n)
    first = rng.choice(
        [
            "Aarav",
            "Priya",
            "Rahul",
            "Ananya",
            "Vikram",
            "Sara",
            "Kabir",
            "Meera",
            "Arjun",
            "Zoya",
            "Dev",
            "Isha",
        ],
        n,
    )
    last = rng.choice(
        [
            "Sharma",
            "Patel",
            "Singh",
            "Khan",
            "Gupta",
            "Rao",
            "Iyer",
            "Das",
            "Mehta",
            "Nair",
            "Joshi",
            "Bose",
        ],
        n,
    )
    dob = dates(rng, n, "1960-01-01", "2006-12-31")
    signup = dates(rng, n, "2020-01-01", "2026-06-01")
    total_orders = (rng.lognormal(1.2, 0.9, n)).astype(int) + 1
    aov = np.round(rng.lognormal(7.0, 0.5, n), 2)
    total_spent = np.round(total_orders * aov * rng.uniform(0.9, 1.1, n), 2)
    first_purchase = [s + timedelta(days=int(d)) for s, d in zip(signup, rng.integers(0, 60, n))]
    last_purchase = [
        f + timedelta(days=int(d)) for f, d in zip(first_purchase, rng.integers(0, 700, n))
    ]
    states = [
        "Maharashtra",
        "Karnataka",
        "Delhi",
        "Tamil Nadu",
        "Telangana",
        "Gujarat",
        "West Bengal",
    ]
    cities = {
        "Maharashtra": ["Mumbai", "Pune", "Nagpur"],
        "Karnataka": ["Bangalore", "Mysore"],
        "Delhi": ["New Delhi"],
        "Tamil Nadu": ["Chennai", "Coimbatore"],
        "Telangana": ["Hyderabad"],
        "Gujarat": ["Ahmedabad", "Surat"],
        "West Bengal": ["Kolkata"],
    }
    st = rng.choice(states, n, p=[0.24, 0.18, 0.12, 0.14, 0.12, 0.12, 0.08])
    city = np.array([cities[s][rng.integers(0, len(cities[s]))] for s in st])

    dim_customer = pl.DataFrame(
        {
            "customer_id": customer_ids,
            "customer_number": [f"CUST-{100000 + i}" for i in range(n)],
            "first_name": first,
            "last_name": last,
            "full_name": [f"{a} {b}" for a, b in zip(first, last)],
            "gender": rng.choice(["Male", "Female", "Other"], n, p=[0.48, 0.50, 0.02]),
            "date_of_birth": [d.date().isoformat() for d in dob],
            "age": [(2026 - d.year) for d in dob],
            "email": [
                f"{a.lower()}.{b.lower()}{i}@example.com"
                for i, (a, b) in enumerate(zip(first, last))
            ],
            "phone_number": [f"+91-9{rng.integers(100000000, 999999999)}" for _ in range(n)],
            "alternate_phone": [
                f"+91-8{rng.integers(100000000, 999999999)}" if rng.random() < 0.4 else None
                for _ in range(n)
            ],
            "customer_type": rng.choice(["New", "Returning", "VIP"], n, p=[0.70, 0.20, 0.10]),
            "loyalty_tier": rng.choice(
                ["Bronze", "Silver", "Gold", "Platinum"], n, p=[0.5, 0.3, 0.15, 0.05]
            ),
            "loyalty_points": (rng.lognormal(5.5, 1.2, n)).astype(int),
            "signup_date": [d.date().isoformat() for d in signup],
            "account_status": rng.choice(
                ["Active", "Inactive", "Suspended"], n, p=[0.85, 0.13, 0.02]
            ),
            "preferred_language": rng.choice(
                ["en", "hi", "ta", "te", "mr"], n, p=[0.5, 0.25, 0.1, 0.08, 0.07]
            ),
            "preferred_currency": rng.choice(["INR", "USD"], n, p=[0.93, 0.07]),
            "preferred_device": rng.choice(
                ["Mobile", "Desktop", "Tablet"], n, p=[0.68, 0.26, 0.06]
            ),
            "preferred_channel": rng.choice(
                ["Website", "Mobile App", "Marketplace"], n, p=[0.35, 0.5, 0.15]
            ),
            "marketing_opt_in": rng.random(n) < 0.62,
            "customer_segment": rng.choice(
                ["Budget", "Premium", "Luxury"], n, p=[0.55, 0.35, 0.10]
            ),
            "occupation": rng.choice(
                [
                    "Engineer",
                    "Teacher",
                    "Doctor",
                    "Student",
                    "Manager",
                    "Designer",
                    "Sales",
                    "Self-employed",
                ],
                n,
            ),
            "annual_income": np.round(rng.lognormal(13.2, 0.6, n), 2),
            "marital_status": rng.choice(["Single", "Married"], n, p=[0.45, 0.55]),
            "country": np.repeat("India", n),
            "state": st,
            "city": city,
            "district": [f"{c} District" for c in city],
            "postal_code": [f"{rng.integers(110000, 700000)}" for _ in range(n)],
            "timezone": np.repeat("Asia/Kolkata", n),
            "address_line1": [
                f"{rng.integers(1, 999)} {s} Street"
                for s in rng.choice(["MG", "Station", "Park", "Lake", "Hill", "Market"], n)
            ],
            "address_line2": [
                f"Apt {rng.integers(1, 80)}" if rng.random() < 0.5 else None for _ in range(n)
            ],
            "latitude": np.round(rng.uniform(8.0, 32.0, n), 6),
            "longitude": np.round(rng.uniform(68.0, 92.0, n), 6),
            "total_orders": total_orders,
            "total_spent": total_spent,
            "average_order_value": aov,
            "first_purchase_date": [d.date().isoformat() for d in first_purchase],
            "last_purchase_date": [d.date().isoformat() for d in last_purchase],
            "churn_risk": rng.choice(["Low", "Medium", "High"], n, p=[0.6, 0.28, 0.12]),
            "customer_lifetime_value": np.round(total_spent * rng.uniform(1.1, 1.8, n), 2),
            "acquisition_source": rng.choice(
                ["Google", "Facebook", "Instagram", "Organic", "Referral"],
                n,
                p=[0.3, 0.2, 0.15, 0.22, 0.13],
            ),
            "acquisition_campaign": rng.choice(
                ["diwali_2025", "summer_sale", "new_user_50", "retarget_q3", "none"],
                n,
                p=[0.2, 0.2, 0.15, 0.1, 0.35],
            ),
            "referral_code": [
                f"REF{rng.integers(10000, 99999)}" if rng.random() < 0.25 else None
                for _ in range(n)
            ],
            "created_at": [d.isoformat(sep=" ") for d in signup],
            "updated_at": [
                (d + timedelta(days=int(x))).isoformat(sep=" ")
                for d, x in zip(signup, rng.integers(1, 200, n))
            ],
        }
    )
    dim_customer.write_csv(out / "dim_customer.csv")

    # ---------------- fact_transaction (50 columns) ----------------
    m = N_TX
    cust_idx = rng.zipf(1.5, m) % n  # repeat-buyer skew
    order_dt = dates(rng, m, "2025-01-01", "2026-06-30")
    payment_dt = [d + timedelta(minutes=int(x)) for d, x in zip(order_dt, rng.integers(1, 120, m))]
    ship_dt = [d + timedelta(hours=int(x)) for d, x in zip(order_dt, rng.integers(4, 72, m))]
    delivery_dt = [d + timedelta(days=int(x)) for d, x in zip(order_dt, rng.integers(1, 8, m))]
    eta_dt = [d + timedelta(days=int(x)) for d, x in zip(order_dt, rng.integers(2, 9, m))]

    qty = rng.poisson(1.3, m) + 1
    unit_price = np.round(rng.lognormal(6.8, 0.8, m), 2)
    coupon = rng.random(m) < 0.35  # 35% coupon usage
    discount = np.where(coupon, np.round(unit_price * qty * rng.uniform(0.05, 0.25, m), 2), 0.0)
    subtotal = np.round(unit_price * qty - discount, 2)
    tax = np.round(subtotal * 0.18, 2)
    fulfillment = rng.choice(["Standard", "Express", "Same Day"], m, p=[0.70, 0.20, 0.10])
    shipping = np.where(
        fulfillment == "Standard", 49.0, np.where(fulfillment == "Express", 99.0, 199.0)
    )
    packaging = np.round(rng.uniform(5, 25, m), 2)
    platform_fee = np.round(subtotal * 0.02, 2)
    gateway_fee = np.round(subtotal * 0.015, 2)
    total = np.round(subtotal + tax + shipping + packaging, 2)

    order_status = rng.choice(
        ["Delivered", "Shipped", "Processing", "Cancelled", "Returned"],
        m,
        p=[0.82, 0.06, 0.05, 0.04, 0.03],
    )
    # return_status consistent-ish with order_status in the seed
    rs_choices = rng.choice(["Requested", "Approved", "Completed"], m, p=[0.2, 0.3, 0.5])
    return_status = np.array(
        [str(r) if s == "Returned" else "None" for s, r in zip(order_status, rs_choices)]
    )
    refund = np.where(order_status == "Returned", total, 0.0)
    rating = rng.choice([5, 4, 3, 2, 1], m, p=[0.55, 0.25, 0.10, 0.06, 0.04])
    fraud_flag = rng.random(m) < 0.005  # ~0.5%
    fraud_score = np.round(np.where(fraud_flag, rng.uniform(0.7, 0.99, m), rng.beta(1.2, 20, m)), 4)

    fact_transaction = pl.DataFrame(
        {
            "transaction_id": uuids(rng, m),
            "order_number": [f"ORD-2025-{700000 + i}" for i in range(m)],
            "customer_id": [customer_ids[i] for i in cust_idx],
            "product_id": uuids(rng, m),
            "seller_id": [str(uuid.UUID(int=int(x), version=4)) for x in rng.integers(1, 200, m)],
            "warehouse_id": [str(uuid.UUID(int=int(x), version=4)) for x in rng.integers(1, 25, m)],
            "order_date": [d.isoformat(sep=" ") for d in order_dt],
            "payment_date": [d.isoformat(sep=" ") for d in payment_dt],
            "shipment_date": [d.isoformat(sep=" ") for d in ship_dt],
            "delivery_date": [d.isoformat(sep=" ") for d in delivery_dt],
            "expected_delivery_date": [d.isoformat(sep=" ") for d in eta_dt],
            "quantity": qty,
            "unit_price": unit_price,
            "discount_amount": discount,
            "coupon_code": [f"SAVE{rng.integers(10, 60)}" if c else None for c in coupon],
            "tax_amount": tax,
            "shipping_charge": shipping,
            "packaging_charge": packaging,
            "platform_fee": platform_fee,
            "payment_gateway_fee": gateway_fee,
            "subtotal": subtotal,
            "total_amount": total,
            "currency": rng.choice(["INR", "USD"], m, p=[0.93, 0.07]),
            "payment_method": rng.choice(
                ["UPI", "Credit Card", "Debit Card", "Wallet", "COD", "PayPal"],
                m,
                p=[0.40, 0.22, 0.15, 0.10, 0.08, 0.05],
            ),
            "payment_status": rng.choice(
                ["Paid", "Pending", "Failed", "Refunded"], m, p=[0.90, 0.04, 0.03, 0.03]
            ),
            "order_status": order_status,
            "return_status": return_status,
            "refund_amount": refund,
            "refund_reason": [
                str(r) if s == "Returned" else None
                for s, r in zip(
                    order_status,
                    rng.choice(["damaged", "wrong_item", "not_as_described", "size_issue"], m),
                )
            ],
            "shipping_provider": rng.choice(
                ["Delhivery", "BlueDart", "Ekart", "DTDC", "XpressBees"],
                m,
                p=[0.3, 0.22, 0.22, 0.14, 0.12],
            ),
            "tracking_number": [f"TRK{rng.integers(10**9, 10**10)}" for _ in range(m)],
            "fulfillment_type": fulfillment,
            "delivery_partner": rng.choice(["InHouse", "3PL"], m, p=[0.35, 0.65]),
            "warehouse_location": rng.choice(
                ["Bhiwandi", "Hoskote", "Gurgaon", "Chakan", "Hyderabad"], m
            ),
            "customer_rating": rating,
            "review_id": [
                str(uuid.UUID(bytes=rng.bytes(16), version=4)) if rng.random() < 0.4 else None
                for _ in range(m)
            ],
            "review_sentiment": rng.choice(
                ["Positive", "Neutral", "Negative"], m, p=[0.72, 0.18, 0.10]
            ),
            "fraud_score": fraud_score,
            "fraud_flag": fraud_flag,
            "device_type": rng.choice(["Android", "iPhone", "Desktop"], m, p=[0.55, 0.22, 0.23]),
            "browser": rng.choice(
                ["Chrome", "Safari", "Edge", "Firefox"], m, p=[0.6, 0.22, 0.1, 0.08]
            ),
            "operating_system": rng.choice(
                ["Android", "iOS", "Windows", "macOS"], m, p=[0.52, 0.2, 0.2, 0.08]
            ),
            "ip_address": [
                f"10.{rng.integers(0, 256)}.{rng.integers(0, 256)}.{rng.integers(1, 255)}"
                for _ in range(m)
            ],
            "session_id": uuids(rng, m),
            "cart_id": uuids(rng, m),
            "checkout_duration_seconds": (rng.lognormal(4.6, 0.7, m)).astype(int),
            "source_channel": rng.choice(
                ["Website", "App", "Marketplace"], m, p=[0.38, 0.47, 0.15]
            ),
            "marketing_campaign": rng.choice(
                ["diwali_2025", "summer_sale", "retarget_q3", "none"], m, p=[0.18, 0.18, 0.12, 0.52]
            ),
            "acquisition_source": rng.choice(
                ["Google", "Facebook", "Organic", "Referral"], m, p=[0.35, 0.22, 0.28, 0.15]
            ),
            "created_at": [d.isoformat(sep=" ") for d in order_dt],
            "updated_at": [d.isoformat(sep=" ") for d in delivery_dt],
        }
    )
    fact_transaction.write_csv(out / "fact_transaction.csv")
    print(
        f"wrote dim_customer({n} x {len(dim_customer.columns)} cols) "
        f"fact_transaction({m} x {len(fact_transaction.columns)} cols) -> {out}"
    )


if __name__ == "__main__":
    main()
