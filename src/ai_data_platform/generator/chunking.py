"""Chunk-size helpers for large-table generation."""

from __future__ import annotations


def effective_chunk_rows(configured: int, table_rows: int) -> int:
    """Scale chunk size for large tables — fewer row groups improves load throughput."""
    if table_rows >= 10_000_000:
        return max(configured, 500_000)
    if table_rows >= 1_000_000:
        return max(configured, 250_000)
    return configured
