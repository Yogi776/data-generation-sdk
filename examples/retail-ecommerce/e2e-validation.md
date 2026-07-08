# Retail E-Commerce E2E Validation

50,000 rows per table generated from profiled metadata (seed 42).

- ✅ **volume customers** — 50,000 rows
- ✅ **volume products** — 50,000 rows
- ✅ **volume orders** — 50,000 rows
- ✅ **volume transactions** — 50,000 rows
- ✅ **FK orders.customer_id -> customers.customer_id** — 0 orphan rows
- ✅ **FK orders.product_id -> products.product_id** — 0 orphan rows
- ✅ **FK transactions.order_id -> orders.order_id** — 0 orphan rows
- ✅ **PK unique customers.customer_id** — 50,000 distinct / 50,000 rows
- ✅ **PK unique products.product_id** — 50,000 distinct / 50,000 rows
- ✅ **PK unique orders.order_id** — 50,000 distinct / 50,000 rows
- ✅ **PK unique transactions.transaction_id** — 50,000 distinct / 50,000 rows

## Statistical fidelity (source vs generated)
- ✅ **mean fidelity orders.total_amount** — source 5,390.49 vs generated 5,379.52 (Δ0.2%)
- ✅ **std fidelity orders.total_amount** — source 6,492.71 vs generated 6,344.82 (Δ2.3%)
- ✅ **mean fidelity orders.quantity** — source 2.39 vs generated 2.40 (Δ0.2%)
- ✅ **std fidelity orders.quantity** — source 1.19 vs generated 1.19 (Δ0.1%)
- ✅ **mean fidelity transactions.amount** — source 5,384.14 vs generated 5,391.31 (Δ0.1%)
- ✅ **std fidelity transactions.amount** — source 6,517.09 vs generated 6,496.61 (Δ0.3%)
- ✅ **mean fidelity products.unit_price** — source 2,325.36 vs generated 2,314.52 (Δ0.5%)
- ✅ **std fidelity products.unit_price** — source 3,369.69 vs generated 3,300.21 (Δ2.1%)
- ✅ **categorical fidelity orders.status** — TVD 0.0013
- ✅ **categorical fidelity orders.channel** — TVD 0.0024
- ✅ **categorical fidelity transactions.payment_method** — TVD 0.0033
- ✅ **categorical fidelity customers.segment** — TVD 0.0018
- ✅ **categorical fidelity customers.city** — TVD 0.0021
- ✅ **categorical fidelity products.category** — TVD 0.0061
- ✅ **no source email values copied** — 0 overlapping emails
- ✅ **deterministic (seed 99, 5k rows, 4 tables)** — byte-identical reruns
- ✅ **analytical joins run** — revenue series (12 months), top cities ['Mumbai', 'Bangalore', 'Pune'], 5 payment methods

## Verdict: ✅ ALL CHECKS PASSED — production-ready for dev/test/analytics use
