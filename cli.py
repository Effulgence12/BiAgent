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


def run_assignment_validation() -> list[dict[str, object]]:
    """Run the assignment appendix questions as acceptance checks."""
    results = []
    for question in VALIDATION_QUESTIONS:
        workflow = run_workflow(question, generate_recommendations=False)
        matched_views = sorted({view for route in workflow.data_analysis.routes.values() for view in route.matched_views})
        results.append(
            {
                "question": question,
                "analysis_type": workflow.plan.analysis_type,
                "matched_views": matched_views,
                "sql_task_count": len(workflow.data_analysis.tasks),
                "has_direct_answer": bool(workflow.data_analysis.direct_answer),
                "has_chart": "<" in workflow.chart_html,
                "has_forecast": bool(workflow.forecast),
                "direct_answer": workflow.data_analysis.direct_answer,
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Agentic BI Olist workflow locally.")
    parser.add_argument("question", nargs="?", default="2017年各月GMV趋势？", help="Natural-language business question")
    parser.add_argument("--bootstrap", action="store_true", help="Force rebuild the local SQLite analytics store before analysis")
    parser.add_argument("--validate-assignment", action="store_true", help="Run the 10 assignment appendix questions without local fallbacks")
    parser.add_argument("--no-recommendations", action="store_true", help="Skip the DecisionMaker LLM recommendation step")
    args = parser.parse_args()

    if args.bootstrap:
        source = bootstrap_local_store(force=True)
        print(json.dumps({"bootstrap_source": source, "counts": table_counts()}, ensure_ascii=False, indent=2))

    if args.validate_assignment:
        print(json.dumps(run_assignment_validation(), ensure_ascii=False, indent=2))
        return

    workflow = run_workflow(args.question, generate_recommendations=not args.no_recommendations)
    payload = {
        "analysis_type": workflow.plan.analysis_type,
        "steps": workflow.plan.steps,
        "sql": workflow.data_analysis.sql,
        "route": workflow.data_analysis.route.route,
        "matched_views": workflow.data_analysis.route.matched_views,
        "summary": workflow.data_analysis.summary,
        "rows_preview": workflow.data_analysis.result.rows[:5],
        "forecast": workflow.forecast,
        "recommendations": workflow.recommendations,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
