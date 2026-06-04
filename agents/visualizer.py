"""Visualization agent that returns Plotly/Folium chart specifications."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from html import escape
from typing import Any
from uuid import uuid4

import folium
import plotly.graph_objects as go

from utils.local_store import QueryResult


@dataclass(frozen=True)
class ChartSpec:
    """A dashboard-ready chart with provenance."""

    id: str
    title: str
    type: str
    source_view: str
    html: str
    summary: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


PLOTLY_TEMPLATE = "plotly_white"


def choose_chart(sql: str) -> str:
    """Select an expected chart type from the routed SQL target."""
    lowered = sql.lower()
    if "mv_monthly_sales" in lowered:
        return "line"
    if "mv_state_geo" in lowered or "geolocation" in lowered:
        return "geo_bubble"
    if "mv_state_sales" in lowered:
        return "bar"
    if "mv_payment_dist" in lowered:
        return "heatmap_or_donut"
    if "mv_category_sales" in lowered or "mv_review_category_perf" in lowered:
        return "horizontal_bar"
    if "mv_delivery_perf" in lowered:
        return "bar"
    if "mv_weight_freight" in lowered or ("weight" in lowered and "freight" in lowered):
        return "bubble"
    return "table"


def _as_float(value: object) -> float:
    try:
        return float(value) if value not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _hex_color(start: str, end: str, ratio: float) -> str:
    ratio = _clamp(ratio)
    s = tuple(int(start[index : index + 2], 16) for index in (1, 3, 5))
    e = tuple(int(end[index : index + 2], 16) for index in (1, 3, 5))
    return "#" + "".join(f"{round(sv + (ev - sv) * ratio):02x}" for sv, ev in zip(s, e))


def _format_rate(value: object) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "未知"


def _first_column(columns: list[str], *candidates: str) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return ""


def _source_view(result_name: str, result: QueryResult) -> str:
    lowered = result_name.lower()
    for name in (
        "mv_monthly_sales",
        "mv_state_sales",
        "mv_category_sales",
        "mv_delivery_perf",
        "mv_seller_perf",
        "mv_payment_dist",
        "mv_weekly_sales",
        "mv_state_geo",
        "mv_review_category_perf",
        "mv_weight_freight",
    ):
        if name in lowered:
            return name
    columns = set(result.columns)
    if {"customer_state", "lat", "lng"}.issubset(columns):
        return "mv_state_geo"
    if {"payment_type", "payment_installments"}.issubset(columns):
        return "mv_payment_dist"
    if {"avg_weight_g", "avg_freight"}.issubset(columns):
        return "mv_weight_freight"
    if "product_category_name" in columns and any(column.endswith("_complaints") for column in columns):
        return "mv_review_category_perf"
    if {"week_start", "total_gmv"}.issubset(columns):
        return "mv_weekly_sales"
    if {"year_month", "total_gmv"}.issubset(columns):
        return "mv_monthly_sales"
    if "customer_state" in columns and any(column in columns for column in ("late_rate", "avg_delivery_days")):
        return "mv_delivery_perf"
    if "product_category_name" in columns:
        return "mv_category_sales"
    if "seller_id" in columns:
        return "mv_seller_perf"
    return result.source


def _plotly_html(fig: go.Figure, include_plotlyjs: bool) -> str:
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        margin=dict(l=24, r=24, t=56, b=32),
        font=dict(family="Microsoft YaHei, Arial, sans-serif", size=13),
        hovermode="closest",
        autosize=True,
    )
    return fig.to_html(
        include_plotlyjs=True if include_plotlyjs else False,
        full_html=False,
        config={"displaylogo": False, "responsive": True},
    )


def _table_html(rows: list[dict[str, Any]], limit: int = 30) -> str:
    if not rows:
        return "<p>无数据可展示。</p>"
    columns = list(rows[0].keys())
    header = "".join(f"<th>{escape(str(column))}</th>" for column in columns)
    body = []
    for row in rows[:limit]:
        body.append("<tr>" + "".join(f"<td>{escape(str(row.get(column, '')))}</td>" for column in columns) + "</tr>")
    return f"<table class='data-table'><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _with_evidence_table(chart_html: str, result: QueryResult) -> str:
    """Attach the queried rows under every chart so the dashboard shows chart + evidence."""
    return (
        f"<div class='chart-visual'>{chart_html}</div>"
        "<details class='chart-data' open>"
        f"<summary>数据表（前 {min(30, len(result.rows))} 行）</summary>"
        f"{_table_html(result.rows)}"
        "</details>"
    )


def _chart_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _line_chart(name: str, result: QueryResult, forecast: list[dict[str, Any]], include_js: bool) -> ChartSpec:
    rows = result.rows
    x_key = _first_column(result.columns, "year_month", "week_start")
    y_key = _first_column(result.columns, "total_gmv", "total_sales")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[row[x_key] for row in rows], y=[_as_float(row.get(y_key)) for row in rows], mode="lines+markers", name="历史GMV"))
    if forecast:
        fig.add_trace(go.Scatter(x=[row["week_start"] for row in forecast], y=[row["yhat_upper"] for row in forecast], mode="lines", line=dict(width=0), showlegend=False))
        fig.add_trace(
            go.Scatter(
                x=[row["week_start"] for row in forecast],
                y=[row["yhat_lower"] for row in forecast],
                mode="lines",
                fill="tonexty",
                fillcolor="rgba(42,111,187,0.18)",
                line=dict(width=0),
                name="预测区间",
            )
        )
        fig.add_trace(go.Scatter(x=[row["week_start"] for row in forecast], y=[row["yhat"] for row in forecast], mode="lines+markers", name="未来6周预测"))
    title = "GMV趋势与未来6周预测" if forecast else "GMV时间序列趋势"
    fig.update_layout(title=title, xaxis_title="时间", yaxis_title="GMV")
    return ChartSpec(_chart_id("trend"), title, "plotly_line", _source_view(name, result), _with_evidence_table(_plotly_html(fig, include_js), result), "展示历史GMV趋势；预测题会叠加未来6周预测和置信区间。")


def _bar_chart(name: str, result: QueryResult, include_js: bool) -> ChartSpec:
    rows = result.rows[:20]
    columns = result.columns
    label_key = _first_column(columns, "customer_state", "product_category_name", "payment_type", "seller_state")
    value_key = _first_column(columns, "total_gmv", "total_sales", "payment_count", "total_count", "total_orders", "late_rate", "negative_rate", "avg_review_score")
    horizontal = label_key in {"product_category_name"} or len(rows) > 10
    fig = go.Figure()
    if horizontal:
        fig.add_trace(go.Bar(y=[row.get(label_key) for row in rows], x=[_as_float(row.get(value_key)) for row in rows], orientation="h", marker_color="#2a6fbb"))
        fig.update_layout(yaxis=dict(autorange="reversed"))
    else:
        fig.add_trace(go.Bar(x=[row.get(label_key) for row in rows], y=[_as_float(row.get(value_key)) for row in rows], marker_color="#2a6fbb"))
    title = "维度排名对比"
    if value_key == "late_rate":
        title = "各州配送延迟率"
    elif "payment" in label_key:
        title = "支付方式频率"
    elif "category" in label_key:
        title = "品类表现排名"
    fig.update_layout(title=title, xaxis_title=value_key, yaxis_title=label_key)
    return ChartSpec(_chart_id("bar"), title, "plotly_bar", _source_view(name, result), _with_evidence_table(_plotly_html(fig, include_js), result), f"按 {label_key} 对 {value_key} 做排名对比。")


def _heatmap_chart(name: str, result: QueryResult, include_js: bool) -> ChartSpec:
    rows = result.rows
    x_values = list(dict.fromkeys(str(row.get("payment_type", "")) for row in rows))
    y_values = list(dict.fromkeys(str(row.get("payment_installments", "")) for row in rows))
    lookup = {(str(row.get("payment_type", "")), str(row.get("payment_installments", ""))): _as_float(row.get("payment_count")) for row in rows}
    z = [[lookup.get((x, y), 0.0) for x in x_values] for y in y_values]
    fig = go.Figure(data=go.Heatmap(x=x_values, y=y_values, z=z, colorscale="Blues", hoverongaps=False))
    fig.update_layout(title="支付方式 x 分期数热力图", xaxis_title="支付方式", yaxis_title="分期数")
    return ChartSpec(_chart_id("heatmap"), "支付方式 x 分期数热力图", "plotly_heatmap", _source_view(name, result), _with_evidence_table(_plotly_html(fig, include_js), result), "展示支付方式与分期数的交叉分布。")


def _bubble_chart(name: str, result: QueryResult, include_js: bool) -> ChartSpec:
    rows = result.rows
    x_key = _first_column(result.columns, "avg_weight_g", "product_weight_g")
    y_key = _first_column(result.columns, "avg_freight", "freight_value")
    size_key = _first_column(result.columns, "order_count", "total_orders")
    color_key = _first_column(result.columns, "delivery_status", "customer_state")
    palette = {"late": "#d64545", "on_time": "#2a6fbb"}
    categories = list(dict.fromkeys(str(row.get(color_key, "")) for row in rows))
    color_lookup = {category: palette.get(category, ["#2a6fbb", "#0f766e", "#d97706", "#7c3aed", "#475569"][index % 5]) for index, category in enumerate(categories)}
    fig = go.Figure(
        data=go.Scatter(
            x=[_as_float(row.get(x_key)) for row in rows],
            y=[_as_float(row.get(y_key)) for row in rows],
            mode="markers",
            marker=dict(
                size=[max(8, min(42, (_as_float(row.get(size_key)) or 1) ** 0.5)) for row in rows],
                color=[color_lookup.get(str(row.get(color_key, "")), "#2a6fbb") for row in rows],
                showscale=False,
                opacity=0.72,
            ),
            text=[str(row) for row in rows],
        )
    )
    fig.update_layout(title="产品重量/体积与运费关系", xaxis_title=x_key, yaxis_title=y_key)
    return ChartSpec(_chart_id("bubble"), "产品重量/体积与运费关系", "plotly_bubble", _source_view(name, result), _with_evidence_table(_plotly_html(fig, include_js), result), "气泡大小表示订单量，颜色区分配送状态或地区。")


def _geo_metric_from_requirements(chart_requirements: list[dict[str, Any]] | tuple[dict[str, Any], ...], columns: set[str]) -> str:
    """Use the Orchestrator's chart metric when the result columns can support it."""
    text = " ".join(
        str(value).lower()
        for requirement in chart_requirements
        if isinstance(requirement, dict)
        for value in requirement.values()
    )
    if any(metric in text for metric in ("delivery_late_rate", "late_rate", "delivery_delay", "logistics_risk")) and {"late_rate", "late_orders"}.issubset(columns):
        return "delivery_late"
    if any(metric in text for metric in ("delivery_on_time_rate", "on_time_rate", "fulfillment_rate")) and "on_time_rate" in columns:
        return "delivery_on_time"
    if any(metric in text for metric in ("seller_review_risk", "seller_score", "review_risk")) and "avg_review_score" in columns:
        return "seller_review_risk"
    if any(metric in text for metric in ("sales_gmv", "total_gmv", "order_volume")) and "total_gmv" in columns:
        return "sales"
    return ""


def _geo_map(name: str, result: QueryResult, chart_requirements: list[dict[str, Any]] | tuple[dict[str, Any], ...] = ()) -> ChartSpec:
    rows = [row for row in result.rows if row.get("lat") not in (None, "") and row.get("lng") not in (None, "")]
    fmap = folium.Map(location=[-14.2, -51.9], zoom_start=4, tiles="CartoDB positron", width="100%", height="520px")
    columns = set(result.columns)
    metric = _geo_metric_from_requirements(chart_requirements, columns)
    if not metric:
        metric = str(rows[0].get("map_metric") or "") if rows else ""
    if not metric:
        if {"late_rate", "late_orders"}.issubset(columns):
            metric = "delivery_late"
        elif "on_time_rate" in columns:
            metric = "delivery_on_time"
        elif "avg_review_score" in columns:
            metric = "seller_review_risk"
        else:
            metric = "sales"

    if metric == "delivery_late":
        title = "各州配送延迟地图"
        source_view = "mv_state_geo + mv_delivery_perf"
        summary = "颜色越红表示延迟率越高，气泡越大表示延迟订单越多。"
        size_key = "late_orders"
        max_size = max((_as_float(row.get(size_key)) for row in rows), default=1.0) or 1.0
        max_late_rate = max((_as_float(row.get("late_rate")) for row in rows), default=1.0) or 1.0
    elif metric == "delivery_on_time":
        title = "各州准时交付率地图"
        source_view = "mv_state_geo + mv_delivery_perf"
        summary = "颜色从红到绿表示准时交付率由低到高，气泡大小表示订单量。"
        size_key = "total_orders"
        max_size = max((_as_float(row.get(size_key)) for row in rows), default=1.0) or 1.0
    elif metric == "seller_review_risk":
        title = "州级卖家评分风险地图"
        source_view = "mv_state_geo + mv_seller_perf"
        summary = "颜色越红表示平均评分越低，气泡大小表示卖家订单量。"
        size_key = "total_orders"
        max_size = max((_as_float(row.get(size_key)) for row in rows), default=1.0) or 1.0
    else:
        title = "巴西州级销售气泡地图"
        source_view = _source_view(name, result)
        summary = "基于州质心经纬度展示销售额和订单量分布。"
        size_key = "total_gmv"
        max_size = max((_as_float(row.get(size_key)) for row in rows), default=1.0) or 1.0

    for row in rows:
        size_value = _as_float(row.get(size_key))
        radius = 5 + 22 * (size_value / max_size) ** 0.5
        if metric == "delivery_late":
            late_rate = _as_float(row.get("late_rate"))
            color = _hex_color("#fca5a5", "#b91c1c", late_rate / max_late_rate)
            popup = (
                f"{row.get('customer_state')}<br>"
                f"延迟率: {_format_rate(row.get('late_rate'))}<br>"
                f"延迟订单: {row.get('late_orders')}<br>"
                f"平均配送天数: {row.get('avg_delivery_days')}<br>"
                f"订单数: {row.get('total_orders')}"
            )
        elif metric == "delivery_on_time":
            on_time_rate = _as_float(row.get("on_time_rate"))
            color = _hex_color("#dc2626", "#16a34a", on_time_rate)
            popup = (
                f"{row.get('customer_state')}<br>"
                f"准时交付率: {_format_rate(row.get('on_time_rate'))}<br>"
                f"延迟率: {_format_rate(row.get('late_rate'))}<br>"
                f"平均配送天数: {row.get('avg_delivery_days')}<br>"
                f"订单数: {row.get('total_orders')}"
            )
        elif metric == "seller_review_risk":
            score = _as_float(row.get("avg_review_score"))
            risk = _clamp((5.0 - score) / 4.0)
            color = _hex_color("#93c5fd", "#dc2626", risk)
            popup = (
                f"{row.get('customer_state')}<br>"
                f"平均评分: {row.get('avg_review_score')}<br>"
                f"卖家订单数: {row.get('total_orders')}<br>"
                f"卖家GMV: {_as_float(row.get('total_gmv')):,.2f}"
            )
        else:
            value = _as_float(row.get("total_gmv"))
            color = "#1f6feb"
            popup = f"{row.get('customer_state')}<br>GMV: {value:,.2f}<br>Orders: {row.get('total_orders')}"
        folium.CircleMarker(
            location=[_as_float(row.get("lat")), _as_float(row.get("lng"))],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.62,
            popup=popup,
        ).add_to(fmap)
    map_html = fmap.get_root().render()
    iframe = f"<iframe class='folium-frame' title='{escape(title)}' srcdoc=\"{escape(map_html, quote=True)}\"></iframe>"
    return ChartSpec(_chart_id("map"), title, f"folium_map_{metric}", source_view, _with_evidence_table(iframe, result), summary)


def _review_reason_chart(name: str, result: QueryResult, include_js: bool) -> ChartSpec:
    rows = result.rows[:12]
    categories = [row.get("product_category_name") for row in rows]
    fig = go.Figure()
    for key, label in (
        ("delay_complaints", "物流延迟"),
        ("quality_complaints", "质量问题"),
        ("wrong_item_complaints", "错发/退换"),
        ("service_complaints", "客服/沟通"),
        ("other_complaints", "其他"),
    ):
        if key in result.columns:
            fig.add_trace(go.Bar(name=label, y=categories, x=[_as_float(row.get(key)) for row in rows], orientation="h"))
    if not fig.data:
        return _bar_chart(name, result, include_js)
    fig.update_layout(title="差评品类与主要原因", barmode="stack", yaxis=dict(autorange="reversed"), xaxis_title="差评次数")
    return ChartSpec(_chart_id("review"), "差评品类与主要原因", "plotly_stacked_bar", _source_view(name, result), _with_evidence_table(_plotly_html(fig, include_js), result), "展示Top差评品类及物流、质量、错发、客服等原因结构。")


def _table_chart(name: str, result: QueryResult) -> ChartSpec:
    return ChartSpec(_chart_id("table"), "数据明细", "table", _source_view(name, result), _table_html(result.rows), "查询结果明细表。")


def render_charts(
    results: dict[str, QueryResult],
    forecast: list[dict[str, Any]] | None = None,
    chart_requirements: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
) -> list[dict[str, str]]:
    """Return structured Plotly/Folium chart specs for the dashboard."""
    forecast = forecast or []
    chart_requirements = chart_requirements or []
    charts: list[ChartSpec] = []
    include_js = True
    for name, result in results.items():
        if not result.rows:
            continue
        columns = result.columns
        chart: ChartSpec | None = None
        if {"week_start", "total_gmv"}.issubset(columns):
            chart = _line_chart(name, result, forecast, include_js)
        elif {"year_month", "total_gmv"}.issubset(columns):
            chart = _line_chart(name, result, [], include_js)
        elif {"customer_state", "lat", "lng"}.issubset(columns):
            chart = _geo_map(name, result, chart_requirements)
        elif {"payment_type", "payment_installments"}.issubset(columns):
            chart = _heatmap_chart(name, result, include_js)
        elif {"avg_weight_g", "avg_freight"}.issubset(columns) or {"product_weight_g", "freight_value"}.issubset(columns):
            chart = _bubble_chart(name, result, include_js)
        elif "product_category_name" in columns and any(key in columns for key in ("delay_complaints", "quality_complaints", "wrong_item_complaints")):
            chart = _review_reason_chart(name, result, include_js)
        elif any(column in columns for column in ("customer_state", "product_category_name", "payment_type", "seller_state")):
            chart = _bar_chart(name, result, include_js)
        else:
            chart = _table_chart(name, result)
        charts.append(chart)
        if chart.type.startswith("plotly"):
            include_js = False
    if not charts and results:
        first_name, first_result = next(iter(results.items()))
        charts.append(_table_chart(first_name, first_result))
    return [chart.to_dict() for chart in charts]


def render_chart_gallery(
    results: dict[str, QueryResult],
    forecast: list[dict[str, Any]] | None = None,
    chart_requirements: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
) -> str:
    """Render all charts as a single HTML fragment for backward compatibility."""
    charts = render_charts(results, forecast, chart_requirements=chart_requirements)
    return "".join(f"<section class='chart-block'>{chart['html']}</section>" for chart in charts)


def render_chart_html(chart_type: str, rows: list[dict[str, Any]]) -> str:
    """Compatibility wrapper used by older tests."""
    result = QueryResult(columns=list(rows[0].keys()) if rows else [], rows=rows, elapsed_ms=0, row_count=len(rows), source="compat")
    return render_chart_gallery({"compat": result})
