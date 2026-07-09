# spec.yaml Reference

Complete language reference for declarative dataset specs. Write a `spec.yaml` to generate FK-safe synthetic data with zero sample data — the engine compiles your declaration into the same catalog entries that `scan`+`profile` would produce, then generates from it.

See [GETTING-STARTED.md](GETTING-STARTED.md) for a runnable walkthrough of the Path A workflow.

---

## Top-level structure

```yaml
version: 1                  # required; must be 1
tables:
  - name: <table_name>      # snake_case recommended
    columns: [...]           # at least one column required
    joins: [...]            # optional; Cube.js-style join declarations
    rows: <int>             # optional; per-table default row count
joins: []                    # optional; explicit join declarations
```

---

## Column types

| Type | Generated as | Notes |
|---|---|---|
| `int` | Sequential or random integers | Use with `mean`, `std`, `min`, `max` |
| `float` | Floating-point numbers | Lognormal for money (mean+std); uniform otherwise |
| `string` | Text values | Use with `values` (categorical) or `format` (ID templates) |
| `bool` | `true` / `false` | Use with `values: {true: 60, false: 40}` |
| `date` | Dates (YYYY-MM-DD) | Use with `start` / `end` |
| `datetime` | Timestamps | Use with `start` / `end`; combine with `after` for temporal ordering |
| `uuid` | UUID v4 strings | Default for primary keys |

---

## Column fields

### `primary_key`

```yaml
- name: customer_id
  type: uuid
  primary_key: true
```

Exactly one per table. Generates unique values automatically. Required for parent tables in FK chains.

---

### `references` (FK declaration via column)

Declare a foreign key at the column level. The parent table must have a `primary_key`.

```yaml
- name: customer_id
  type: uuid
  references: dim_customer.customer_id    # table.column
```

Parent-first generation ensures zero orphans.

---

### `values` — weighted categoricals

```yaml
- name: payment_method
  type: string
  values:
    UPI: 40
    Credit Card: 22
    Debit Card: 15
    Wallet: 10
    COD: 8
    PayPal: 5
```

Weights are normalized automatically (any positive numbers work). For equal weights, use a list:

```yaml
- name: status
  type: string
  values: [Active, Inactive, Pending]
```

---

### `mean`, `std`, `min`, `max` — numeric distributions

```yaml
# Money columns (lognormal fit: σ² = ln(1 + (std/mean)²))
- name: annual_income
  type: float
  mean: 850000
  std: 500000
  min: 0

# Count columns (Poisson fit: λ = mean)
- name: quantity
  type: int
  mean: 3
  min: 1

# Integer range
- name: age
  type: int
  min: 18
  max: 85
```

**Engine rules:**
- Columns named `amount`, `price`, `total`, `income`, `salary`, `revenue` → lognormal fit
- Columns named `quantity`, `count`, `items`, `units` → Poisson fit
- Others → uniform in `[min, max]` or `[mean - std, mean + std]`

---

### `start`, `end` — date/datetime ranges

```yaml
- name: signup_date
  type: date
  start: 2020-01-01
  end: 2026-01-01

- name: order_timestamp
  type: datetime
  start: 2024-01-01T00:00:00
  end: 2026-06-30T23:59:59
```

---

### `null_ratio` — sparsity

```yaml
- name: coupon_code
  type: string
  null_ratio: 0.65     # 65% of rows will be null
```

Range: `0.0` to `0.95`. Cannot exceed 95%.

---

### `format` — ID/code templates

```yaml
- name: order_number
  type: string
  format: "ORD-2025-######"    # # = digit, ? = letter

- name: tracking_id
  type: string
  format: "TRK-##########"     # 10 digits

- name: mrn
  type: string
  format: "MRN-#######"         # 7 digits
```

**Use for:** business codes, order numbers, tracking IDs, MRNs, product SKUs.

**Do NOT use for:** names, emails, phone numbers — the engine has built-in realistic samplers for those. Using `format` on person/contact columns produces gibberish.

**Name-based columns the engine handles automatically:**

| Column name pattern | Sampler |
|---|---|
| `full_name`, `first_name`, `last_name` | Real human first/last names |
| `email` | Name-based realistic email addresses |
| `phone`, `phone_number`, `mobile` | Realistic phone numbers |
| `address`, `address_line1`, `street` | Street addresses |
| `city` | Real world city names |
| `country` | Real world country names |

For these columns, give only `name` and `type` — no `format` needed.

---

### `expr` — arithmetic from sibling columns

```yaml
# Declare in order: dependencies before the column that uses them
- name: unit_price
  type: float
  mean: 149.99
  std: 50

- name: quantity
  type: int
  mean: 2
  min: 1

- name: discount_amount
  type: float
  mean: 10
  std: 5

- name: subtotal
  type: float
  expr: "unit_price * quantity - discount_amount"
```

**Rules:**
- Columns referenced in `expr` must be declared **before** the column that uses them
- Supported operators: `+`, `-`, `*`, `/`, `//` (floor division)
- Division by zero returns `null`

---

### `after` — temporal ordering

Ensures this column's datetime is always after another column's datetime by a random interval.

```yaml
- name: order_date
  type: datetime
  start: 2024-01-01T00:00:00
  end: 2026-06-30T23:59:59

- name: payment_date
  type: datetime
  after: {column: order_date, min_minutes: 1, max_minutes: 120}
```

**Common use:** `payment_date` always after `order_date`; `discharge_date` always after `admission_date`; `delivery_date` always after `ship_date`.

---

### `null_unless` — conditional presence

```yaml
- name: refund_reason
  type: string
  values: {damaged: 30, wrong_item: 25, not_as_described: 25, size_issue: 20}
  null_unless: "order_status = 'Returned'"
```

The column is null unless the condition is true. Used to model fields that only apply in specific cases (refund reason only for returned orders, cancellation code only for cancelled orders).

---

### `values_by` — hierarchical categoricals

Ensures consistency across related categorical columns (city within state, region within country).

```yaml
- name: state
  type: string
  values: {Maharashtra: 40, Karnataka: 35, Delhi: 25}

- name: city
  type: string
  values_by:
    column: state
    mapping:
      Maharashtra: {Mumbai: 55, Pune: 35, Nagpur: 10}
      Karnataka: {Bangalore: 80, Mysore: 20}
      Delhi: {New Delhi: 100}
```

If a state's city distribution is not specified, the engine falls back to the column's own `values` weights.

---

### `seasonal_scale` — scale a measure by seasonality

Multiply a base-sampled numeric column by the seasonal multiplier at an `anchor`
date column, so measures grow on peak days/years. Declare after the anchor. Takes
the same factor fields as the table-level `seasonality` block (`trend`, `weekly`,
`yearly`, `holidays`, `events`, ...).

```yaml
- name: revenue
  type: float
  mean: 1800
  std: 900
  seasonal_scale:
    anchor: order_ts
    trend: {kind: linear, annual_growth: 0.1}
    yearly: {peaks: [{month: 11, day: 29, strength: 1.6, width_days: 5}]}
```

### `calendar` — derived date-attribute columns

Expands one block into **N columns** named `{prefix or anchor}_{part}`.

```yaml
- name: cal
  type: string
  calendar:
    anchor: order_ts
    parts: [day_of_week, is_weekend, month, quarter, fiscal_quarter, season, is_holiday]
    fiscal_year_start_month: 4     # optional; defaults from adp.yaml generation:
    hemisphere: north              # optional; for season
    country: IN                    # optional; for is_holiday / is_business_day
```

Parts: `day_of_week` (Mon=1..Sun=7), `is_weekend`, `week`, `month`, `quarter`,
`year`, `fiscal_month`, `fiscal_quarter`, `fiscal_year`, `season`, `is_holiday`,
`is_business_day`.

### `inherit` — carry a parent column across an FK

Requires `references` on the same column. Format: `"parent_column as local_name"`.
The child inherits the parent's value **per row** (gathered with the same index as
the FK key), typically the parent's seasonal timestamp — then offset with `after`:

```yaml
- name: order_id
  type: uuid
  references: fact_orders.order_id
  inherit: "order_ts as parent_order_ts"
- name: payment_ts
  type: datetime
  after: {column: parent_order_ts, min_minutes: 1, max_minutes: 240}
```

See [SEASONALITY.md](SEASONALITY.md) for the full seasonality guide.

---

## Table-level fields

### `rows` — per-table row count

Overrides the global `--rows` argument for this specific table.

```yaml
- name: products
  rows: 50
  columns:
    - {name: product_id, type: uuid, primary_key: true}
    - {name: category, type: string, values: {Electronics: 40, Apparel: 35, Home: 25}}
```

Use for dimension tables (small) vs fact tables (large):

```yaml
- name: dim_customer
  rows: 1000
  columns: [...]

- name: fact_transaction
  # inherits global --rows from CLI (e.g. 50000)
  columns: [...]
```

---

### `seasonality` — time-aware event volume

Shapes an `anchor` timestamp column so event volume peaks on busy days and follows
a growth trend (the fixed row count is redistributed over time, not changed).

```yaml
- name: fact_orders
  rows: 50000
  seasonality:
    anchor: order_ts                          # a date/datetime column of this table
    trend: {kind: linear, annual_growth: 0.18}
    weekly: {Sat: 1.6, Sun: 1.4, Mon: 0.8}
    yearly: {amplitude: 0.15, peaks: [{month: 11, day: 29, strength: 3.5, width_days: 4}]}
    holidays: {country: IN, strength: 1.6, window_days: 1}
    events: [{name: summer_sale, start: 2025-06-01, end: 2025-06-15, multiplier: 1.8}]
  columns:
    - {name: order_id, type: uuid, primary_key: true}
    - {name: order_ts, type: datetime, start: 2024-01-01, end: 2025-12-31}
```

A `datetime` anchor also accepts a `daily: {hour_weights: [...24...]}` shape.
Country holidays need the `[seasonality]` extra; explicit `dates:` need nothing.
Validate output with `adp seasonality-check`. Full guide: [SEASONALITY.md](SEASONALITY.md).

---

### `joins` — Cube.js-style join declarations

Alternative to `references` at the column level. Declares joins from the perspective of the enclosing table.

```yaml
- name: dim_customer
  columns:
    - {name: customer_id, type: uuid, primary_key: true}
    - {name: full_name, type: string}
  joins:
    - name: fact_transaction
      relationship: one_to_many        # one customer, many transactions
      sql: "{TABLE.customer_id} = {fact_transaction.customer_id}"
    - name: customer_kyc
      relationship: one_to_one        # unique FK: one KYC per customer
      sql: "{TABLE.customer_id} = {customer_kyc.customer_id}"
```

**Relationship meanings:**

| Relationship | Current table | Named table |
|---|---|---|
| `one_to_many` | Parent (the "one") | Child holds FK (the "many") |
| `many_to_one` | Child holds FK (the "many") | Parent (the "one") |
| `one_to_one` | Parent | Exactly one row per parent (unique FK) |

`{TABLE}` (or `{CUBE}`) refers to the enclosing table. `{other_table}` refers to the joined table.

---

## `joins[]` — explicit join declarations (top-level)

Alternative to both `references` and table-level `joins`. Declares FKs at the top level.

```yaml
version: 1
tables:
  - name: orders
    columns:
      - {name: order_id, type: uuid, primary_key: true}
      - {name: customer_id, type: uuid}
      - {name: amount, type: float, mean: 150, std: 50}
  - name: customers
    columns:
      - {name: customer_id, type: uuid, primary_key: true}
joins:
  - left: orders.customer_id      # child
    right: customers.customer_id   # parent
    relationship: many_to_one
```

Normalized form: `left` is always the FK side, `right` is always the PK side.

---

## Examples — minimal to advanced

### Minimal (1 table, 3 columns)

```yaml
version: 1
tables:
  - name: products
    columns:
      - name: product_id
        type: uuid
        primary_key: true
      - name: category
        type: string
        values: {Electronics: 40, Apparel: 35, Home: 25}
      - name: price
        type: float
        mean: 99.99
        std: 30
```

### Intermediate (2 tables, FK, weighted categories)

```yaml
version: 1
tables:
  - name: customers
    rows: 1000
    columns:
      - name: customer_id
        type: uuid
        primary_key: true
      - name: gender
        type: string
        values: {Male: 48, Female: 50, Other: 2}
      - name: age
        type: int
        min: 18
        max: 85
      - name: signup_date
        type: date
        start: 2020-01-01
        end: 2026-01-01

  - name: orders
    columns:
      - name: order_id
        type: uuid
        primary_key: true
      - name: customer_id
        type: uuid
        references: customers.customer_id
      - name: amount
        type: float
        mean: 142.50
        std: 89.30
      - name: status
        type: string
        values: {Delivered: 80, Processing: 12, Cancelled: 8}
```

### Advanced (full features: expr, after, null_unless, values_by)

```yaml
version: 1
tables:
  - name: dim_customer
    rows: 5000
    columns:
      - name: customer_id
        type: uuid
        primary_key: true
      - name: full_name
        type: string                    # built-in name sampler
      - name: email
        type: string                   # built-in email sampler
      - name: state
        type: string
        values: {Maharashtra: 40, Karnataka: 35, Delhi: 25}
      - name: city
        type: string
        values_by:
          column: state
          mapping:
            Maharashtra: {Mumbai: 55, Pune: 35, Nagpur: 10}
            Karnataka: {Bangalore: 80, Mysore: 20}
            Delhi: {New Delhi: 100}
      - name: signup_date
        type: date
        start: 2020-01-01
        end: 2026-01-01

  - name: fact_transaction
    columns:
      - name: transaction_id
        type: uuid
        primary_key: true
      - name: customer_id
        type: uuid
        references: dim_customer.customer_id
      - name: order_date
        type: datetime
        start: 2024-01-01T00:00:00
        end: 2026-06-30T23:59:59
      - name: payment_date
        type: datetime
        after: {column: order_date, min_minutes: 1, max_minutes: 120}
      - name: unit_price
        type: float
        mean: 149.99
        std: 50
      - name: quantity
        type: int
        mean: 2
        min: 1
      - name: discount_amount
        type: float
        mean: 10
        std: 5
      - name: total_amount
        type: float
        expr: "unit_price * quantity - discount_amount"    # arithmetic
      - name: payment_method
        type: string
        values: {UPI: 40, Credit Card: 22, Debit Card: 15, Wallet: 10, COD: 8, PayPal: 5}
      - name: order_status
        type: string
        values: {Delivered: 82, Shipped: 6, Processing: 5, Cancelled: 4, Returned: 3}
      - name: refund_reason
        type: string
        values: {damaged: 30, wrong_item: 25, not_as_described: 25, size_issue: 20}
        null_unless: "order_status = 'Returned'"          # conditional null
      - name: rating
        type: int
        values: {5: 55, 4: 25, 3: 10, 2: 6, 1: 4}
      - name: coupon_used
        type: bool
        values: {true: 35, false: 65}
```

---

## Validation rules

| Rule | Error |
|---|---|
| At least one column per table | `table needs at least one column` |
| Exactly one `primary_key` per table (recommended) | Warning only |
| `references` must be `"table.column"` | `references must be "table.column"` |
| `expr` columns must be declared after all columns they reference | Engine error at generation time |
| `values_by` `column` must exist in same table | `references unknown column` |
| Circular FKs | Detected and rejected at apply-spec time |
| `null_ratio` > 0.95 | Rejected (`ge: 0.0, le: 0.95`) |

---

## Full example specs for reference

| Example | Path | Highlights |
|---|---|---|
| [benchmarks/fixtures/seasonal-retail-spec.yaml](../benchmarks/fixtures/seasonal-retail-spec.yaml) | A | Seasonality + FK chain |
| [cursor-test/spec.yaml](../cursor-test/spec.yaml) | A | MCP test harness; same as customer-transaction |
| [healthcare-claims/spec.yaml](https://github.com/Yogi776/data-generation-sdk/blob/main/healthcare-claims/spec.yaml) | A | 5+ tables, temporal/hierarchy rules |
| [retail/spec.yaml](../../retail/spec.yaml) | A | 4-table retail star schema |
