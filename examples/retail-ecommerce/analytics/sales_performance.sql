-- Sales performance analysis (Snowflake)
-- Database: Retail  |  Schema: PUBLIC  |  Horizon: 3 years (2023–2025)

USE DATABASE Retail;
USE SCHEMA PUBLIC;

-- 1) Monthly revenue & order volume
SELECT
    DATE_TRUNC('month', o.order_date) AS month,
    COUNT(DISTINCT o.order_id)        AS orders,
    SUM(o.total_amount)               AS gross_revenue,
    SUM(CASE WHEN o.status = 'delivered' THEN o.total_amount ELSE 0 END) AS net_revenue
FROM orders o
WHERE o.order_date >= '2023-01-01'
GROUP BY 1
ORDER BY 1;

-- 2) Year-over-year revenue growth
WITH monthly AS (
    SELECT
        YEAR(o.order_date)  AS yr,
        MONTH(o.order_date) AS mo,
        SUM(o.total_amount) AS revenue
    FROM orders o
    WHERE o.status <> 'cancelled'
    GROUP BY 1, 2
)
SELECT
    mo,
    MAX(CASE WHEN yr = 2023 THEN revenue END) AS rev_2023,
    MAX(CASE WHEN yr = 2024 THEN revenue END) AS rev_2024,
    MAX(CASE WHEN yr = 2025 THEN revenue END) AS rev_2025,
    ROUND(
        (MAX(CASE WHEN yr = 2024 THEN revenue END) - MAX(CASE WHEN yr = 2023 THEN revenue END))
        / NULLIF(MAX(CASE WHEN yr = 2023 THEN revenue END), 0) * 100, 1
    ) AS yoy_2024_pct
FROM monthly
GROUP BY mo
ORDER BY mo;

-- 3) Category mix
SELECT
    p.category,
    COUNT(*)              AS line_items,
    SUM(o.total_amount)   AS revenue,
    ROUND(SUM(o.total_amount) * 100.0 / SUM(SUM(o.total_amount)) OVER (), 1) AS revenue_pct
FROM orders o
JOIN products p ON o.product_id = p.product_id
WHERE o.status = 'delivered'
GROUP BY 1
ORDER BY revenue DESC;

-- 4) Channel & region performance
SELECT
    o.region,
    o.channel,
    COUNT(DISTINCT o.order_id) AS orders,
    SUM(o.total_amount)        AS revenue,
    ROUND(AVG(o.total_amount), 2) AS avg_order_value
FROM orders o
WHERE o.status = 'delivered'
GROUP BY 1, 2
ORDER BY revenue DESC;

-- 5) Customer segment value
SELECT
    c.segment,
    COUNT(DISTINCT c.customer_id) AS customers,
    COUNT(DISTINCT o.order_id)    AS orders,
    SUM(o.total_amount)           AS revenue,
    ROUND(SUM(o.total_amount) / NULLIF(COUNT(DISTINCT c.customer_id), 0), 2) AS revenue_per_customer
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE o.status = 'delivered'
GROUP BY 1
ORDER BY revenue DESC;

-- 6) Payment method mix
SELECT
    t.payment_method,
    COUNT(*)           AS transactions,
    SUM(t.amount)      AS amount,
    ROUND(AVG(t.amount), 2) AS avg_ticket
FROM transactions t
GROUP BY 1
ORDER BY amount DESC;
