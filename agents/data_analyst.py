"""Initial DataAnalyst implementation with view-first SQL routing."""

from __future__ import annotations

from dataclasses import dataclass

from utils.query_router import QueryRoute, decide_query_route
from utils.schema import render_schema_context


@dataclass(frozen=True)
class AnalysisDraft:
    """A safe SQL draft and routing metadata generated for the skeleton app."""

    sql: str
    route: QueryRoute
    schema_context: str


def draft_sql(question: str) -> AnalysisDraft:
    """Draft a simple view-first SQL statement for common project questions."""
    text = question.lower()
    if any(keyword in text for keyword in ("配送", "delivery", "延迟", "late")):
        sql = "SELECT * FROM mv_delivery_perf ORDER BY year_month DESC, late_rate DESC LIMIT 20;"
    elif any(keyword in text for keyword in ("支付", "payment", "分期")):
        sql = "SELECT * FROM mv_payment_dist ORDER BY year_month DESC, payment_value DESC LIMIT 20;"
    elif any(keyword in text for keyword in ("品类", "category", "类目")):
        sql = "SELECT * FROM mv_category_sales ORDER BY total_gmv DESC LIMIT 20;"
    elif any(keyword in text for keyword in ("州", "state", "地区", "区域")):
        sql = "SELECT * FROM mv_state_sales ORDER BY year_month DESC, total_gmv DESC LIMIT 20;"
    elif any(keyword in text for keyword in ("卖家", "seller")):
        sql = "SELECT * FROM mv_seller_perf ORDER BY year_month DESC, total_gmv DESC LIMIT 20;"
    else:
        sql = "SELECT * FROM mv_monthly_sales ORDER BY year_month DESC LIMIT 20;"
    return AnalysisDraft(sql=sql, route=decide_query_route(sql), schema_context=render_schema_context())
