"""Visualization agent with dependency-free HTML/SVG chart rendering."""

from __future__ import annotations

from html import escape
from typing import Any


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
    if "product_weight_g" in lowered and "freight_value" in lowered:
        return "scatter"
    return "table"


def _as_float(value: object) -> float:
    try:
        return float(value) if value not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def _table_html(rows: list[dict[str, Any]], limit: int = 20) -> str:
    if not rows:
        return "<p>无数据可展示。</p>"
    columns = list(rows[0].keys())
    header = "".join(f"<th>{escape(str(column))}</th>" for column in columns)
    body = []
    for row in rows[:limit]:
        body.append("<tr>" + "".join(f"<td>{escape(str(row.get(column, '')))}</td>" for column in columns) + "</tr>")
    return f"<table class='data-table'><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _bar_svg(rows: list[dict[str, Any]], label_key: str, value_key: str, title: str, limit: int = 12) -> str:
    data = rows[:limit]
    if not data:
        return "<p>无数据可展示。</p>"
    width, row_height, left, right = 760, 34, 170, 30
    height = 60 + len(data) * row_height
    max_value = max(_as_float(row.get(value_key)) for row in data) or 1.0
    bars = [f"<text x='{left}' y='28' font-size='16' font-weight='700'>{escape(title)}</text>"]
    for idx, row in enumerate(data):
        y = 50 + idx * row_height
        value = _as_float(row.get(value_key))
        bar_width = int((width - left - right) * value / max_value)
        label = escape(str(row.get(label_key, ""))[:24])
        bars.append(f"<text x='8' y='{y + 18}' font-size='12'>{label}</text>")
        bars.append(f"<rect x='{left}' y='{y}' width='{bar_width}' height='22' rx='5' fill='#2a6fbb'></rect>")
        bars.append(f"<text x='{left + bar_width + 6}' y='{y + 16}' font-size='12'>{value:,.0f}</text>")
    return f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='{escape(title)}'>{''.join(bars)}</svg>"


def _line_svg(rows: list[dict[str, Any]], x_key: str, y_key: str, title: str) -> str:
    data = rows[-36:]
    if len(data) < 2:
        return _table_html(rows)
    width, height, pad = 780, 360, 45
    values = [_as_float(row.get(y_key)) for row in data]
    min_v, max_v = min(values), max(values)
    span = max(max_v - min_v, 1.0)
    points = []
    for idx, value in enumerate(values):
        x = pad + idx * (width - 2 * pad) / (len(values) - 1)
        y = height - pad - (value - min_v) * (height - 2 * pad) / span
        points.append(f"{x:.1f},{y:.1f}")
    labels = "".join(
        f"<text x='{pad + idx * (width - 2 * pad) / max(len(data)-1, 1):.1f}' y='{height - 12}' font-size='10' text-anchor='middle'>{escape(str(row.get(x_key, '')))}</text>"
        for idx, row in enumerate(data)
        if idx % max(1, len(data) // 8) == 0
    )
    return f"""
    <svg viewBox='0 0 {width} {height}' role='img' aria-label='{escape(title)}'>
      <text x='{pad}' y='24' font-size='16' font-weight='700'>{escape(title)}</text>
      <line x1='{pad}' y1='{height-pad}' x2='{width-pad}' y2='{height-pad}' stroke='#9aa8bd'/>
      <line x1='{pad}' y1='{pad}' x2='{pad}' y2='{height-pad}' stroke='#9aa8bd'/>
      <polyline points='{' '.join(points)}' fill='none' stroke='#1f6feb' stroke-width='3'/>
      {labels}
      <text x='{pad}' y='{pad-8}' font-size='11'>{max_v:,.0f}</text>
      <text x='{pad}' y='{height-pad+18}' font-size='11'>{min_v:,.0f}</text>
    </svg>
    """


def _scatter_svg(rows: list[dict[str, Any]], x_key: str, y_key: str, title: str, limit: int = 160) -> str:
    data = rows[:limit]
    if not data:
        return "<p>无数据可展示。</p>"
    width, height, pad = 760, 360, 45
    xs = [_as_float(row.get(x_key)) for row in data]
    ys = [_as_float(row.get(y_key)) for row in data]
    max_x, max_y = max(xs) or 1.0, max(ys) or 1.0
    dots = []
    for x_value, y_value in zip(xs, ys):
        x = pad + x_value * (width - 2 * pad) / max_x
        y = height - pad - y_value * (height - 2 * pad) / max_y
        dots.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='3' fill='#1f6feb' opacity='0.5'></circle>")
    return f"<svg viewBox='0 0 {width} {height}'><text x='{pad}' y='24' font-size='16' font-weight='700'>{escape(title)}</text><line x1='{pad}' y1='{height-pad}' x2='{width-pad}' y2='{height-pad}' stroke='#9aa8bd'/><line x1='{pad}' y1='{pad}' x2='{pad}' y2='{height-pad}' stroke='#9aa8bd'/>{''.join(dots)}</svg>"


def render_chart_html(chart_type: str, rows: list[dict[str, Any]]) -> str:
    """Render a small embeddable HTML chart for the dashboard."""
    if chart_type == "line":
        return _line_svg(rows, "year_month", "total_gmv", "月度GMV趋势") + _table_html(rows)
    if chart_type == "bar_or_choropleth":
        return _bar_svg(rows, "customer_state", "total_gmv", "州维度GMV排名") + _table_html(rows)
    if chart_type == "horizontal_bar":
        return _bar_svg(rows, "product_category_name", "total_gmv", "品类GMV Top") + _table_html(rows)
    if chart_type == "bar_with_late_rate":
        return _bar_svg(rows, "customer_state", "late_rate", "配送延迟率") + _table_html(rows)
    if chart_type == "heatmap_or_donut":
        return _bar_svg(rows, "payment_type", "payment_value", "支付方式金额分布") + _table_html(rows)
    if chart_type == "scatter":
        return _scatter_svg(rows, "product_weight_g", "freight_value", "重量 vs 运费") + _table_html(rows)
    return _table_html(rows)
