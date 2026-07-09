# Examples

| Project | Goal |
|---------|------|
| [retail-ecommerce](retail-ecommerce/) | **Sales performance analysis** — 3 years of orders, generate parquet, load to Snowflake |

```bash
cd retail-ecommerce
python make_data.py          # seed CSVs (2023–2025)
adp scan && adp profile
adp generate-data --rows-per-table "customers=5000,products=500,orders=200000,transactions=185000"
adp load
```

See [retail-ecommerce/README.md](retail-ecommerce/README.md).
