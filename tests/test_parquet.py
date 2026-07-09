"""Ingestion — Parquet single file, folders, hive partitions, predicate pushdown."""

from __future__ import annotations

from pathlib import Path

from ai_data_platform.ingestion import ingest_data
from ai_data_platform.ingestion.detector import detect
from ai_data_platform.ingestion.engine import IngestionEngine

from _ingest_helpers import make_frame, write_parquet


def test_ingest_single_parquet(tmp_path: Path) -> None:
    f = write_parquet(tmp_path / "orders.parquet", rows=500)
    r = ingest_data(str(f), table_name="orders", options={"project": str(tmp_path)})
    assert r["detected_format"] == "parquet"
    assert r["relation_kind"] == "view"
    assert r["row_count"] == 500


def test_ingest_parquet_folder(tmp_path: Path) -> None:
    folder = tmp_path / "orders"
    folder.mkdir()
    write_parquet(folder / "part-0.parquet", rows=100)
    write_parquet(folder / "part-1.parquet", rows=150)
    d = detect(str(folder))
    assert d.fmt == "parquet" and d.is_folder
    r = ingest_data(str(folder), table_name="orders_all", options={"project": str(tmp_path)})
    assert r["row_count"] == 250


def test_ingest_hive_partitioned(tmp_path: Path) -> None:
    base = tmp_path / "sales"
    for region in ("NA", "EU"):
        part = base / f"region={region}"
        part.mkdir(parents=True)
        make_frame(40).drop("region").write_parquet(part / "data.parquet")
    d = detect(str(base))
    assert d.partitioned is True
    assert "region" in d.partition_keys
    r = ingest_data(str(base), table_name="sales", options={"project": str(tmp_path)})
    assert r["row_count"] == 80
    # partition column is available for predicate pushdown
    res = IngestionEngine(str(tmp_path)).query("SELECT count(*) c FROM sales WHERE region = 'NA'")
    assert res["rows"][0]["c"] == 40


def test_predicate_pushdown_query(tmp_path: Path) -> None:
    f = write_parquet(tmp_path / "orders.parquet", rows=1000)
    ingest_data(str(f), table_name="orders", options={"project": str(tmp_path)})
    res = IngestionEngine(str(tmp_path)).query("SELECT count(*) c FROM orders WHERE amount > 0")
    assert res["rows"][0]["c"] == 1000
