#!/usr/bin/env bash
# Generate 3-year retail sales data and validate (no Snowflake load).
set -euo pipefail
cd "$(dirname "$0")"

ROWS_PER_TABLE="${ROWS_PER_TABLE:-customers=5000,products=500,orders=200000,transactions=185000}"

echo "==> Seed CSVs (2023–2025)"
python3 make_data.py

echo "==> Scan + profile"
adp scan
adp profile

echo "==> Generate synthetic data"
adp generate-data --rows-per-table "$ROWS_PER_TABLE"

echo "==> Quality check"
adp quality-check

echo "Done. Load with: adp load doctor && adp load"
