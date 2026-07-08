# Data Quality Report

**Quality Score: 100.0/100** (score v1)

| Category | Score |
|---|---|
| integrity | 100.0 |
| completeness | 100.0 |
| consistency | 100.0 |
| validity | 100.0 |

## customers — 11/11 passed (25000 rows)

| Check | Column | Result | Evidence |
|---|---|---|---|
| unique | customer_id | ✅ | 0 duplicate value(s) |
| not_null | customer_id | ✅ | null ratio 0.0000 (tolerance 0.0) |
| not_null | full_name | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | email | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | phone | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | city | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | city | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | segment | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | segment | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | signup_date | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | is_active | ✅ | null ratio 0.0000 (tolerance 0.02) |

## orders — 15/15 passed (25000 rows)

| Check | Column | Result | Evidence |
|---|---|---|---|
| unique | order_id | ✅ | 0 duplicate value(s) |
| not_null | order_id | ✅ | null ratio 0.0000 (tolerance 0.0) |
| not_null | customer_id | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | product_id | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | order_date | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | quantity | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | quantity | ✅ | 2 value(s) (0.01%) outside [0.1, 10.9] (tolerance 1%) |
| not_null | total_amount | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | total_amount | ✅ | 1 value(s) (0.00%) outside [-1.124e+04, 1.246e+05] (tolerance 1%) |
| not_null | channel | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | channel | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | status | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | status | ✅ | 0 value(s) outside accepted set (0.00%) |
| foreign_key | customer_id | ✅ | 0 orphan value(s) |
| foreign_key | product_id | ✅ | 0 orphan value(s) |

## products — 10/10 passed (25000 rows)

| Check | Column | Result | Evidence |
|---|---|---|---|
| unique | product_id | ✅ | 0 duplicate value(s) |
| not_null | product_id | ✅ | null ratio 0.0000 (tolerance 0.0) |
| not_null | product_name | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | category | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | category | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | unit_price | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | unit_price | ✅ | 70 value(s) (0.28%) outside [-2358, 2.704e+04] (tolerance 1%) |
| not_null | stock_quantity | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | stock_quantity | ✅ | 0 value(s) (0.00%) outside [-48.8, 548.8] (tolerance 1%) |
| not_null | is_discontinued | ✅ | null ratio 0.0000 (tolerance 0.02) |

## transactions — 11/11 passed (25000 rows)

| Check | Column | Result | Evidence |
|---|---|---|---|
| unique | transaction_id | ✅ | 0 duplicate value(s) |
| not_null | transaction_id | ✅ | null ratio 0.0000 (tolerance 0.0) |
| not_null | order_id | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | payment_method | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | payment_method | ✅ | 0 value(s) outside accepted set (0.00%) |
| not_null | amount | ✅ | null ratio 0.0000 (tolerance 0.02) |
| range | amount | ✅ | 0 value(s) (0.00%) outside [-1.124e+04, 1.246e+05] (tolerance 1%) |
| not_null | transaction_date | ✅ | null ratio 0.0000 (tolerance 0.02) |
| not_null | tx_status | ✅ | null ratio 0.0000 (tolerance 0.02) |
| accepted_values | tx_status | ✅ | 0 value(s) outside accepted set (0.00%) |
| foreign_key | order_id | ✅ | 0 orphan value(s) |
