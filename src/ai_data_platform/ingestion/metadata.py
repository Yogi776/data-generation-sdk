"""Metadata assembly & registry.

Builds the final ingest report and persists a per-source metadata JSON plus a
manifest under ``.adp/ingestion/`` so later sessions (and the `adp query`
command) know which tables/views exist and how they were created.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_data_platform.core.paths import adp_dir

_REGISTRY_DIR = "ingestion"
_MANIFEST = "manifest.json"


def registry_dir(root: str | Path) -> Path:
    d = adp_dir(root) / _REGISTRY_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def build_report(
    *,
    source_path: str,
    detected_format: str,
    table_name: str,
    relation_kind: str,
    persisted: bool,
    profile_result: dict[str, Any],
    quality_warnings: list[dict[str, Any]],
    sql_examples: list[dict[str, str]],
    create_statements: dict[str, str],
    profiling_sql: str,
    quality_sql: list[dict[str, str]],
    schema_export: str,
    documentation: str,
    detection_notes: list[str],
    excel_sheets: list[str] | None = None,
    sheet_used: str | None = None,
) -> dict[str, Any]:
    return {
        "source_path": source_path,
        "detected_format": detected_format,
        "table_name": table_name,
        "relation_kind": relation_kind,  # view | table
        "persisted": persisted,
        "row_count": profile_result["row_count"],
        "column_count": profile_result["column_count"],
        "schema": profile_result["schema"],
        "profile": profile_result["profile"],
        "quality_warnings": quality_warnings,
        "sample_rows": profile_result["sample_rows"],
        "sql_examples": sql_examples,
        "generated": {
            "create_view": create_statements["create_view"],
            "create_table_as": create_statements["create_table_as"],
            "applied_ddl": create_statements["applied_ddl"],
            "profiling_sql": profiling_sql,
            "quality_sql": quality_sql,
            "schema_export_json": schema_export,
            "documentation_markdown": documentation,
        },
        "detection_notes": detection_notes,
        "excel_sheets": excel_sheets or [],
        "sheet_used": sheet_used,
        "ingested_at": datetime.now(UTC).isoformat(),
    }


def persist_report(root: str | Path, report: dict[str, Any]) -> Path:
    d = registry_dir(root)
    path = d / f"{report['table_name']}.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    _update_manifest(d, report)
    return path


def _update_manifest(d: Path, report: dict[str, Any]) -> None:
    manifest_path = d / _MANIFEST
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
    manifest[report["table_name"]] = {
        "source_path": report["source_path"],
        "detected_format": report["detected_format"],
        "relation_kind": report["relation_kind"],
        "row_count": report["row_count"],
        "column_count": report["column_count"],
        "ingested_at": report["ingested_at"],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")


def load_manifest(root: str | Path) -> dict[str, Any]:
    path = registry_dir(root) / _MANIFEST
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
