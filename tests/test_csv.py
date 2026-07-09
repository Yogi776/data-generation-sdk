"""Ingestion — CSV/TSV, delimiter/header/encoding detection, gzip, profiling."""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from ai_data_platform.core.exceptions import UnsafeSQLError
from ai_data_platform.ingestion import ingest_data
from ai_data_platform.ingestion.detector import detect
from ai_data_platform.ingestion.engine import IngestionEngine

from _ingest_helpers import make_frame, write_csv


def test_detect_csv_delimiter_and_header(tmp_path: Path) -> None:
    f = write_csv(tmp_path / "orders.csv")
    d = detect(str(f))
    assert d.fmt == "csv"
    assert d.delimiter == ","
    assert d.has_header is True
    assert d.encoding


def test_detect_tsv(tmp_path: Path) -> None:
    f = tmp_path / "orders.tsv"
    make_frame(50).write_csv(f, separator="\t")
    d = detect(str(f))
    assert d.fmt in ("tsv", "csv")
    assert d.delimiter == "\t"


def test_ingest_csv_view_and_profile(tmp_path: Path) -> None:
    f = write_csv(tmp_path / "orders.csv", rows=300)
    r = ingest_data(str(f), table_name="orders", options={"project": str(tmp_path)})
    assert r["detected_format"] == "csv"
    assert r["relation_kind"] == "view"  # native format, not persisted
    assert r["row_count"] == 300
    assert r["column_count"] == 5
    cols = {c["name"] for c in r["schema"]}
    assert {"id", "region", "amount", "qty", "order_date"} == cols
    amount = r["profile"]["columns"]["amount"]
    assert amount["min"] is not None and amount["avg"] is not None
    assert r["sql_examples"]
    assert r["generated"]["create_view"].startswith("CREATE VIEW")
    assert r["generated"]["documentation_markdown"].startswith("# Data dictionary")


def test_ingest_gzip_csv(tmp_path: Path) -> None:
    raw = make_frame(100).write_csv()
    gz = tmp_path / "orders.csv.gz"
    with gzip.open(gz, "wt") as fh:
        fh.write(raw)
    d = detect(str(gz))
    assert d.fmt == "csv" and d.compression == "gzip"
    r = ingest_data(str(gz), table_name="orders_gz", options={"project": str(tmp_path)})
    assert r["row_count"] == 100


def test_persist_creates_table(tmp_path: Path) -> None:
    f = write_csv(tmp_path / "orders.csv")
    r = ingest_data(str(f), table_name="orders_p", persist=True, options={"project": str(tmp_path)})
    assert r["relation_kind"] == "table"
    assert r["persisted"] is True


def test_query_after_ingest(tmp_path: Path) -> None:
    f = write_csv(tmp_path / "orders.csv", rows=400)
    ingest_data(str(f), table_name="orders", options={"project": str(tmp_path)})
    eng = IngestionEngine(str(tmp_path))
    res = eng.query("SELECT region, count(*) n FROM orders GROUP BY 1 ORDER BY n DESC")
    assert res["columns"][0] == "region"
    assert res["row_count"] >= 1
    assert "orders" in eng.list_sources()


def test_query_guard_blocks_mutation(tmp_path: Path) -> None:
    f = write_csv(tmp_path / "orders.csv")
    ingest_data(str(f), table_name="orders", options={"project": str(tmp_path)})
    with pytest.raises(UnsafeSQLError):
        IngestionEngine(str(tmp_path)).query("DROP TABLE orders")
