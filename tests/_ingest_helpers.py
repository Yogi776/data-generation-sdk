"""Shared helpers for ingestion tests (not collected by pytest)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl


def make_frame(rows: int = 200, seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    return pl.DataFrame(
        {
            "id": np.arange(1, rows + 1),
            "region": rng.choice(["NA", "EU", "APAC", "LATAM"], rows),
            "amount": np.round(rng.lognormal(4.0, 0.6, rows), 2),
            "qty": rng.integers(1, 50, rows),
            "order_date": [
                f"2025-{m:02d}-{d:02d}"
                for m, d in zip(rng.integers(1, 13, rows), rng.integers(1, 28, rows))
            ],
        }
    )


def write_csv(path: Path, rows: int = 200) -> Path:
    make_frame(rows).write_csv(path)
    return path


def write_parquet(path: Path, rows: int = 200) -> Path:
    make_frame(rows).write_parquet(path)
    return path
