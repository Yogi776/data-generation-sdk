"""Insight agent: deterministic analytics with optional LLM enrichment.

Everything here works with zero network/keys — suggestions and insights are
computed from schema shape and real result statistics. When a model provider is
configured, the narrative summary and query ideas are *augmented* (never
required); any provider failure degrades silently back to the deterministic
output. This is the "hybrid" mode.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ai_data_platform.config import ModelProviderConfig
from ai_data_platform.core.logging import get_logger
from ai_data_platform.explorer.engine import DuckDBExplorer
from ai_data_platform.explorer.metastore import ExplorerMetastore
from ai_data_platform.explorer.registrar import quote_ident

log = get_logger("adp.explorer.insights")

_MEASURE_HINTS = (
    "amount",
    "amt",
    "price",
    "revenue",
    "sales",
    "cost",
    "total",
    "qty",
    "quantity",
    "value",
    "balance",
    "count",
    "score",
    "rate",
    "profit",
    "spend",
)
_ID_RE = re.compile(r"(^id$|_id$|_key$|^id_)", re.IGNORECASE)


def _classify(columns: list[dict[str, Any]]) -> dict[str, list[str]]:
    ids, measures, dims, dates = [], [], [], []
    for c in columns:
        name = c["name"]
        dtype = str(c["type"]).upper()
        numeric = any(k in dtype for k in ("INT", "DECIMAL", "DOUBLE", "FLOAT", "REAL", "HUGEINT"))
        temporal = any(k in dtype for k in ("DATE", "TIME", "TIMESTAMP"))
        if _ID_RE.search(name):
            ids.append(name)
        elif temporal:
            dates.append(name)
        elif numeric:
            # Numeric columns are treated as measures whether or not the name
            # matches a business-metric hint.
            measures.append(name)
        else:
            dims.append(name)
    return {"ids": ids, "measures": measures, "dimensions": dims, "dates": dates}


class InsightAgent:
    def __init__(
        self,
        metastore: ExplorerMetastore,
        engine: DuckDBExplorer,
        provider_cfg: ModelProviderConfig | None = None,
    ) -> None:
        self.metastore = metastore
        self.engine = engine
        self.provider_cfg = provider_cfg

    # -- suggestions ---------------------------------------------------------
    def suggest_analytics_queries(
        self, dataset: str, table: str | None = None, limit: int = 8
    ) -> dict[str, Any]:
        # Single query fetches every table with its columns (no per-table N+1).
        tables = self.metastore.list_tables_with_columns(dataset)
        by_name = {t["table"]: t for t in tables}
        targets = [by_name[table]] if table and table in by_name else tables
        suggestions: list[dict[str, str]] = []

        for t in targets:
            suggestions.extend(self._table_suggestions(t["table"], t["columns"]))
        suggestions.extend(self._join_suggestions(tables))

        # De-dup by SQL, cap.
        seen: set[str] = set()
        unique = []
        for s in suggestions:
            if s["sql"] in seen:
                continue
            seen.add(s["sql"])
            unique.append(s)
        unique = unique[:limit]

        source = "deterministic"
        enriched = self._llm_suggestions(tables)
        if enriched:
            for e in enriched:
                if e["sql"] not in seen:
                    unique.append(e)
                    seen.add(e["sql"])
            source = "hybrid"
        return {
            "dataset": dataset,
            "suggestions": unique[: max(limit, len(unique))],
            "source": source,
        }

    def _table_suggestions(self, table: str, columns: list[dict[str, Any]]) -> list[dict[str, str]]:
        roles = _classify(columns)
        ident = quote_ident(table)
        out: list[dict[str, str]] = [
            {
                "title": f"Row count — {table}",
                "sql": f"SELECT count(*) AS rows FROM {ident};",
                "rationale": "Baseline volume for the table.",
                "category": "overview",
            }
        ]
        measure = roles["measures"][0] if roles["measures"] else None
        date = roles["dates"][0] if roles["dates"] else None
        dim = roles["dimensions"][0] if roles["dimensions"] else None

        if measure and date:
            out.append(
                {
                    "title": f"Monthly {measure} — {table}",
                    "sql": (
                        f"SELECT date_trunc('month', {quote_ident(date)}) AS month, "
                        f"sum({quote_ident(measure)}) AS total_{measure} "
                        f"FROM {ident} GROUP BY 1 ORDER BY 1;"
                    ),
                    "rationale": "Time series of the primary measure — trend/seasonality.",
                    "category": "trend",
                }
            )
        if measure and dim:
            out.append(
                {
                    "title": f"Top {dim} by {measure} — {table}",
                    "sql": (
                        f"SELECT {quote_ident(dim)}, sum({quote_ident(measure)}) AS total_{measure} "
                        f"FROM {ident} GROUP BY 1 ORDER BY 2 DESC LIMIT 20;"
                    ),
                    "rationale": "Ranking to find the biggest contributors.",
                    "category": "ranking",
                }
            )
        if dim:
            out.append(
                {
                    "title": f"Distribution of {dim} — {table}",
                    "sql": (
                        f"SELECT {quote_ident(dim)}, count(*) AS n FROM {ident} "
                        f"GROUP BY 1 ORDER BY 2 DESC LIMIT 20;"
                    ),
                    "rationale": "Category mix / segment sizes.",
                    "category": "distribution",
                }
            )
        return out

    def _join_suggestions(self, tables: list[dict[str, Any]]) -> list[dict[str, str]]:
        # Shared id-like columns across tables imply a join key. `tables` already
        # carries columns (fetched once), so no further metastore reads here.
        col_index: dict[str, list[str]] = {}
        for t in tables:
            for c in t["columns"]:
                if _ID_RE.search(c["name"]):
                    col_index.setdefault(c["name"], []).append(t["table"])
        out: list[dict[str, str]] = []
        for col, owners in col_index.items():
            if len(owners) >= 2:
                a, b = owners[0], owners[1]
                out.append(
                    {
                        "title": f"Join {a} × {b} on {col}",
                        "sql": (
                            f"SELECT * FROM {quote_ident(a)} a "
                            f"JOIN {quote_ident(b)} b USING ({quote_ident(col)}) LIMIT 100;"
                        ),
                        "rationale": f"{col!r} appears in both {a} and {b} — a natural join key.",
                        "category": "join",
                    }
                )
        return out

    # -- insights over a result ---------------------------------------------
    def generate_business_insights(self, dataset: str, sql: str) -> dict[str, Any]:
        result = self.engine.execute_sql(dataset, sql)
        insights = self._result_insights(result)
        metrics = self._dashboard_metrics(result)
        recs = self._recommended_followups(dataset, result)
        summary = self._deterministic_summary(result, insights)

        source = "deterministic"
        llm = self._llm_narrative(sql, result, insights)
        if llm:
            summary = llm
            source = "hybrid"
        return {
            "summary": summary,
            "insights": insights,
            "dashboard_metrics": metrics,
            "recommended_queries": recs,
            "result_preview": result,
            "source": source,
        }

    def _result_insights(self, result: dict[str, Any]) -> list[dict[str, str]]:
        rows = result["rows"]
        cols = result["columns"]
        out: list[dict[str, str]] = []
        if not rows:
            out.append({"kind": "data_quality", "message": "Query returned no rows."})
            return out
        if result.get("truncated"):
            out.append(
                {
                    "kind": "data_quality",
                    "message": (
                        f"Result truncated to {result['row_count']} rows"
                        f"{' (sampled)' if result.get('sampled') else ''}; "
                        "aggregate or add filters for a complete view."
                    ),
                }
            )
        for col in cols:
            values = [r[col] for r in rows]
            nums = [v for v in values if isinstance(v, int | float) and not isinstance(v, bool)]
            nulls = sum(1 for v in values if v is None)
            if nulls:
                out.append(
                    {
                        "kind": "data_quality",
                        "message": f"Column {col!r} has {nulls}/{len(values)} null values.",
                    }
                )
            if len(nums) >= 3:
                lo, hi = min(nums), max(nums)
                mean = sum(nums) / len(nums)
                out.append(
                    {
                        "kind": "finding",
                        "message": (
                            f"{col}: min={lo:g}, max={hi:g}, avg={mean:.2f} over {len(nums)} rows."
                        ),
                    }
                )
                # crude outlier flag: max is far above the mean
                if mean and hi > mean * 5 and hi > lo:
                    out.append(
                        {
                            "kind": "anomaly",
                            "message": f"{col}: max {hi:g} is >5× the mean ({mean:.2f}) — possible outlier.",
                        }
                    )
                # crude monotonic trend on ordered result
                if len(nums) >= 4:
                    ups = sum(1 for a, b in zip(nums, nums[1:]) if b > a)
                    downs = sum(1 for a, b in zip(nums, nums[1:]) if b < a)
                    if ups >= len(nums) - 2:
                        out.append(
                            {"kind": "trend", "message": f"{col} is increasing across the result."}
                        )
                    elif downs >= len(nums) - 2:
                        out.append(
                            {"kind": "trend", "message": f"{col} is decreasing across the result."}
                        )
        return out[:20]

    @staticmethod
    def _dashboard_metrics(result: dict[str, Any]) -> list[dict[str, Any]]:
        rows, cols = result["rows"], result["columns"]
        metrics: list[dict[str, Any]] = [{"label": "rows_returned", "value": result["row_count"]}]
        if not rows:
            return metrics
        for col in cols:
            nums = [
                r[col]
                for r in rows
                if isinstance(r[col], int | float) and not isinstance(r[col], bool)
            ]
            if nums:
                metrics.append({"label": f"sum_{col}", "value": round(sum(nums), 4)})
                metrics.append({"label": f"avg_{col}", "value": round(sum(nums) / len(nums), 4)})
        return metrics[:12]

    def _recommended_followups(self, dataset: str, result: dict[str, Any]) -> list[dict[str, str]]:
        recs: list[dict[str, str]] = []
        cols = result["columns"]
        for col in cols:
            if _ID_RE.search(col):
                continue
            sample = next((r[col] for r in result["rows"] if r[col] is not None), None)
            if isinstance(sample, int | float) and not isinstance(sample, bool):
                recs.append(
                    {
                        "title": f"Distribution of {col}",
                        "sql": f"SELECT min({quote_ident(col)}), max({quote_ident(col)}), "
                        f"avg({quote_ident(col)}) FROM ({result_marker()}) t;",
                        "rationale": "Understand the spread of this metric.",
                        "category": "drilldown",
                    }
                )
                break
        return recs[:3]

    @staticmethod
    def _deterministic_summary(result: dict[str, Any], insights: list[dict[str, str]]) -> str:
        head = f"Query returned {result['row_count']} row(s) across {len(result['columns'])} column(s)."
        findings = [i["message"] for i in insights if i["kind"] in ("finding", "trend", "anomaly")]
        if findings:
            return head + " " + " ".join(findings[:3])
        return head

    # -- validation ----------------------------------------------------------
    def validate_business_questions(self, dataset: str, questions: list[str]) -> dict[str, Any]:
        # One query for all tables+columns; build the vocabulary in memory.
        vocab: dict[str, list[str]] = {
            t["table"]: [c["name"] for c in t["columns"]]
            for t in self.metastore.list_tables_with_columns(dataset)
        }

        verdicts = []
        for q in questions:
            tokens = set(re.findall(r"[a-z_]+", q.lower()))
            needed = []
            for tname, cols in vocab.items():
                if tname.lower() in tokens or any(
                    c.lower() in tokens or c.lower().rstrip("s") in tokens for c in cols
                ):
                    needed.append(tname)
            answerable = bool(needed)
            verdicts.append(
                {
                    "question": q,
                    "answerable": answerable,
                    "reason": (
                        f"Matched tables/columns: {', '.join(needed)}."
                        if answerable
                        else "No registered table or column matched the question terms."
                    ),
                    "suggested_sql": (
                        f"SELECT * FROM {quote_ident(needed[0])} LIMIT 100;" if answerable else None
                    ),
                    "tables_needed": needed,
                }
            )
        return {"dataset": dataset, "verdicts": verdicts}

    # -- optional LLM --------------------------------------------------------
    def _provider(self) -> Any | None:
        if not self.provider_cfg:
            return None
        try:
            from ai_data_platform.sql.providers import get_provider

            return get_provider(self.provider_cfg)
        except Exception as e:  # noqa: BLE001 - LLM is optional everywhere
            log.info("insight LLM unavailable, using deterministic only: %s", e)
            return None

    def _llm_narrative(
        self, sql: str, result: dict[str, Any], insights: list[dict[str, str]]
    ) -> str | None:
        provider = self._provider()
        if provider is None:
            return None
        try:
            preview = {"columns": result["columns"], "rows": result["rows"][:20]}
            user = (
                f"SQL:\n{sql}\n\nResult sample (JSON):\n{json.dumps(preview, default=str)}\n\n"
                f"Deterministic findings:\n{json.dumps(insights, default=str)}\n\n"
                "Write a concise 2-4 sentence business summary of what this shows."
            )
            text = provider.complete(
                "You are a precise data analyst. Summarize findings factually; "
                "do not invent numbers beyond the provided data.",
                user,
            )
            return text.strip() or None
        except Exception as e:  # noqa: BLE001
            log.info("insight narrative failed, degrading: %s", e)
            return None

    def _llm_suggestions(
        self, tables: list[dict[str, Any]]
    ) -> list[dict[str, str]] | None:
        provider = self._provider()
        if provider is None:
            return None
        try:
            # `tables` already carries columns — no per-table metastore reads.
            schema = "\n".join(
                f"{t['table']}({', '.join(c['name'] for c in t['columns'])})" for t in tables
            )
            raw = provider.complete(
                "You suggest read-only analytical SQL (DuckDB). Respond with a JSON "
                'array of {"title","sql","rationale","category"}. SELECT only.',
                f"Schema:\n{schema}\n\nSuggest 3 useful analytics queries.",
            )
            data = json.loads(re.sub(r"^```[a-z]*\n?|\n?```$", "", raw.strip()))
            if isinstance(data, list):
                return [
                    {
                        "title": str(d.get("title", "query")),
                        "sql": str(d["sql"]),
                        "rationale": str(d.get("rationale", "")),
                        "category": str(d.get("category", "llm")),
                    }
                    for d in data
                    if isinstance(d, dict) and d.get("sql")
                ][:3]
        except Exception as e:  # noqa: BLE001
            log.info("insight suggestions LLM failed, degrading: %s", e)
        return None


def result_marker() -> str:
    """Placeholder subquery text for follow-up templates (documented, not executed
    verbatim). Kept as a function so the intent is explicit in output."""
    return "SELECT 1 WHERE false"
