"""Deterministic orchestrator stub for the first runnable skeleton."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisPlan:
    """Minimal plan shared by the skeleton agents."""

    analysis_type: str
    steps: tuple[str, ...]


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
    common_steps = ["DataAnalyst: route SQL with mv_* priority", "Visualizer: choose chart from result shape"]
    if analysis_type == "predictive":
        steps = common_steps + ["ForecastModel: forecast the requested time series", "DecisionMaker: summarize forecast implications"]
    elif analysis_type == "prescriptive":
        steps = common_steps + ["DecisionMaker: generate actionable recommendations"]
    elif analysis_type == "diagnostic":
        steps = ["DataAnalyst: run aggregate query", "DataAnalyst: drill down with fallback query", "DecisionMaker: explain likely root causes"]
    else:
        steps = common_steps + ["DecisionMaker: summarize descriptive findings"]
    return AnalysisPlan(analysis_type=analysis_type, steps=tuple(steps))
