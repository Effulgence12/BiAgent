"""Orchestrator agent for the runnable Agentic BI workflow."""

from __future__ import annotations

from dataclasses import dataclass

from agents.data_analyst import DataAnalysis, analyze_question
from agents.decision_maker import build_recommendations
from agents.visualizer import choose_chart, render_chart_html
from models.forecast import linear_forecast


@dataclass(frozen=True)
class AnalysisPlan:
    """Minimal plan shared by the skeleton agents."""

    analysis_type: str
    steps: tuple[str, ...]


@dataclass(frozen=True)
class WorkflowResult:
    """End-to-end multi-agent output."""

    plan: AnalysisPlan
    data_analysis: DataAnalysis
    chart_type: str
    chart_html: str
    recommendations: list[str]
    forecast: list[dict[str, float | int]]


def classify_question(question: str) -> str:
    """Classify a natural-language question into one of the four BI layers."""
    text = question.lower()
    if any(keyword in text for keyword in ("预测", "forecast", "未来", "future")):
        return "predictive"
    if any(keyword in text for keyword in ("建议", "策略", "优化", "recommend", "what-if")):
        return "prescriptive"
    if any(keyword in text for keyword in ("原因", "为什么", "延迟", "诊断", "why")):
        return "diagnostic"
    return "descriptive"


def build_plan(question: str) -> AnalysisPlan:
    """Build a conservative multi-agent execution plan for a user question."""
    analysis_type = classify_question(question)
    common_steps = ["DataAnalyst: route SQL with mv_* priority", "Visualizer: render chart/table from result shape"]
    if analysis_type == "predictive":
        steps = common_steps + ["ForecastModel: forecast requested time series", "DecisionMaker: summarize forecast implications"]
    elif analysis_type == "prescriptive":
        steps = common_steps + ["DecisionMaker: generate actionable recommendations"]
    elif analysis_type == "diagnostic":
        steps = ["DataAnalyst: run aggregate query", "DataAnalyst: inspect high-risk dimensions", "DecisionMaker: explain likely root causes"]
    else:
        steps = common_steps + ["DecisionMaker: summarize descriptive findings"]
    return AnalysisPlan(analysis_type=analysis_type, steps=tuple(steps))


def run_workflow(question: str) -> WorkflowResult:
    """Run the full local multi-agent workflow."""
    plan = build_plan(question)
    data_analysis = analyze_question(question)
    chart_type = choose_chart(data_analysis.sql)
    chart_html = render_chart_html(chart_type, data_analysis.result.rows)
    forecast = linear_forecast(data_analysis.result.rows, "total_gmv", periods=6) if plan.analysis_type == "predictive" else []
    recommendations = build_recommendations(plan.analysis_type, data_analysis.result.rows, data_analysis.summary)
    return WorkflowResult(
        plan=plan,
        data_analysis=data_analysis,
        chart_type=chart_type,
        chart_html=chart_html,
        recommendations=recommendations,
        forecast=forecast,
    )
