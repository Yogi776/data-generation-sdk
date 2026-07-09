# Retail e-commerce — sales performance (3 years → Snowflake)

Synthetic **3-year** retail dataset for **sales performance analysis**: revenue trends, YoY growth, category/channel mix, segment value, and payment analytics.

```
customers ──┐
products  ────┼──► orders (order_date 2023–2025) ──► transactions
```

## What you get

| Table | Role | Typical generated volume |
|-------|------|--------------------------|
| `customers` | Dimension (segment, city, signup) | 5,000 |
| `products` | Dimension (category, price) | 500 |
| `orders` | Fact — line items with `order_date`, `region`, `channel` | 200,000 |
| `transactions` | Fact — payments | ~185,000 |

Date range in generated data: **2023-01-01 → 2025-12-31** (learned from seed CSVs).

## Prerequisites

```bash
pip install 'ai-data-platform[load]'   # load extra includes ingestr
cp .env.example .env                   # set SNOWFLAKE_URI
```

## Full pipeline

```bash
cd ai-data-platform/examples/retail-ecommerce

# 1) Seed CSVs (3 years of sample orders for profiling)
python make_data.py

# 2) Learn schema + distributions
adp scan
adp profile

# 3) Generate synthetic parquet (~3 years of sales at scale)
adp generate-data --rows-per-table \
  "customers=5000,products=500,orders=200000,transactions=185000"

adp quality-check

# 4) Load to Snowflake
adp load doctor
adp load
```

Or run everything (except load) via:

```bash
./run_pipeline.sh
```

## Snowflake

Tables land in `Retail.PUBLIC`:

- `PUBLIC.customers`
- `PUBLIC.products`
- `PUBLIC.orders`
- `PUBLIC.transactions`

Run the KPI workbook:

```bash
# Snowflake worksheet or snowsql -f analytics/sales_performance.sql
```

### Example KPIs

1. Monthly revenue & order volume  
2. Year-over-year growth by month  
3. Category revenue mix  
4. Region × channel performance  
5. Customer segment LTV proxy  
6. Payment method mix  

## Smaller dev run

```bash
python make_data.py
adp scan && adp profile
adp generate-data --rows 5000
adp quality-check
```

## Project layout

```
retail-ecommerce/
├── adp.yaml                    # project + Snowflake destination
├── make_data.py                # build seed CSVs (2023–2025)
├── run_pipeline.sh             # scan → profile → generate → quality
├── data/                       # seed CSVs (generated)
├── analytics/
│   └── sales_performance.sql   # Snowflake analysis queries
└── output/                     # parquet (generated)
```

No LLM API key required for generation.
