"""What-if 反事实模拟引擎（任务书加分项）。

反事实推演的本质：给定一个假设干预（如"下架评分最低的若干卖家"），在真实数据上
排除该子群体后重新计算平台级指标，给出"干预前 → 干预后"的对比。

这里的所有计算都是真实只读 SQL 聚合，不做任何模拟编造：基线和反事实都来自同一批
真实订单/评价，差异只来自"排除哪一批数据"。场景的选择与解读交给大模型（见
orchestrator 的 whatif Agent 节点），计算本身保持确定性、可复现。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from utils.local_store import run_query


@dataclass(frozen=True)
class WhatIfResult:
    """一次反事实模拟的结构化结果。"""

    scenario_id: str
    scenario_label: str
    metric_label: str
    unit: str
    baseline: float
    scenario: float
    delta: float
    direction: str
    params: dict[str, Any]
    affected_label: str
    affected_count: int
    affected_share: float
    narrative: str
    detail_rows: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fetch_row(sql: str) -> dict[str, Any]:
    result = run_query(sql)
    return result.rows[0] if result.rows else {}


def _combined_score_sql(keep_expr: str) -> str:
    """一趟扫描同时算出干预前后平均评分：keep=1 的评价代表干预后仍保留的订单。

    比分两条 SQL 各扫一遍快近一倍；NOT EXISTS/CASE 只对每条评价求值一次。
    """
    return f"""
    SELECT ROUND(AVG(CAST(review_score AS REAL)), 4) AS base_score,
           COUNT(*) AS base_n,
           ROUND(AVG(CASE WHEN keep = 1 THEN CAST(review_score AS REAL) END), 4) AS scen_score,
           SUM(keep) AS scen_n
    FROM (
      SELECT r.review_score AS review_score, {keep_expr} AS keep
      FROM order_reviews r
      JOIN orders o ON r.order_id = o.order_id
      WHERE o.order_status = 'delivered' AND r.review_score <> ''
    ) labeled
    """


def _build_score_result(
    *,
    scenario_id: str,
    scenario_label: str,
    affected_label: str,
    params: dict[str, Any],
    combined: dict[str, Any],
    detail_rows: list[dict[str, Any]],
) -> WhatIfResult:
    """把一趟查询得到的干预前后聚合整理成结构化对比。"""
    base_val = round(float(combined.get("base_score") or 0.0), 3)
    scen_val = round(float(combined.get("scen_score") or 0.0), 3)
    base_n = int(combined.get("base_n") or 0)
    scen_n = int(combined.get("scen_n") or 0)
    delta = round(scen_val - base_val, 3)
    affected = max(0, base_n - scen_n)
    share = round(affected / base_n, 4) if base_n else 0.0
    direction = "提升" if delta > 0 else ("下降" if delta < 0 else "基本不变")
    narrative = (
        f"{scenario_label}后，平台整体平均评分将从 {base_val:.3f} {direction}到 {scen_val:.3f}"
        f"（变化 {delta:+.3f} 分），相当于剔除 {affected} 条{affected_label}、占全部评价的 {share * 100:.1f}%。"
    )
    return WhatIfResult(
        scenario_id=scenario_id,
        scenario_label=scenario_label,
        metric_label="平台整体平均评分",
        unit="分",
        baseline=base_val,
        scenario=scen_val,
        delta=delta,
        direction=direction,
        params=params,
        affected_label=affected_label,
        affected_count=affected,
        affected_share=share,
        narrative=narrative,
        detail_rows=detail_rows,
    )


def _run_delist_low_rating_sellers(top_n: int = 20, min_orders: int = 5) -> WhatIfResult:
    """反事实：下架评分最低的 Top-N 卖家后，平台整体平均评分如何变化。"""
    top_n = max(1, min(int(top_n or 20), 100))
    min_orders = max(1, min(int(min_orders or 5), 100))
    # 视图优先：直接从预聚合的 mv_seller_perf 选出最差卖家（毫秒级），不下钻全量基础表。
    detail = run_query(
        f"""
        SELECT seller_id,
               SUM(total_orders) AS orders,
               ROUND(AVG(avg_review_score), 3) AS avg_score
        FROM mv_seller_perf
        GROUP BY seller_id
        HAVING orders >= {min_orders}
        ORDER BY avg_score ASC, orders DESC
        LIMIT {top_n}
        """
    ).rows
    worst_ids = [str(row.get("seller_id")) for row in detail if row.get("seller_id")]
    if worst_ids:
        in_list = ", ".join("'" + sid.replace("'", "''") + "'" for sid in worst_ids)
        # seller_id 前的 + 一元前缀禁止其走索引，强制按 order_items(order_id) 索引相关，
        # 避免 SQLite 误选 seller_id 索引导致每条评价都重扫这批卖家的全部商品。
        keep_expr = (
            "CASE WHEN NOT EXISTS ("
            f"SELECT 1 FROM order_items oi WHERE oi.order_id = r.order_id AND +oi.seller_id IN ({in_list})"
            ") THEN 1 ELSE 0 END"
        )
    else:
        keep_expr = "1"
    combined = _fetch_row(_combined_score_sql(keep_expr))
    return _build_score_result(
        scenario_id="delist_low_rating_sellers",
        scenario_label=f"下架评分最低的 {len(worst_ids)} 个卖家（每个卖家累计至少 {min_orders} 单）",
        affected_label="差评/低分订单评价",
        params={"top_n": top_n, "min_orders": min_orders},
        combined=combined,
        detail_rows=detail,
    )


def _run_resolve_late_deliveries() -> WhatIfResult:
    """反事实：如果所有延迟订单都按时送达，平台整体平均评分如何变化。"""
    keep_expr = (
        "CASE WHEN ("
        "o.order_delivered_customer_date <> '' "
        "AND o.order_estimated_delivery_date <> '' "
        "AND o.order_delivered_customer_date > o.order_estimated_delivery_date"
        ") THEN 0 ELSE 1 END"
    )
    combined = _fetch_row(_combined_score_sql(keep_expr))
    detail = run_query(
        """
        SELECT ROUND(AVG(CAST(r.review_score AS REAL)), 3) AS late_avg_score, COUNT(*) AS late_reviews
        FROM order_reviews r
        JOIN orders o ON r.order_id = o.order_id
        WHERE o.order_status = 'delivered' AND r.review_score <> ''
          AND o.order_delivered_customer_date <> ''
          AND o.order_estimated_delivery_date <> ''
          AND o.order_delivered_customer_date > o.order_estimated_delivery_date
        """
    ).rows
    return _build_score_result(
        scenario_id="resolve_late_deliveries",
        scenario_label="如果消除所有延迟订单（让其全部按时送达）",
        affected_label="延迟订单评价",
        params={},
        combined=combined,
        detail_rows=detail,
    )


# 反事实场景注册表：label/hint 供大模型选择，runner 为确定性计算函数。
SCENARIOS: dict[str, dict[str, Any]] = {
    "delist_low_rating_sellers": {
        "label": "下架评分最低的若干卖家 → 平台平均评分变化",
        "hint": "下架/移除/剔除评分最低（差评最多）的 Top-N 卖家后，平台整体平均评分会提升多少。参数 top_n（默认 20）、min_orders（默认 5）。",
        "runner": _run_delist_low_rating_sellers,
        "params": {"top_n": 20, "min_orders": 5},
    },
    "resolve_late_deliveries": {
        "label": "消除延迟订单 → 平台平均评分变化",
        "hint": "如果所有延迟订单都按时送达，平台整体平均评分会提升多少。无参数。",
        "runner": _run_resolve_late_deliveries,
        "params": {},
    },
}

WHATIF_MARKERS = ("如果", "假设", "假如", "若", "倘若", "what-if", "what if", "下架", "移除", "剔除", "砍掉", "停用")


def detect_whatif(question: str) -> bool:
    """轻量关键词护栏：判断问题是否包含反事实/假设性意图。"""
    text = question.lower()
    return any(marker in text for marker in WHATIF_MARKERS)


def default_scenario(question: str) -> tuple[str, dict[str, Any]]:
    """大模型选择失败时的确定性兜底：按关键词映射到最贴近的场景。"""
    text = question.lower()
    if any(keyword in text for keyword in ("延迟", "配送", "准时", "物流", "履约", "late", "delivery")):
        return "resolve_late_deliveries", {}
    if any(keyword in text for keyword in ("卖家", "seller", "差评", "评分", "评价", "review")):
        return "delist_low_rating_sellers", {}
    return "", {}


def run_whatif(scenario_id: str, params: dict[str, Any] | None = None) -> WhatIfResult:
    """执行一个已注册的反事实场景。"""
    spec = SCENARIOS.get(scenario_id)
    if not spec:
        raise ValueError(f"未知的 What-if 场景：{scenario_id}")
    merged = {**spec["params"], **(params or {})}
    kwargs = {key: merged[key] for key in spec["params"]}
    return spec["runner"](**kwargs)
