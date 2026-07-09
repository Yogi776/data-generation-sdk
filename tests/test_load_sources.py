"""Tests for staging path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_data_platform.core.exceptions import LoadError
from ai_data_platform.load.local_sources import (
    detect_staging_format,
    resolve_source_table,
    resolve_source_uri,
    staging_file_path,
)


def test_detect_parquet(tmp_path: Path) -> None:
    (tmp_path / "a.parquet").write_bytes(b"x")
    assert detect_staging_format(tmp_path, None) == "parquet"


def test_resolve_source_uri_parquet(tmp_path: Path) -> None:
    p = tmp_path / "a.parquet"
    p.write_bytes(b"x")
    uri = resolve_source_uri(tmp_path, "a", "parquet")
    assert uri.startswith("parquet://")
    assert uri.endswith("a.parquet")


def test_resolve_source_table() -> None:
    assert resolve_source_table("dim_customer", "parquet") == "dim_customer#parquet"
    assert resolve_source_table("dim_customer", "duckdb") == "dim_customer"
    assert resolve_source_table("dim_customer", "csv") == "dim_customer"


def test_staging_file_missing(tmp_path: Path) -> None:
    with pytest.raises(LoadError):
        staging_file_path(tmp_path, "missing", "parquet")
