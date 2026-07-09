"""Tests for ingestr argv builder and transport."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

from ai_data_platform.load.ingestr import IngestrTransport, build_ingestr_argv
from ai_data_platform.load.types import TableLoadSpec


def test_build_ingestr_argv_replace() -> None:
    spec = TableLoadSpec(
        table="dim_customer",
        source_uri="file:///out",
        source_table="dim_customer.parquet",
        dest_uri="snowflake://u@acct/db",
        dest_table="PUBLIC.dim_customer",
        incremental_strategy="replace",
    )
    argv = build_ingestr_argv(spec)
    assert "--incremental-strategy" in argv
    assert argv[argv.index("--incremental-strategy") + 1] == "replace"


def test_build_ingestr_argv_merge_and_options() -> None:
    spec = TableLoadSpec(
        table="t",
        source_uri="file:///out",
        source_table="t.parquet",
        dest_uri="bigquery://p",
        dest_table="raw.t",
        incremental_strategy="merge",
        primary_key="id",
        ingestr_options={"staging-bucket": "gs://b"},
    )
    argv = build_ingestr_argv(spec)
    assert "--primary-key" in argv
    assert "--staging-bucket" in argv


def test_build_ingestr_argv_source_sql_not_emitted() -> None:
    spec = TableLoadSpec(
        table="t",
        source_uri="postgresql://localhost/db",
        source_table="orders",
        dest_uri="snowflake://acct/db",
        dest_table="PUBLIC.orders",
        source_sql="SELECT * FROM orders",
        is_live_source=True,
    )
    argv = build_ingestr_argv(spec)
    assert "--sql" not in argv


def test_ingestr_transport_dry_run() -> None:
    t = IngestrTransport()
    spec = TableLoadSpec(
        table="t",
        source_uri="file:///o",
        source_table="t.parquet",
        dest_uri="duckdb:///d",
        dest_table="main.t",
    )
    r = t.load_table(spec, dry_run=True)
    assert r.status == "dry_run"


def test_ingestr_transport_mock_runner() -> None:
    proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    runner = MagicMock(return_value=proc)
    t = IngestrTransport(runner=runner)
    spec = TableLoadSpec(
        table="t",
        source_uri="file:///o",
        source_table="t.parquet",
        dest_uri="duckdb:///d",
        dest_table="main.t",
    )
    r = t.load_table(spec, dry_run=False)
    assert r.status == "ok"
    runner.assert_called_once()
