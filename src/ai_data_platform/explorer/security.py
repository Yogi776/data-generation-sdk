"""Query governance for the DuckDB explorer.

Defense in depth — no single control is trusted alone:

1. **Read-only connection** — the engine opens DuckDB with ``read_only=True``,
   so DDL/DML physically cannot run regardless of the SQL text.
2. **Statement guard** (:func:`guard_select`) — only a single ``SELECT``/``WITH``
   is accepted; a denylist rejects mutation, attach/copy/install/pragma/set, and
   filesystem-touching functions.
3. **Result bounding** (:func:`wrap_with_limit`) — the query is wrapped so at
   most ``max_rows + 1`` rows return (the extra row detects truncation), with an
   optional reservoir sample for large outputs.
4. **Timeout + scan guard + query log** — enforced by the engine.
"""

from __future__ import annotations

import re

from ai_data_platform.core.exceptions import UnsafeSQLError

# Keywords that must never appear in an explorer query. COPY is blocked here even
# though it can be read-only, because ``COPY ... TO`` writes files; the sanctioned
# path for writing results is export_query_result (server-controlled, sandboxed).
_FORBIDDEN_KEYWORDS = re.compile(
    r"(?is)\b("
    r"insert|update|delete|drop|alter|create|truncate|grant|revoke|"
    r"copy|attach|detach|call|merge|replace|vacuum|pragma|set|reset|"
    r"install|load|export|import|checkpoint|use"
    r")\b"
)

# File/host reaching functions — even inside a SELECT these can exfiltrate or
# read arbitrary paths. Registered data is reached through views, not ad-hoc
# readers, so these are unnecessary for legitimate exploration.
_FORBIDDEN_FUNCTIONS = re.compile(
    r"(?is)\b("
    r"read_csv|read_csv_auto|read_parquet|read_json|read_json_auto|read_ndjson|"
    r"read_text|read_blob|parquet_scan|csv_scan|glob|"
    r"httpfs|read_parquet_mr|delta_scan|iceberg_scan"
    r")\s*\("
)


def guard_select(sql: str) -> str:
    """Return the sanitized single-statement SELECT, or raise UnsafeSQLError."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise UnsafeSQLError("Empty SQL statement.")
    if ";" in stripped:
        raise UnsafeSQLError(
            "Multiple SQL statements are not allowed.",
            hint="Submit exactly one SELECT/WITH statement.",
        )
    head = stripped.split(None, 1)[0].lower()
    if head not in ("select", "with"):
        raise UnsafeSQLError(
            f"Only SELECT queries are allowed (got {head!r}).",
            hint="The explorer is read-only by design.",
        )
    if _FORBIDDEN_KEYWORDS.search(stripped):
        raise UnsafeSQLError(
            "Statement contains a forbidden keyword.",
            hint="The explorer is read-only; DDL/DML and ATTACH/COPY/SET are blocked.",
        )
    if _FORBIDDEN_FUNCTIONS.search(stripped):
        raise UnsafeSQLError(
            "Direct file/remote reader functions are not allowed.",
            hint="Query the registered table names (views) instead of raw file readers.",
        )
    return stripped


def wrap_with_limit(sql: str, *, max_rows: int, sample: bool) -> str:
    """Wrap a validated SELECT so it returns at most ``max_rows + 1`` rows.

    The +1 lets the engine detect truncation. When ``sample`` is set a uniform
    reservoir sample is taken so large results stay representative rather than
    just the first N rows.
    """
    inner = sql.rstrip(";")
    fetch = max_rows + 1
    if sample:
        return f"SELECT * FROM ({inner}) AS _adp_q USING SAMPLE reservoir({fetch} ROWS)"
    return f"SELECT * FROM ({inner}) AS _adp_q LIMIT {fetch}"
