"""End-to-end: retail sales performance analysis via MCP server."""
from __future__ import annotations

import asyncio
import json

from ai_data_platform.mcp.server import create_server


def parse_result(result) -> dict:
    if isinstance(result, tuple):
        content_list = result[0]
        if isinstance(content_list, list) and hasattr(content_list[0], "text"):
            return json.loads(content_list[0].text)
    if isinstance(result, list):
        return json.loads(result[0].text)
    if hasattr(result, "text"):
        return json.loads(result.text)
    return json.loads(str(result))


async def run():
    server = create_server(
        "/Users/yogeshkhangode/experiment-personal/Data Generator/retail"
    )

    # ── Step 1: Generate 10k rows ──────────────────────────────────────
    print("=" * 60)
    print("STEP 1 — GENERATE 10k rows (parquet, seed=42)")
    print("=" * 60)
    result = await server.call_tool(
        "generate_synthetic_data",
        {"rows": 10000, "seed": 42, "output_format": "parquet"},
    )
    r = parse_result(result)
    print(f"ok: {r.get('ok')}")
    if r.get("ok"):
        for table, info in r["result"]["tables"].items():
            print(f"  {table}: {info['rows']:,} rows  →  {info.get('path', '?').split('/')[-1]}")
    else:
        print(f"ERROR: {r.get('error', r)}")
        return

    # ── Step 2: Quality check ──────────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 2 — QUALITY CHECK")
    print("=" * 60)
    result = await server.call_tool("run_quality_check", {})
    r = parse_result(result)
    print(f"ok: {r.get('ok')}")
    if r.get("ok"):
        print(f"  quality_score: {r['result']['quality_score']}")
        for cat, score in r["result"].get("category_scores", {}).items():
            print(f"  {cat}: {score}")
        failing = r["result"].get("failing_checks", [])
        print(f"  failing_checks: {len(failing)}")
        for fc in failing:
            print(f"    {fc['table']}.{fc['column']}: {fc['rule']} — {fc['evidence']}")

    # ── Step 3: Sales performance SQL queries ──────────────────────────
    queries = [
        (
            "Revenue by month",
            """
            SELECT DATE_TRUNC('month', order_date) AS month,
                   COUNT(DISTINCT order_id) AS num_orders,
                   SUM(total_amount) AS revenue,
                   ROUND(AVG(total_amount), 2) AS aov
            FROM fact_order
            GROUP BY 1 ORDER BY 1
            """,
        ),
        (
            "Revenue by product category",
            """
            SELECT p.category,
                   SUM(oi.quantity) AS units_sold,
                   ROUND(SUM(oi.item_total), 2) AS revenue
            FROM fact_order_item oi
            JOIN dim_product p ON oi.product_id = p.product_id
            GROUP BY 1 ORDER BY 3 DESC
            """,
        ),
        (
            "Top 10 customers by lifetime value",
            """
            SELECT c.first_name, c.last_name, c.loyalty_tier,
                   COUNT(o.order_id) AS total_orders,
                   ROUND(SUM(o.total_amount), 2) AS lifetime_value
            FROM dim_customer c
            JOIN fact_order o ON o.customer_id = c.customer_id
            GROUP BY 1,2,3 ORDER BY 5 DESC LIMIT 10
            """,
        ),
        (
            "Payment method mix (from dim_customer)",
            """
            SELECT c.preferred_payment_method,
                   COUNT(DISTINCT c.customer_id) AS customers,
                   COUNT(o.order_id) AS orders,
                   ROUND(AVG(o.total_amount), 2) AS aov,
                   ROUND(100.0*COUNT(o.order_id)/SUM(COUNT(o.order_id)) OVER(), 1) AS pct_orders
            FROM dim_customer c
            JOIN fact_order o ON o.customer_id = c.customer_id
            GROUP BY 1 ORDER BY 3 DESC
            """,
        ),
        (
            "Order status distribution",
            """
            SELECT order_status,
                   COUNT(*) AS cnt,
                   ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER(), 1) AS pct
            FROM fact_order
            GROUP BY 1 ORDER BY 2 DESC
            """,
        ),
        (
            "Return rate by product category",
            """
            SELECT p.category,
                   COUNT(*) AS total_items,
                   SUM(CASE WHEN oi.is_returned THEN 1 ELSE 0 END) AS returns,
                   ROUND(100.0*SUM(CASE WHEN oi.is_returned THEN 1 ELSE 0 END)/COUNT(*), 2) AS return_rate_pct
            FROM fact_order_item oi
            JOIN dim_product p ON oi.product_id = p.product_id
            GROUP BY 1 ORDER BY 4 DESC
            """,
        ),
        (
            "Revenue by loyalty tier",
            """
            SELECT c.loyalty_tier,
                   COUNT(DISTINCT c.customer_id) AS customers,
                   ROUND(SUM(o.total_amount), 2) AS total_revenue,
                   ROUND(AVG(o.total_amount), 2) AS avg_order_value,
                   ROUND(SUM(o.total_amount)/COUNT(DISTINCT c.customer_id), 2) AS arpu
            FROM dim_customer c
            JOIN fact_order o ON o.customer_id = c.customer_id
            GROUP BY 1 ORDER BY 4 DESC
            """,
        ),
        (
            "Month-over-month revenue growth",
            """
            WITH monthly AS (
                SELECT DATE_TRUNC('month', order_date) AS month,
                       SUM(total_amount) AS revenue
                FROM fact_order
                GROUP BY 1
            )
            SELECT month, revenue,
                   LAG(revenue) OVER (ORDER BY month) AS prev_month,
                   ROUND(100.0*(revenue - LAG(revenue) OVER (ORDER BY month))
                         / NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 1) AS mom_growth_pct
            FROM monthly ORDER BY 1
            """,
        ),
        (
            "Fulfillment: avg delivery days by warehouse",
            """
            SELECT warehouse_location,
                   COUNT(*) AS orders,
                   ROUND(AVG(EXTRACT(DAY FROM (delivery_date - shipment_date))), 2) AS avg_days_to_deliver,
                   ROUND(100.0*SUM(CASE WHEN order_status='Delivered' THEN 1 ELSE 0 END)/COUNT(*),1) AS delivery_rate_pct
            FROM fact_order
            WHERE delivery_date IS NOT NULL
            GROUP BY 1 ORDER BY 2 DESC
            """,
        ),
        (
            "Marketing campaign revenue attribution",
            """
            SELECT marketing_campaign,
                   COUNT(*) AS orders,
                   ROUND(SUM(total_amount), 2) AS revenue,
                   ROUND(AVG(total_amount), 2) AS aov,
                   ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER(), 1) AS pct_orders
            FROM fact_order
            GROUP BY 1 ORDER BY 3 DESC
            """,
        ),
    ]

    for name, sql in queries:
        print(f"\n{'─' * 60}")
        print(f"  {name}")
        print("─" * 60)
        result = await server.call_tool("execute_sql", {"sql": sql.strip()})
        r = parse_result(result)
        if r.get("ok"):
            rows = r["result"]["rows"]
            cols = list(rows[0].keys()) if rows else []
            print(f"  columns: {cols}")
            for row in rows[:8]:
                print(f"  {row}")
        else:
            print(f"  ERROR: {str(r.get('error', r))[:300]}")

    # ── Step 4: validate_business_questions ────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 4 — VALIDATE BUSINESS QUESTIONS")
    print("=" * 60)
    bqs = [
        "What is the total revenue and number of orders?",
        "What is the average order value?",
        "Which payment methods drive the most revenue?",
        "What is the month-over-month revenue trend?",
    ]
    result = await server.call_tool("validate_business_questions", {"questions": bqs})
    r = parse_result(result)
    print(f"ok: {r.get('ok')}")
    if r.get("ok"):
        for bq in r["result"].get("results", []):
            print(f"  Q: {bq.get('question', '')[:60]}")
            print(f"    answered: {bq.get('answered')}  |  SQL: {str(bq.get('sql', ''))[:80]}")

    # ── Step 5: generate_business_insights ────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 5 — GENERATE BUSINESS INSIGHTS")
    print("=" * 60)
    result = await server.call_tool(
        "generate_business_insights",
        {
            "sql": """
                SELECT p.category,
                       DATE_TRUNC('month', o.order_date) AS month,
                       ROUND(SUM(oi.item_total), 2) AS revenue,
                       SUM(oi.quantity) AS units_sold
                FROM fact_order_item oi
                JOIN fact_order o ON oi.order_id = o.order_id
                JOIN dim_product p ON oi.product_id = p.product_id
                GROUP BY 1, 2
                ORDER BY 3 DESC
                LIMIT 20
            """
        },
    )
    r = parse_result(result)
    print(f"ok: {r.get('ok')}")
    if r.get("ok"):
        insight = r["result"].get("insight", "")
        print(f"  {insight[:600]}")


if __name__ == "__main__":
    asyncio.run(run())
