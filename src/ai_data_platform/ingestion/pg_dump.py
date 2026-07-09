"""Minimal PostgreSQL dump (`pg_dump --inserts` / plain COPY) reader.

Parses the first ``COPY table (cols…) FROM stdin;`` block and its tab-delimited
data rows up to the terminating ``\\.`` marker into an Arrow table. This is a
pragmatic subset — full SQL dumps are not a data interchange format, so anything
beyond a COPY block (INSERT statements, custom-format archives) is rejected with
guidance to export as CSV/Parquet instead.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ai_data_platform.core.exceptions import IngestionError

_COPY = re.compile(r"COPY\s+([^\s(]+)\s*\(([^)]*)\)\s+FROM\s+stdin;", re.IGNORECASE)
_PG_NULL = "\\N"


def load_pg_copy_block(path: str, options: dict[str, Any] | None = None) -> tuple[Any, str]:
    options = options or {}
    import pyarrow as pa

    text = Path(path).expanduser().read_text(encoding=options.get("encoding", "utf-8"), errors="replace")
    m = _COPY.search(text)
    if not m:
        raise IngestionError(
            "No COPY … FROM stdin block found in the SQL dump.",
            hint="Re-export the table as CSV or Parquet; full pg_dump SQL isn't directly queryable.",
        )
    table_name = m.group(1).split(".")[-1].strip('"')
    columns = [c.strip().strip('"') for c in m.group(2).split(",")]

    body = text[m.end():]
    rows: list[dict[str, Any]] = []
    for line in body.splitlines():
        if line == "\\.":
            break
        if not line:
            continue
        values = line.split("\t")
        if len(values) != len(columns):
            continue
        rows.append(
            {c: (None if v == _PG_NULL else v) for c, v in zip(columns, values)}
        )
    if not rows:
        raise IngestionError(f"COPY block for {table_name!r} had no data rows.")
    return pa.Table.from_pylist(rows), table_name
