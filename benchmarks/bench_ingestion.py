"""Ingestion performance benchmark.

Measures ingest (detect + register + profile) and query latency across formats
and sizes. Views over Parquet should register in ~constant time regardless of
size (lazy), while profiling scales with a single scan.

    python benchmarks/bench_ingestion.py --rows 1000000
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
import polars as pl

from ai_data_platform.ingestion import ingest_data
from ai_data_platform.ingestion.engine import IngestionEngine


def _frame(rows: int) -> pl.DataFrame:
    rng = np.random.default_rng(0)
    return pl.DataFrame(
        {
            "id": np.arange(rows),
            "region": rng.choice(["NA", "EU", "APAC", "LATAM"], rows),
            "amount": np.round(rng.lognormal(4, 0.6, rows), 2),
            "ts": rng.integers(1_700_000_000, 1_760_000_000, rows),
        }
    )


def _time(fn) -> tuple[object, float]:
    t = time.perf_counter()
    out = fn()
    return out, (time.perf_counter() - t) * 1000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=1_000_000)
    args = ap.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="adp-bench-"))
    try:
        df = _frame(args.rows)
        csv_path = workdir / "data.csv"
        pq_path = workdir / "data.parquet"
        df.write_csv(csv_path)
        df.write_parquet(pq_path)

        print(f"{'stage':<28}{'ms':>12}")
        print("-" * 40)
        for label, src in (("ingest csv (view)", csv_path), ("ingest parquet (view)", pq_path)):
            r, ms = _time(lambda s=src: ingest_data(str(s), options={"project": str(workdir)}))
            print(f"{label:<28}{ms:>12.1f}   ({r['row_count']:,} rows)")

        eng = IngestionEngine(str(workdir))
        _, ms = _time(
            lambda: eng.query("SELECT region, count(*), sum(amount) FROM data GROUP BY 1")
        )
        print(f"{'query group-by':<28}{ms:>12.1f}")
        _, ms = _time(lambda: eng.query("SELECT * FROM data WHERE amount > 100", max_rows=1000))
        print(f"{'query filter (limit 1k)':<28}{ms:>12.1f}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
