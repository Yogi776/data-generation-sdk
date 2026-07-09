"""Ingestion — JSON arrays, NDJSON, and nested flattening."""

from __future__ import annotations

import json
from pathlib import Path

from ai_data_platform.ingestion import ingest_data
from ai_data_platform.ingestion.detector import detect
from ai_data_platform.ingestion.engine import IngestionEngine

from _ingest_helpers import make_frame


def test_ingest_json_array(tmp_path: Path) -> None:
    f = tmp_path / "orders.json"
    rows = make_frame(80).to_dicts()
    f.write_text(json.dumps(rows), encoding="utf-8")
    r = ingest_data(str(f), table_name="orders", options={"project": str(tmp_path)})
    assert r["detected_format"] == "json"
    assert r["row_count"] == 80


def test_ingest_ndjson(tmp_path: Path) -> None:
    f = tmp_path / "events.ndjson"
    make_frame(60).write_ndjson(f)
    d = detect(str(f))
    assert d.fmt == "ndjson"
    r = ingest_data(str(f), table_name="events", options={"project": str(tmp_path)})
    assert r["row_count"] == 60


def test_flatten_nested_json(tmp_path: Path) -> None:
    f = tmp_path / "nested.json"
    records = [
        {"id": 1, "customer": {"name": "A", "geo": {"city": "Pune"}}, "total": 10.0},
        {"id": 2, "customer": {"name": "B", "geo": {"city": "Delhi"}}, "total": 20.0},
    ]
    f.write_text(json.dumps(records), encoding="utf-8")
    r = ingest_data(str(f), table_name="nested", options={"project": str(tmp_path), "flatten": True})
    cols = {c["name"] for c in r["schema"]}
    assert "customer.name" in cols and "customer.geo.city" in cols
    # flattened JSON is materialized
    assert r["relation_kind"] == "table"
    res = IngestionEngine(str(tmp_path)).query(
        'SELECT "customer.geo.city" AS city, count(*) n FROM nested GROUP BY 1'
    )
    assert res["row_count"] == 2
