"""DataAnalyst agent with view-first SQL routing and local execution."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

from utils.local_store import QueryResult, run_query
from utils.query_router import QueryRoute, decide_query_route
from utils.schema import render_schema_context


@dataclass(frozen=True)
class AnalysisDraft:
    """A safe SQL draft and routing metadata."""

    sql: str
    route: QueryRoute
    schema_context: str


@dataclass(frozen=True)
class DataAnalysis:
    """Executed analysis output shared with downstream agents."""

    question: str
    sql: str
    route: QueryRoute
    result: QueryResult
    summary: str


def draft_sql(question: str) -> AnalysisDraft:
    """Draft a view-first SQL statement for common project questions."""
    text = question.lower()
    if any(keyword in text for keyword in ("配送", "delivery", "延迟", "late", "准时")):
        sql = "SELECT * FROM mv_delivery_perf ORDER BY year_month DESC, late_rate DESC LIMIT 30;"
    elif any(keyword in text for keyword in ("支付", "payment", "分期")):
        sql = "SELECT * FROM mv_payment_dist ORDER BY year_month DESC, payment_value DESC LIMIT 40;"
    elif any(keyword in text for keyword in ("品类", "category", "类目")):
        sql = "SELECT product_category_name, SUM(total_gmv) AS total_gmv, SUM(total_orders) AS total_orders FROM mv_category_sales GROUP BY product_category_name ORDER BY total_gmv DESC LIMIT 15;"
    elif any(keyword in text for keyword in ("州", "state", "地区", "区域", "地图")):
        sql = "SELECT customer_state, SUM(total_gmv) AS total_gmv, SUM(total_orders) AS total_orders, ROUND(AVG(avg_order_value), 2) AS avg_order_value FROM mv_state_sales GROUP BY customer_state ORDER BY total_gmv DESC LIMIT 20;"
    elif any(keyword in text for keyword in ("卖家", "seller", "差评")):
        sql = "SELECT seller_id, seller_state, SUM(total_gmv) AS total_gmv, SUM(total_orders) AS total_orders, ROUND(AVG(avg_review_score), 2) AS avg_review_score FROM mv_seller_perf GROUP BY seller_id, seller_state ORDER BY avg_review_score ASC, total_gmv DESC LIMIT 20;"
    elif any(keyword in text for keyword in ("重量", "运费", "freight", "weight")):
        sql = "SELECT CAST(p.product_weight_g AS REAL) AS product_weight_g, CAST(oi.freight_value AS REAL) AS freight_value, CAST(oi.price AS REAL) AS price FROM order_items oi JOIN products p ON oi.product_id = p.product_id WHERE p.product_weight_g <> '' ORDER BY freight_value DESC LIMIT 200;"
    else:
        sql = "SELECT * FROM mv_monthly_sales ORDER BY year_month ASC LIMIT 36;"
    return AnalysisDraft(sql=sql, route=decide_query_route(sql), schema_context=render_schema_context())


def summarize_rows(rows: list[dict[str, Any]], columns: list[str]) -> str:
    """Create a compact Chinese data summary from query rows."""
    if not rows:
        return "查询成功，但结果为空。"
    parts = [f"返回 {len(rows)} 行，字段：{', '.join(columns)}。"]
    numeric_columns: list[str] = []
    for column in columns:
        values = []
        for row in rows:
            try:
                if row[column] is not None and row[column] != "":
                    values.append(float(row[column]))
            except (TypeError, ValueError):
                pass
        if values and len(values) >= max(2, len(rows) // 3):
            numeric_columns.append(column)
            parts.append(f"{column} 均值 {mean(values):.2f}，最大 {max(values):.2f}，最小 {min(values):.2f}。")
        if len(numeric_columns) >= 3:
            break
    first = rows[0]
    parts.append("首行样例：" + ", ".join(f"{key}={first[key]}" for key in columns[:5]))
    return " ".join(parts)


def analyze_question(question: str) -> DataAnalysis:
    """Draft, route, execute, and summarize a business question."""
    draft = draft_sql(question)
    result = run_query(draft.sql)
    summary = summarize_rows(result.rows, result.columns)
    return DataAnalysis(question=question, sql=draft.sql, route=draft.route, result=result, summary=summary)
