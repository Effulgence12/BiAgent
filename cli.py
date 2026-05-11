"""Command-line entry point for offline Agentic BI validation."""

from __future__ import annotations

import argparse
import json

from agents.orchestrator import run_workflow
from utils.local_store import bootstrap_local_store, table_counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Agentic BI Olist workflow locally.")
    parser.add_argument("question", nargs="?", default="2017年各月GMV趋势？", help="Natural-language business question")
    parser.add_argument("--bootstrap", action="store_true", help="Force rebuild the local SQLite analytics store before analysis")
    args = parser.parse_args()

    if args.bootstrap:
        source = bootstrap_local_store(force=True)
        print(json.dumps({"bootstrap_source": source, "counts": table_counts()}, ensure_ascii=False, indent=2))

    workflow = run_workflow(args.question)
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
