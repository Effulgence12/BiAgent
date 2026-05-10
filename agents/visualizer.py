"""Visualization agent skeleton for chart type selection."""

from __future__ import annotations


def choose_chart(sql: str) -> str:
    """Select an expected chart type from the routed SQL target."""
    lowered = sql.lower()
    if "mv_monthly_sales" in lowered:
        return "line"
    if "mv_state_sales" in lowered:
        return "bar_or_choropleth"
    if "mv_payment_dist" in lowered:
        return "heatmap_or_donut"
    if "mv_category_sales" in lowered:
        return "horizontal_bar"
    if "mv_delivery_perf" in lowered:
        return "bar_with_late_rate"
    return "table"
