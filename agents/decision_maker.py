"""DecisionMaker skeleton that formats prescriptive BI recommendations."""

from __future__ import annotations


def build_recommendations(analysis_type: str) -> list[str]:
    """Return placeholder recommendations until LLM integration is wired."""
    focus = {
        "diagnostic": "优先下钻配送延迟率、差评率和高运费订单，定位异常州/卖家/品类。",
        "predictive": "将预测结果与库存、履约产能和营销节奏联动，提前准备峰值月份。",
        "prescriptive": "把预聚合视图中的高风险区域转化为负责人、动作、指标和复盘周期。",
    }.get(analysis_type, "先用预聚合视图建立GMV、订单量、品类和区域表现基线。")
    return [
        f"问题定位：{focus}",
        "根因假设：订单、物流、支付和评价链路需要通过 mv_* 视图与基础表回退查询共同验证。",
        "具体行动：下一步接入 MySQL、LLM 和 Plotly 后，将真实查询结果注入建议模板。",
    ]
