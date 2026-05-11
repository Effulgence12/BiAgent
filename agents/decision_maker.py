"""DecisionMaker agent for actionable Olist operations recommendations."""

from __future__ import annotations

from typing import Any


def build_recommendations(analysis_type: str, rows: list[dict[str, Any]] | None = None, summary: str = "") -> list[str]:
    """Return data-aware recommendations that can run without an LLM key."""
    rows = rows or []
    if analysis_type == "diagnostic":
        focus = "优先定位 late_rate、avg_delivery_days 或 avg_review_score 的异常维度。"
    elif analysis_type == "predictive":
        focus = "把未来需求峰值与库存、履约产能、营销投放节奏联动。"
    elif analysis_type == "prescriptive":
        focus = "把高GMV但体验风险高的州、卖家和品类拆成可执行运营项目。"
    else:
        focus = "先建立 GMV、订单量、品类、区域与支付结构的经营基线。"

    evidence = summary or "当前问题已完成结构化查询，可在页面查看 SQL、图表与结果表。"
    if rows:
        top = rows[0]
        top_hint = ", ".join(f"{key}={value}" for key, value in list(top.items())[:4])
    else:
        top_hint = "暂无首行样例"

    return [
        f"问题定位：{focus} 数据证据：{evidence}",
        f"根因判断：首要样例为 {top_hint}；建议继续按州/品类/卖家/支付方式下钻，验证是否由物流时效、商品结构或卖家服务导致。",
        "具体行动：对高价值维度设置负责人和周度指标；对延迟率高的州调整承运商与承诺时效；对低评分卖家建立预警、培训和限流机制。预期效果是提升准时率、评分与复购转化。",
    ]
