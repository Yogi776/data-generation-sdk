"""Tests for DuckDB streaming quality checks."""

from __future__ import annotations

import polars as pl

from ai_data_platform.sdk import ADPClient


def test_duckdb_quality_matches_polars(profiled_project: ADPClient) -> None:
    """DuckDB engine produces same pass/fail verdicts as in-memory Polars."""
    from ai_data_platform.core.paths import safe_resolve
    from ai_data_platform.quality.checks import run_quality_checks
    from ai_data_platform.quality.duckdb_checks import run_quality_checks_on_dir

    profiled_project.generate_data(rows=500, output_format="parquet")
    out = safe_resolve(profiled_project.root, "output")
    data = {f.stem: pl.read_parquet(f) for f in out.glob("*.parquet")}
    polars_report = run_quality_checks(profiled_project.catalog, data)
    duck_report = run_quality_checks_on_dir(profiled_project.catalog, out)
    assert duck_report["engine"] == "duckdb"
    assert duck_report["quality_score"] == polars_report["quality_score"]
