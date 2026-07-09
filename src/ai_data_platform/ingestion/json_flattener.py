"""JSON flattening options.

DuckDB's ``read_json_auto`` handles most JSON/NDJSON, inferring STRUCT/LIST
columns for nested data. When the caller wants a flat relational shape,
``flatten=True`` normalizes nested objects into dotted columns (and can explode
top-level record arrays) using pandas' json_normalize, returning an Arrow table.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa

from ai_data_platform.core.exceptions import IngestionError


def flatten_json_file(
    path: str, options: dict[str, Any] | None = None
) -> pa.Table:
    """Load a JSON/NDJSON file and return a flattened Arrow table.

    options:
      record_path: key holding the list of records (e.g. "data.items").
      sep: nested-key separator (default ".").
      max_level: max nesting depth to flatten (default: full).
      ndjson: treat as newline-delimited (auto-detected if omitted).
    """
    options = options or {}
    p = Path(path).expanduser()
    try:
        import pandas as pd
    except ImportError as e:  # pragma: no cover
        raise IngestionError(
            "JSON flattening needs pandas.",
            hint="pip install 'ai-data-platform[ingest]'",
        ) from e

    sep = str(options.get("sep", "."))
    max_level = options.get("max_level")
    ndjson = options.get("ndjson")

    text = p.read_text(encoding=options.get("encoding", "utf-8"), errors="replace")
    records = _parse_records(text, ndjson)

    record_path = options.get("record_path")
    if record_path:
        for key in str(record_path).split("."):
            records = _dig(records, key)

    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        raise IngestionError("Flattened JSON did not resolve to a list of records.")

    df = pd.json_normalize(records, sep=sep, max_level=max_level)
    df.columns = [str(c) for c in df.columns]
    if df.empty:
        raise IngestionError("No records to ingest after flattening.")
    return pa.Table.from_pandas(df, preserve_index=False)


def _parse_records(text: str, ndjson: bool | None) -> Any:
    stripped = text.strip()
    if ndjson is True or (ndjson is None and _looks_ndjson(stripped)):
        return [json.loads(line) for line in stripped.splitlines() if line.strip()]
    return json.loads(stripped)


def _looks_ndjson(text: str) -> bool:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return False
    # Multiple standalone JSON objects, not a single array.
    return not text.lstrip().startswith("[") and lines[0].lstrip().startswith("{")


def _dig(obj: Any, key: str) -> Any:
    if isinstance(obj, dict) and key in obj:
        return obj[key]
    raise IngestionError(f"record_path key {key!r} not found in JSON.")
