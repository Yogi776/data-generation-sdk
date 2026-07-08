# Customer + Transaction Scenario — Instructions

Your spec: `dim_customer` (47 cols) + `fact_transaction` (51 cols), 1:N via
`customer_id`, with production-style distributions (UPI 40%, Delivered 82%,
5★ 55%, coupon 35%, fraud ~0.5%, …). **Built and validated: 13/13 targets met,
quality 100/100.** Reports: `distribution-validation.md`, `quality-report.md`.

## Two ways to run this scenario

### Way 1 (recommended): declarative spec — no seed data, no Python

`spec.yaml` in this folder declares all 98 columns with your exact weights:

```bash
adp init --name customer-transaction
adp apply-spec spec.yaml        # 2 tables, 98 columns, 1 FK — no scan/profile needed
adp generate-data --rows 50000 --output parquet
adp quality-check
```

Validated: UPI 40.6%, Delivered 82.4%, 5★ 54.8% (Int64), gender 50/48/2,
coupon 35.2%, 0 FK orphans, all PKs unique.

### Way 2: seed data (when you have real samples or need learned shapes)

`make_data.py` exists only as a stand-in for real sample data — if you have
production exports, point `adp connect` at them and skip it entirely.
Seed data is the better path when you want shapes you can't easily declare
(long-tail category mixes, real lognormal tails, correlations present in
your samples); the spec is the better path for cold-start from a design doc.

## Run it yourself (seed path)

```bash
cd examples/customer-transaction
python make_data.py                 # writes data/dim_customer.csv + data/fact_transaction.csv
adp init --name customer-transaction
adp connect --name crm --type csv --path ./data
adp scan       # finds fact_transaction.customer_id -> dim_customer (dim_/fact_ prefixes handled)
adp profile --sample-rows 20000
adp generate-data --rows 50000 --output parquet     # ~2s for 100k rows
adp quality-check --report quality-report.md
```

Change volume: `--rows 1000000`. Change format: `--output csv|duckdb|sql`.
Reproduce exactly: `--seed 42`. Different data, same shapes: any other seed.

## To use YOUR values instead of the sample seed

Edit `make_data.py` (or replace the CSVs with real exported samples):
- category mixes = the `p=[...]` weights per column,
- money shapes = the lognormal means/sigmas,
- volumes = `N_CUSTOMERS` / `N_TX`.
Then rerun scan → profile → generate. If you have real production samples,
skip make_data.py entirely — point `adp connect` at them (profiles are
learned the same way; PII is flagged automatically).

## Validated results (50k rows/table)

| Target | Spec | Generated |
|---|---|---|
| Gender M/F/O | 48/50/2 | 45.8/51.5/2.7 |
| Customer type New/Ret/VIP | 70/20/10 | 68.5/21.4/10.1 |
| Segment Budget/Prem/Lux | 55/35/10 | 56.0/33.6/10.4 |
| Payment UPI/CC/DC/Wal/COD/PayPal | 40/22/15/10/8/5 | 40.0/21.8/15.0/9.6/8.3/5.3 |
| Order status Del/Ship/Proc/Canc/Ret | 82/6/5/4/3 | 81.9/5.9/5.1/4.0/3.1 |
| Rating 5/4/3/2/1 | 55/25/10/6/4 | 55.5/24.3/10.0/6.2/4.0 |
| Fulfillment Std/Exp/Same-day | 70/20/10 | 69.4/20.6/10.0 |
| Coupon usage | 35% | 35.4% |
| Fraud rate | 0.3–0.8% | 0.59% |
| FK orphans / PK duplicates | 0 | 0 / 0 |

## Dependencies & joins (spec.yaml supports all of these)

```yaml
# JOINS — Cube.js style, nested under a table; three cardinalities
joins:
  - name: fact_transaction
    relationship: one_to_many          # one customer, many transactions
    sql: "{TABLE.customer_id} = {fact_transaction.customer_id}"
  - name: customer_kyc
    relationship: one_to_one           # unique FK: exactly one KYC per customer
    sql: "{TABLE.customer_id} = {customer_kyc.customer_id}"
  # many_to_one: this table holds the FK

# TEMPORAL: payment always 1–120 minutes after order
- name: payment_date
  type: datetime
  after: {column: order_date, min_minutes: 1, max_minutes: 120}

# ARITHMETIC: row-exact money math
- name: subtotal
  type: float
  expr: unit_price * quantity - discount_amount

# CONDITIONAL: refunds only exist for returned orders
- name: refund_reason
  type: string
  values: {damaged: 30, wrong_item: 25, not_as_described: 25, size_issue: 20}
  null_unless: order_status = 'Returned'

# HIERARCHICAL: city always consistent with state, state with country
- name: city
  type: string
  values_by:
    column: state
    mapping:
      Maharashtra: {Mumbai: 55, Pune: 35, Nagpur: 10}
      Karnataka: {Bangalore: 82, Mysore: 18}
```

Validated at 10k rows: payment ≥ order in 100% of rows, subtotal/total math
exact to the paisa, refund fields null except for Returned, 10,000/10,000
city-state-country consistent, 1:1 FKs perfectly unique, 0 orphans everywhere.

## Remaining caveats

- `fraud_flag` comes back as string "true"/"false" rather than boolean.
- Dependencies are within-table, same-row; cross-table derived aggregates
  (customer.total_spent = sum of their transactions) are roadmap.
- Engine features this scenario contributed: dim_/fact_ FK matching, integer
  categorical fidelity, >50% null sparsity, apply-spec, join cardinalities,
  and the dependency engine (`after`, `expr`, `null_unless`, `values_by`).
