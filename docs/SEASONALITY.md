# Universal Seasonality Engine

Most synthetic data is statistically valid but temporally flat — rows are spread
uniformly across a date range, so there is no Black Friday spike, no weekend lift,
no growth trend, no festival surge. The seasonality engine makes **time-aware
business behavior a first-class, metadata-driven concept**: you declare it in the
spec, and the generator produces it.

Nothing is hardcoded per industry. Every effect reduces to the same handful of
**generic primitives**, composed multiplicatively:

```
value(t) = base × trend(t) × yearly(t) × monthly(t) × weekly(t) × daily(t)
                × holiday(t) × Π events_i(t)   + noise
```

"Black Friday", "Diwali", "monsoon", "payday", "flu season", "quarter close" and
"recession" are all just the same primitives with different numbers.

---

## Two effects

1. **Volume seasonality** — *when* events happen. A table's fixed row count is
   distributed non-uniformly across time, so aggregating by day/week/month reveals
   peaks and troughs. Row count is unchanged.
2. **Value seasonality** — *how big* a measure is. A metric column (revenue, units)
   is multiplied by the seasonal factor at its anchor date, so peak days also carry
   bigger baskets.

Plus **calendar features**: derive `quarter`, `season`, `is_holiday`, `fiscal_quarter`,
etc. from any timestamp column.

---

## Quick start

```yaml
version: 1
tables:
  - name: fact_orders
    rows: 50000
    seasonality:
      anchor: order_ts                        # a date/datetime column of this table
      trend: {kind: linear, annual_growth: 0.18}
      weekly: {Sat: 1.6, Sun: 1.4, Mon: 0.8}
      yearly: {peaks: [{month: 11, day: 29, strength: 3.5, width_days: 4}]}
      holidays: {country: IN, strength: 1.6, window_days: 1}
      events: [{name: summer_sale, start: 2025-06-01, end: 2025-06-15, multiplier: 1.8}]
    columns:
      - {name: order_id, type: uuid, primary_key: true}
      - {name: order_ts, type: datetime, start: 2024-01-01, end: 2025-12-31}
```

```bash
adp apply-spec spec.yaml
adp generate-data --rows 50000
adp seasonality-check --report seasonality.md --csv seasonality-daily.csv
```

A full multi-table seasonal spec lives at [`benchmarks/fixtures/seasonal-retail-spec.yaml`](../benchmarks/fixtures/seasonal-retail-spec.yaml).

---

## The `seasonality` block (table-level)

Declared on a fact table. `anchor` names a `date`/`datetime` column of that table;
a `datetime` anchor also gets a time-of-day shape from `daily`.

| Field | Meaning |
|---|---|
| `anchor` | **Required.** The timestamp column whose event volume is shaped. |
| `base` | Baseline multiplier (default `1.0`). |
| `trend` | Long-run drift: `{kind: linear\|exponential\|logarithmic, annual_growth: 0.15}`. |
| `weekly` | Day-of-week multipliers: `{Mon: 0.8, Sat: 1.6, ...}` (missing days = 1.0). |
| `monthly` | `{shape: month_start\|month_end, strength: 0.5}` or `{weights_by_day: {1: 1.2, 31: 1.5}}`. |
| `yearly` | `{amplitude: 0.3, peaks: [{month, day, strength, width_days}]}` — sinusoid + recurring Gaussian peaks. |
| `daily` | `{hour_weights: [...24 floats...]}` — hour-of-day shape (datetime anchors only). |
| `holidays` | `{country: IN, strength: 1.8, window_days: 2}` or `{dates: [YYYY-MM-DD, ...], ...}`. |
| `events` | `[{name, start, end, multiplier}]` — promotions, weather, economic windows. |
| `noise` | `{kind: lognormal\|normal, sigma: 0.05}` — jitter on the volume curve. |

`trend`/`holidays` are anchored to the range of the anchor column (`start`/`end`).

### Holidays

`{country: "IN"}` uses the optional [`holidays`](https://pypi.org/project/holidays/)
package — install it with `pip install 'ai-data-platform[seasonality]'`. Without the
package, use an explicit list: `{dates: ["2025-12-25", "2025-01-01"], strength: 2.0}`
(always works, no dependency). A `subdiv:` narrows to a state/province.

---

## Value seasonality — `seasonal_scale` (column-level)

Scale a base-sampled measure by the seasonal multiplier at an anchor date. Same
factor fields as the `seasonality` block. Declare the column **after** its anchor.

```yaml
- name: revenue
  type: float
  mean: 1800
  std: 900
  seasonal_scale:
    anchor: order_ts
    yearly: {amplitude: 0.15, peaks: [{month: 11, day: 29, strength: 1.6, width_days: 5}]}
```

---

## Calendar features — `calendar` (column-level)

One block expands into **N derived columns**, named `{prefix or anchor}_{part}`.

```yaml
- name: cal
  type: string
  calendar:
    anchor: order_ts
    parts: [day_of_week, is_weekend, month, quarter, fiscal_quarter, season, is_holiday]
    fiscal_year_start_month: 4     # optional (defaults from adp.yaml)
    country: IN                    # for is_holiday / is_business_day
```

Available parts: `day_of_week` (Mon=1..Sun=7), `is_weekend`, `week`, `month`,
`quarter`, `year`, `fiscal_month`, `fiscal_quarter`, `fiscal_year`, `season`,
`is_holiday`, `is_business_day`. Defaults for `fiscal_year_start_month`,
`hemisphere`, and holiday `country` come from `generation:` in `adp.yaml` when the
block omits them.

---

## Cross-table propagation — `inherit`

Real businesses aren't one table: orders → payments → shipments → returns all peak
on the same days. Declare `inherit` on a child's FK column to carry the parent's
exact timestamp across the join (same row), then offset it with `after`:

```yaml
- name: order_id
  type: uuid
  references: fact_orders.order_id
  inherit: "order_ts as parent_order_ts"     # carry the parent timestamp
- name: payment_ts
  type: datetime
  start: 2024-01-01
  end: 2025-12-31
  after: {column: parent_order_ts, min_minutes: 1, max_minutes: 240}
```

The child inherits the parent timestamp **per row** (gathered with the same index
as the FK key — zero orphans, guaranteed `payment_ts >= parent_order_ts`). Chains
are transitive: a grandchild can inherit the child's timestamp, so the whole
lineage shares one temporal rhythm.

---

## Validation

`adp seasonality-check` aggregates the generated anchor columns and scores five
generic metrics against the declared factor curve:

| Metric | What it checks |
|---|---|
| `curve_correlation` | Pearson r of expected vs observed daily density. |
| `weekly_pattern` | Observed day-of-week profile vs declared `weekly` weights. |
| `event:*` | Each event/promotion window spikes as declared. |
| `trend_direction` | Daily-count slope sign matches `annual_growth`. |
| cross-table | Children share top-K peak days (or high correlation) with their seasonal parent. |

`--report seasonality.md` writes a Markdown report; `--csv daily.csv` writes
per-day observed-vs-expected intensity for charting. `adp seasonality-preview
<table>` inspects a config and its expected curve **before** generating.

The same capabilities are exposed via the SDK (`ADPClient.seasonality_check`,
`.preview_seasonality`) and MCP (`run_seasonality_check`, `preview_seasonality`).

---

## Guarantees & scope

- **Deterministic** — identical `(seed, spec)` → identical output. Seasonal draws
  use the same per-`(seed, table, chunk)` RNG as the rest of the engine.
- **Streaming** — the per-day weight curve is bounded by the number of days
  (thousands), never the row count; generation stays chunked and memory-bounded.
- **Non-seasonal specs are unaffected** — inheritance consumes no RNG, so specs
  without a `seasonality`/`inherit` block generate byte-for-byte as before.
- **Executor** — seasonal plans run on the Python engine (the Go executor has no
  date/seasonal samplers yet); this is selected automatically.
- **Cross-table validation** scores each child against its *directly* seasonal
  parent. Deeper chains still generate correctly (the data is offset per row);
  they're just not each independently scored.

### Deferred (later phases)
ML-driven seasonality learned from real datasets; persona/segment-specific
responses; supply-chain disruptions; per-locale holiday nuances; Go-executor
parity; formal 1M–1B-row benchmarks.
