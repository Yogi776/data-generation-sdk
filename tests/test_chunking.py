"""Tests for generation chunk sizing."""

from __future__ import annotations

from ai_data_platform.generator.chunking import effective_chunk_rows


def test_effective_chunk_rows_small_table() -> None:
    assert effective_chunk_rows(100_000, 50_000) == 100_000


def test_effective_chunk_rows_medium_table() -> None:
    assert effective_chunk_rows(100_000, 2_000_000) == 250_000


def test_effective_chunk_rows_large_table() -> None:
    assert effective_chunk_rows(100_000, 10_000_000) == 500_000


def test_effective_chunk_rows_respects_higher_config() -> None:
    assert effective_chunk_rows(1_000_000, 10_000_000) == 1_000_000
