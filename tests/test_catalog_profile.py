"""Catalog + scan + profiler behavior."""

from __future__ import annotations

import pytest

from ai_data_platform.core.exceptions import TableNotFoundError
from ai_data_platform.profiler.profiler import classify_pii
from ai_data_platform.sdk import ADPClient


def test_scan_populates_catalog(scanned_project: ADPClient) -> None:
    tables = scanned_project.list_tables()
    assert {t["table"] for t in tables} == {"customers", "orders"}
    orders = scanned_project.get_table("orders")
    assert {c["name"] for c in orders["columns"]} >= {"order_id", "customer_id", "total_amount"}


def test_scan_finds_fk_candidate(scanned_project: ADPClient) -> None:
    rels = scanned_project.catalog.get_relationships()
    assert any(
        r["child_table"] == "orders"
        and r["parent_table"] == "customers"
        and r["child_column"] == "customer_id"
        for r in rels
    )


def test_rescan_is_idempotent(scanned_project: ADPClient) -> None:
    before = len(scanned_project.list_tables())
    scanned_project.scan()
    assert len(scanned_project.list_tables()) == before


def test_profile_sets_pk_and_stats(profiled_project: ADPClient) -> None:
    orders = profiled_project.get_table("orders")
    pk = [c["name"] for c in orders["columns"] if c["primary_key"]]
    assert pk == ["order_id"]
    prof = profiled_project.catalog.get_latest_profile("orders")
    assert prof is not None
    amount = next(c for c in prof["columns"] if c["name"] == "total_amount")
    assert amount["min"] > 0 and amount["mean"] > 0
    assert amount["null_ratio"] == 0.0


def test_profile_confirms_fk(profiled_project: ADPClient) -> None:
    rels = profiled_project.catalog.get_relationships()
    fk = next(r for r in rels if r["child_table"] == "orders")
    assert fk["confidence"] > 0.9  # inclusion-confirmed


def test_pii_detection(profiled_project: ADPClient) -> None:
    customers = profiled_project.get_table("customers")
    by_name = {c["name"]: c for c in customers["columns"]}
    assert by_name["email"]["pii"] == "likely"
    assert by_name["city"]["pii"] == "none"


def test_pii_date_not_phone() -> None:
    dates = [f"2025-01-{d:02d}" for d in range(1, 30)]
    level, _cat, _conf = classify_pii("order_date", dates)
    assert level == "none"


def test_search(profiled_project: ADPClient) -> None:
    hits = profiled_project.search_metadata("customer")
    assert hits
    assert any(h["match"] == "table" for h in hits) or any(h["match"] == "column" for h in hits)


def test_unknown_table_raises(scanned_project: ADPClient) -> None:
    with pytest.raises(TableNotFoundError):
        scanned_project.get_table("ghosts")
