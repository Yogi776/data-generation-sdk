"""Ingestion — large files: lazy views (no full load), streaming query, limits."""

from __future__ import annotations

import time
from pathlib import Path

from ai_data_platform.ingestion import ingest_data
from ai_data_platform.ingestion.engine import IngestionEngine

from _ingest_helpers import write_parquet


def test_large_parquet_view_is_lazy(tmp_path: Path) -> None:
    # 250k rows: registering a view must be fast and must not load the file.
    f = write_parquet(tmp_path / "big.parquet", rows=250_000)
    start = time.perf_counter()
    r = ingest_data(str(f), table_name="big", options={"project": str(tmp_path)})
    elapsed = time.perf_counter() - start
    assert r["row_count"] == 250_000
    assert r["relation_kind"] == "view"
    # generous ceiling — profiling scans, but a view + SUMMARIZE stays well under this
    assert elapsed < 30


def test_streaming_aggregate(tmp_path: Path) -> None:
    f = write_parquet(tmp_path / "big.parquet", rows=200_000)
    ingest_data(str(f), table_name="big", options={"project": str(tmp_path)})
    res = IngestionEngine(str(tmp_path)).query(
        "SELECT region, count(*) n, sum(amount) rev FROM big GROUP BY 1 ORDER BY rev DESC"
    )
    assert sum(row["n"] for row in res["rows"]) == 200_000


def test_query_row_limit_truncation(tmp_path: Path) -> None:
    f = write_parquet(tmp_path / "big.parquet", rows=50_000)
    ingest_data(str(f), table_name="big", options={"project": str(tmp_path)})
    res = IngestionEngine(str(tmp_path)).query("SELECT * FROM big", max_rows=100)
    assert res["row_count"] == 100
    assert res["truncated"] is True
