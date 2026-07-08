"""NL->SQL assistant.

Grounding: schema context built from the catalog (names/types/relationships
only — PII-tagged columns contribute no sample values, per ADR-0009).
Safety: strict read-only guard; only single SELECT/WITH statements execute.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from ai_data_platform.config import ModelProviderConfig
from ai_data_platform.core.exceptions import AIExtractionError, UnsafeSQLError
from ai_data_platform.sql.providers import get_provider

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.metadata.catalog import Catalog

_FORBIDDEN = re.compile(
    r"(?is)\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|attach|"
    r"call|merge|replace|vacuum|pragma|set|install|load|export)\b"
)

_SYSTEM_PROMPT = (
    "You are a SQL assistant. Generate a single read-only SQL SELECT statement "
    "(DuckDB dialect) answering the user's question against the described schema. "
    "Respond with JSON only: "
    '{"sql": "...", "explanation": "...", "confidence": 0.0-1.0, "tables_used": ["..."]}. '
    "Never invent tables or columns not present in the schema."
)


def guard_sql(sql: str) -> str:
    """Reject anything that is not a single SELECT/WITH statement."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise UnsafeSQLError("Empty SQL statement.")
    if ";" in stripped:
        raise UnsafeSQLError("Multiple SQL statements are not allowed.")
    head = stripped.split(None, 1)[0].lower()
    if head not in ("select", "with"):
        raise UnsafeSQLError(
            f"Only SELECT queries are allowed (got {head!r}).",
            hint="The SQL assistant is read-only by design.",
        )
    if _FORBIDDEN.search(stripped):
        raise UnsafeSQLError(
            "Statement contains a forbidden keyword.",
            hint="The SQL assistant is read-only by design.",
        )
    return stripped


class SQLAssistant:
    def __init__(self, catalog: Catalog, provider_cfg: ModelProviderConfig) -> None:
        self.catalog = catalog
        self.provider = get_provider(provider_cfg)

    def schema_context(self, limit_tables: int = 30) -> str:
        """Compact, PII-safe schema description for prompting."""
        lines: list[str] = []
        for t in self.catalog.list_tables()[:limit_tables]:
            meta = self.catalog.get_table(t["table"])
            cols = ", ".join(
                f"{c['name']} {c['type']}"
                + (" PK" if c["primary_key"] else "")
                + (" [PII]" if c["pii"] not in (None, "none") else "")
                for c in meta["columns"]
            )
            lines.append(f"table {meta['table']}: {cols}")
        for r in self.catalog.get_relationships():
            if r["confidence"] >= 0.6:
                lines.append(
                    f"join: {r['child_table']}.{r['child_column']} -> "
                    f"{r['parent_table']}.{r['parent_column']}"
                )
        return "\n".join(lines)

    def generate_sql(self, question: str) -> dict[str, Any]:
        """NL -> guarded SQL with explanation and grounding validation."""
        context = self.schema_context()
        raw = self.provider.complete(_SYSTEM_PROMPT, f"Schema:\n{context}\n\nQuestion: {question}")
        payload = _parse_json_block(raw)
        sql = guard_sql(str(payload.get("sql", "")))

        known_tables = {t["table"].lower() for t in self.catalog.list_tables()}
        used = [str(t) for t in payload.get("tables_used", [])]
        hallucinated = [t for t in used if t.lower() not in known_tables]
        if hallucinated:
            raise AIExtractionError(
                f"Model referenced unknown table(s): {', '.join(hallucinated)}.",
                hint="Re-run; if it persists, `adp scan` may be stale.",
            )
        return {
            "sql": sql,
            "explanation": str(payload.get("explanation", "")),
            "confidence": float(payload.get("confidence", 0.0)),
            "tables_used": used,
        }


def _parse_json_block(raw: str) -> dict[str, Any]:
    """Extract the first JSON object from a model response (handles fences)."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    raise AIExtractionError(
        "Model response was not valid JSON.",
        hint="Try again; check the provider/model configuration in adp.yaml.",
    )
