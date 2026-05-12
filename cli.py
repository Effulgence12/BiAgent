"""Command-line entry point for offline Agentic BI validation."""

from __future__ import annotations

import argparse
import json

from agents.orchestrator import run_workflow
from utils.local_store import bootstrap_local_store, table_counts

VALIDATION_QUESTIONS = [
    "2017年GMV是多少？按月和各州排名的趋势怎样？",
    "平台整体准时交付率是多少？哪些州延迟最严重？",
    "哪种支付方式最受欢迎？平均分期数是多少？",
    "产品的重量、尺寸与运费之间有什么关系？",
    "Top10差评品类及其主要差评原因是什么？",
    "根据历史订单趋势，预测未来6周的销售额，并给出趋势解读。",
    "基于全部分析结果，给出平台3个月内的三大优先改进策略。",
    "2017年哪个州的销售额最高？交付准时率是多少？哪种支付方式最受欢迎？",
    "为什么某些州平均配送时长显著高于全国均值？哪些卖家的差评率最高？",
    "如何降低巴西东北部地区的高退货率？请给出具体的运营改进方案。",
]

EXPECTED_VIEWS = [
    ("mv_monthly_sales", "mv_state_sales"),
    ("mv_delivery_perf",),
    ("mv_payment_dist",),
    ("mv_weight_freight",),
    ("mv_review_category_perf",),
    ("mv_weekly_sales",),
    ("mv_monthly_sales", "mv_state_sales", "mv_delivery_perf", "mv_category_sales", "mv_payment_dist"),
    ("mv_state_sales", "mv_delivery_perf", "mv_payment_dist"),
    ("mv_delivery_perf", "mv_seller_perf"),
    ("mv_delivery_perf", "mv_review_category_perf"),
]

GENERAL_VALIDATION_CASES = [
    {"question": "2018年上半年每个月GMV和订单量走势如何？", "expected_any_views": ("mv_monthly_sales",)},
    {"question": "2017年第四季度哪些州GMV最高？", "expected_any_views": ("mv_state_sales", "mv_state_geo")},
    {"question": "请用地图展示各州销售额和订单量分布。", "expected_any_views": ("mv_state_geo",)},
    {"question": "SP、RJ、MG 三个州的客单价和订单量对比如何？", "expected_any_views": ("mv_state_sales", "mv_state_geo")},
    {"question": "东北部州的配送延迟情况和GMV表现有什么关系？", "expected_any_views": ("mv_delivery_perf", "mv_state_sales", "mv_state_geo")},
    {"question": "信用卡和boleto支付在订单量、金额、分期数上有什么差异？", "expected_any_views": ("mv_payment_dist",)},
    {"question": "不同支付方式和分期数的订单分布热力图应该怎么看？", "expected_any_views": ("mv_payment_dist",)},
    {"question": "health_beauty 品类销售额、订单量和评分表现如何？", "expected_any_views": ("mv_category_sales", "mv_review_category_perf")},
    {"question": "哪些品类GMV高但平均评分低，应该优先关注？", "expected_any_views": ("mv_category_sales", "mv_review_category_perf")},
    {"question": "Top 10 品类的销售额和平均客单价对比。", "expected_any_views": ("mv_category_sales",)},
    {"question": "低分评价主要集中在哪些原因类别？", "expected_any_views": ("mv_review_category_perf",)},
    {"question": "物流延迟是否会影响评价得分？请给出证据。", "expected_any_views": ("mv_delivery_perf", "mv_review_category_perf")},
    {"question": "哪些卖家的订单量较高但差评率偏高？", "expected_any_views": ("mv_seller_perf",)},
    {"question": "请下钻分析差评率最高的卖家所在州。", "expected_any_views": ("mv_seller_perf", "mv_state_sales")},
    {"question": "商品重量和运费是否正相关？请展示散点和业务解读。", "expected_any_views": ("mv_weight_freight",)},
    {"question": "重量较高但运费异常低的商品群体有哪些风险？", "expected_any_views": ("mv_weight_freight",)},
    {"question": "未来6周GMV预测是多少？需要置信区间和误差说明。", "expected_any_views": ("mv_weekly_sales", "mv_monthly_sales"), "requires_forecast": True},
    {"question": "结合月度趋势解释未来6周预测的增长或下滑原因。", "expected_any_views": ("mv_weekly_sales", "mv_monthly_sales"), "requires_forecast": True},
    {"question": "如果下个月订单量增长10%，哪些配送区域最可能成为瓶颈？", "expected_any_views": ("mv_delivery_perf", "mv_state_sales")},
    {"question": "请给出未来三个月提升准时交付率的运营优先级。", "expected_any_views": ("mv_delivery_perf", "mv_state_sales")},
    {"question": "平台整体运营健康度如何？请综合销售、配送、支付和评价分析。", "expected_any_views": ("mv_monthly_sales", "mv_delivery_perf", "mv_payment_dist", "mv_review_category_perf")},
    {"question": "展示各州销售情况地图，并指出最需要改善的州。", "expected_any_views": ("mv_state_geo", "mv_delivery_perf")},
    {"question": "哪类支付用户更可能选择高分期？这些订单金额是否更高？", "expected_any_views": ("mv_payment_dist",)},
    {"question": "请比较订单量最高州和最低州的销售表现。", "expected_any_views": ("mv_state_sales", "mv_state_geo")},
    {"question": "对刚才地图里表现最差的州继续分析配送原因。", "expected_any_views": ("mv_delivery_perf", "mv_state_geo"), "followup": True},
    {"question": "请继续分析该品类为什么评分偏低。", "expected_any_views": ("mv_review_category_perf", "mv_category_sales"), "followup": True},
]


def _validate_payload(payload: dict[str, object], expected_views: tuple[str, ...], requires_forecast: bool = False, require_all_views: bool = True) -> tuple[bool, list[str]]:
    """Return whether a validation payload satisfies the expected contract."""
    issues: list[str] = []
    matched_views = set(payload.get("matched_views") or [])
    expected = set(expected_views)
    if require_all_views:
        missing_views = sorted(expected - matched_views)
        if missing_views:
            issues.append(f"missing_views={missing_views}")
    elif expected and not (expected & matched_views):
        issues.append(f"missing_any_view={sorted(expected)}")
    if int(payload.get("sql_task_count") or 0) < 1:
        issues.append("no_sql_tasks")
    if not payload.get("has_direct_answer"):
        issues.append("missing_direct_answer")
    if not payload.get("has_chart"):
        issues.append("missing_chart")
    if not payload.get("has_summary"):
        issues.append("missing_summary")
    if requires_forecast:
        if not payload.get("has_forecast"):
            issues.append("missing_forecast")
        if not payload.get("forecast_has_interval"):
            issues.append("missing_forecast_interval")
    return not issues, issues


def _workflow_payload(question: str) -> dict[str, object]:
    """Run a question through the real workflow and return validation evidence."""
    workflow = run_workflow(question, generate_recommendations=False)
    matched_views = sorted({view for route in workflow.data_analysis.routes.values() for view in route.matched_views})
    return {
        "question": question,
        "analysis_type": workflow.plan.analysis_type,
        "intent": workflow.plan.intent,
        "required_agents": list(workflow.plan.required_agents),
        "required_views": list(workflow.plan.required_views),
        "followup_reference": workflow.plan.followup_reference,
        "matched_views": matched_views,
        "sql_task_count": len(workflow.data_analysis.tasks),
        "chart_count": len(workflow.charts),
        "has_direct_answer": bool(workflow.data_analysis.direct_answer),
        "has_summary": bool(workflow.data_analysis.summary),
        "has_chart": bool(workflow.charts) and all(chart.get("html") for chart in workflow.charts),
        "has_forecast": bool(workflow.forecast),
        "forecast_has_interval": bool(workflow.forecast) and all({"yhat", "yhat_lower", "yhat_upper"}.issubset(item) for item in workflow.forecast),
        "forecast_diagnostics": workflow.forecast_diagnostics,
        "direct_answer": workflow.data_analysis.direct_answer,
    }


def run_assignment_validation() -> list[dict[str, object]]:
    """Run the assignment appendix questions as acceptance checks."""
    results = []
    for index, question in enumerate(VALIDATION_QUESTIONS):
        payload = _workflow_payload(question)
        payload["expected_views"] = list(EXPECTED_VIEWS[index])
        passed, issues = _validate_payload(payload, EXPECTED_VIEWS[index], requires_forecast=index == 5, require_all_views=True)
        payload["passed"] = passed
        payload["issues"] = issues
        results.append(payload)
    return results


def run_general_validation() -> dict[str, object]:
    """Run non-appendix questions to check generalization beyond the required 10."""
    results = []
    for case in GENERAL_VALIDATION_CASES:
        question = str(case["question"])
        payload = _workflow_payload(question)
        expected_views = tuple(case.get("expected_any_views") or ())
        payload["expected_any_views"] = list(expected_views)
        payload["followup_case"] = bool(case.get("followup"))
        passed, issues = _validate_payload(
            payload,
            expected_views,
            requires_forecast=bool(case.get("requires_forecast")),
            require_all_views=False,
        )
        payload["passed"] = passed
        payload["issues"] = issues
        results.append(payload)
    passed_count = sum(1 for item in results if item.get("passed"))
    pass_rate = passed_count / len(results) if results else 0
    return {
        "total": len(results),
        "passed_count": passed_count,
        "pass_rate": round(pass_rate, 4),
        "target_pass_rate": 0.9,
        "passed": pass_rate >= 0.9,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Agentic BI Olist workflow locally.")
    parser.add_argument("question", nargs="?", default="2017年各月GMV趋势？", help="Natural-language business question")
    parser.add_argument("--bootstrap", action="store_true", help="Force rebuild the local SQLite analytics store before analysis")
    parser.add_argument("--validate-assignment", action="store_true", help="Run the 10 assignment appendix questions without local fallbacks")
    parser.add_argument("--validate-general", action="store_true", help="Run 25+ non-appendix questions to validate generalization")
    parser.add_argument("--no-recommendations", action="store_true", help="Skip the DecisionMaker LLM recommendation step")
    args = parser.parse_args()

    if args.bootstrap:
        source = bootstrap_local_store(force=True)
        print(json.dumps({"bootstrap_source": source, "counts": table_counts()}, ensure_ascii=False, indent=2))

    if args.validate_assignment:
        results = run_assignment_validation()
        print(json.dumps(results, ensure_ascii=False, indent=2))
        if not all(item.get("passed") for item in results):
            raise SystemExit(1)
        return

    if args.validate_general:
        report = run_general_validation()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not report.get("passed"):
            raise SystemExit(1)
        return

    workflow = run_workflow(args.question, generate_recommendations=not args.no_recommendations)
    payload = {
        "analysis_type": workflow.plan.analysis_type,
        "intent": workflow.plan.intent,
        "required_agents": workflow.plan.required_agents,
        "required_views": workflow.plan.required_views,
        "steps": workflow.plan.steps,
        "sql": workflow.data_analysis.sql,
        "route": workflow.data_analysis.route.route,
        "matched_views": workflow.data_analysis.route.matched_views,
        "direct_answer": workflow.data_analysis.direct_answer,
        "summary": workflow.data_analysis.summary,
        "rows_preview": workflow.data_analysis.result.rows[:5],
        "forecast": workflow.forecast,
        "forecast_diagnostics": workflow.forecast_diagnostics,
        "recommendations": workflow.recommendations,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
