"""Destination catalog tests."""

from __future__ import annotations

from ai_data_platform.load.destinations import INGESTR_DESTINATIONS, lookup_uri


def test_destination_catalog_count() -> None:
    assert len(INGESTR_DESTINATIONS) == 29


def test_lookup_snowflake_uri() -> None:
    info = lookup_uri("snowflake://user@acct/db/schema")
    assert info is not None
    assert info.id == "snowflake"
