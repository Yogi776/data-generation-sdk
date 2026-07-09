# ADP Data Store — Launch SKU Catalog

First 5 SKUs for the curated data store. Package from existing `examples/` — generate at listed row counts, bundle with quality report and license.

**Store positioning:** Business-ready synthetic data — FK-safe, quality-scored, commercially licensed, spec included.

---

## SKU 1 — Retail Seasonal Starter

| Field | Value |
|-------|-------|
| **SKU ID** | `ADP-RETAIL-100K` |
| **Price** | **$19** one-time |
| **License** | Commercial (single org, unlimited users) |
| **Target buyer** | Students, POC, indie developers |

### Title
**Retail Seasonal Demo Data — 100K Orders (FK-Safe, India Holidays)**

### Description
Ready-to-use synthetic retail dataset with **realistic seasonality** — weekend lift, Diwali/Black Friday peaks, hourly patterns, and 18% YoY growth. No production data. No PII.

**Perfect for:** Dashboard prototypes, SQL practice, BI tool demos, coursework.

**Tables (100K rows each unless noted):**
- `fact_orders` — 100,000 rows, 11 columns (order_id, timestamps, revenue, units, channel, city…)
- `fact_payments` — 100,000 rows, 4 columns (FK → orders)
- `fact_shipments` — 100,000 rows, 3 columns (FK → orders)

**Quality:** 100/100 score · 0 orphan FKs · seasonality validated

### What's included

```
retail-seasonal-100k/
├── data/
│   ├── fact_orders.parquet
│   ├── fact_payments.parquet
│   ├── fact_shipments.parquet
│   ├── fact_orders.csv          # optional CSV mirror
│   └── generated.duckdb         # all tables, query-ready
├── spec.yaml                    # regenerate or extend with ADP
├── quality-report.md            # full check evidence
├── data-dictionary.md           # column definitions
├── sample-queries.sql           # revenue by city, seasonal KPIs
└── LICENSE.pdf                  # commercial use terms
```

**Source spec:** `benchmarks/fixtures/seasonal-retail-spec.yaml`  
**Generate command:** `adp apply-spec spec.yaml && adp generate-data --rows 100000 --seed 42`

### Free sample
1,000 rows per table — [GitHub sample link TBD]

---

## SKU 2 — Retail Seasonal Pro

| Field | Value |
|-------|-------|
| **SKU ID** | `ADP-RETAIL-1M` |
| **Price** | **$99** one-time |
| **License** | Commercial |
| **Target buyer** | BI agencies, sales engineers, analytics consultants |

### Title
**Retail Seasonal Pro — 1M Rows + Cube Semantic Model + KPI Pack**

### Description
Full retail demo environment for **stakeholder presentations** and **client workshops**. 1 million orders with FK-safe payments and shipments, holiday seasonality, and a pre-built **Cube.js semantic model** for instant dashboard connection.

**Perfect for:** ThoughtSpot/Looker/Power BI demos, client POCs, seasonal analytics storytelling.

**Tables:** 1M rows × 3 tables (3M total rows)

**Bundles:**
- Parquet + CSV + DuckDB
- `model/cubes.yml` — Cube.js semantic layer (revenue, orders, dimensions)
- 10 sample KPI SQL queries with expected result ranges
- Seasonality daily CSV for chart validation

### What's included

```
retail-seasonal-1m/
├── data/                        # parquet, csv, duckdb (3M rows total)
├── spec.yaml
├── model/
│   └── cubes.yml                # Cube.js — facts, dims, measures
├── quality-report.md
├── seasonality-report.md
├── data-dictionary.md
├── kpi-pack/
│   ├── revenue_by_city.sql
│   ├── orders_by_channel.sql
│   ├── seasonal_daily_trend.sql
│   └── README.md                # expected KPI ranges
└── LICENSE.pdf
```

**Benchmark:** Generated in ~20s on 8-core machine · 171K rows/s throughput

---

## SKU 3 — E-Commerce Full Stack

| Field | Value |
|-------|-------|
| **SKU ID** | `ADP-ECOM-500K` |
| **Price** | **$79** one-time |
| **License** | Commercial |
| **Target buyer** | E-commerce startups, marketplace builders, ML engineers |

### Title
**E-Commerce Full Stack — Customers, Products, Orders, Transactions (500K)**

### Description
Four-table e-commerce star schema with **complete referential integrity**. Customers browse products, place orders, and complete transactions — realistic names, addresses, product categories, and order values.

**Perfect for:** Recommendation engine prototypes, cart abandonment analysis, customer 360 demos.

**Tables:**
- `customers` — 50,000 rows
- `products` — 5,000 rows
- `orders` — 200,000 rows
- `transactions` — 500,000 rows

### What's included

```
ecommerce-fullstack-500k/
├── data/
│   ├── customers.parquet
│   ├── products.parquet
│   ├── orders.parquet
│   └── transactions.parquet
├── spec.yaml                    # from retail-ecommerce pattern
├── quality-report.md            # 100/100 validated
├── data-dictionary.md
├── erd.png                      # entity relationship diagram
├── sample-queries.sql
└── LICENSE.pdf
```

**Source:** `examples/retail-ecommerce/` (validated 100/100)

---

## SKU 4 — SaaS CRM Enterprise Dataset

| Field | Value |
|-------|-------|
| **SKU ID** | `ADP-SAAS-50K` |
| **Price** | **$149** one-time |
| **License** | Commercial |
| **Target buyer** | B2B SaaS companies, CRM vendors, churn model builders |

### Title
**SaaS CRM Dataset — 50K Customers, 98 Columns, KYC + Transactions**

### Description
Production-grade **customer 360** synthetic dataset. Dimension table with 98 columns (demographics, firmographics, KYC, preferences) plus fact transactions with one-to-many and one-to-one relationships. Built for complex CRM, billing, and compliance demos.

**Perfect for:** Salesforce/HubSpot-style demos, churn prediction, KYC workflow testing, data warehouse POCs.

**Tables:**
- `dim_customer` — 50,000 rows, 98 columns
- `fact_transaction` — 500,000 rows
- `customer_kyc` — 50,000 rows (1:1 with customer)

### What's included

```
saas-crm-50k/
├── data/
│   ├── dim_customer.parquet
│   ├── fact_transaction.parquet
│   ├── customer_kyc.parquet
│   └── generated.duckdb
├── spec.yaml
├── quality-report.md
├── data-dictionary.md           # all 98 columns documented
├── sample-queries.sql           # churn, LTV, segment analysis
└── LICENSE.pdf
```

**Source:** curated SKU (not in `examples/` — use `examples/retail-ecommerce/` for the walkthrough)

---

## SKU 5 — Retail Enterprise + Regenerate Kit

| Field | Value |
|-------|-------|
| **SKU ID** | `ADP-RETAIL-10M` |
| **Price** | **$299** one-time |
| **License** | Commercial (includes regeneration rights) |
| **Target buyer** | Platform engineers, load testing, enterprise QA |

### Title
**Retail Enterprise — 10M Rows + Spec + Regeneration Kit (Performance Grade)**

### Description
**Performance-scale** retail dataset for load testing, pipeline stress tests, and enterprise staging environments. 10 million rows per fact table (30M total). Includes full `spec.yaml`, ADP project config, and documentation to **regenerate at any scale** with `seed=42` for CI reproducibility.

**Perfect for:** Performance testing, data pipeline validation, warehouse load tests, enterprise QA environments.

**Tables:** 10M × 3 = **30 million rows**

**Performance proof:**
- Wall time: ~3 minutes (8-core machine)
- Throughput: 171K rows/s
- Output: ~2.3 GB compressed Parquet
- Quality: 100/100 (27/27 checks)

### What's included

```
retail-enterprise-10m/
├── data/
│   ├── fact_orders.parquet      # ~553 MB
│   ├── fact_payments.parquet    # ~932 MB
│   ├── fact_shipments.parquet   # ~871 MB
│   └── generated.duckdb
├── spec.yaml
├── adp.yaml                     # project config
├── quality-report.md
├── benchmark-report.md          # performance evidence
├── regeneration-guide.md        # scale to 100M with ADP CLI
├── data-dictionary.md
└── LICENSE.pdf                  # includes regeneration rights
```

**Regeneration rights:** Buyer may run ADP locally to regenerate from included `spec.yaml` at any row count for internal use.

---

## SKU comparison

| SKU | Rows (total) | Price | Best for |
|-----|--------------|-------|----------|
| ADP-RETAIL-100K | 300K | $19 | POC, learning |
| ADP-RETAIL-1M | 3M | $99 | BI demos, client workshops |
| ADP-ECOM-500K | 755K | $79 | E-commerce / ML prototypes |
| ADP-SAAS-50K | 600K | $149 | CRM / customer 360 |
| ADP-RETAIL-10M | 30M | $299 | Load test, enterprise QA |

---

## Bundle offer (launch promo)

**Demo-in-a-Box Bundle — $249** (save $77)

Includes: ADP-RETAIL-1M + ADP-ECOM-500K + ADP-SAAS-50K + 1 hour spec customization call

---

## Generation checklist (internal)

Before listing each SKU:

- [ ] Generate with `seed=42` for reproducibility
- [ ] Run `adp quality-check` — score ≥ 95
- [ ] Run `adp seasonality-check` (retail SKUs)
- [ ] Export Parquet + CSV + DuckDB
- [ ] Generate `data-dictionary.md`
- [ ] Attach [DATASET-LICENSE.md](./templates/DATASET-LICENSE.md)
- [ ] Create 1K-row free sample for Gumroad preview
- [ ] Upload to Hugging Face with commercial license metadata

---

## Related

- [DATA-MARKETPLACE.md](./DATA-MARKETPLACE.md) — full marketplace research
- [templates/DATASET-LICENSE.md](./templates/DATASET-LICENSE.md) — license terms
- [PRICING.md](./PRICING.md) — subscription tiers
