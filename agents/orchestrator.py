"""Orchestrator agent for the runnable Agentic BI workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from agents.data_analyst import DataAnalysis, analyze_question
from agents.decision_maker import build_recommendations
from agents.visualizer import choose_chart, render_charts
from langgraph.graph import END, StateGraph
from models.forecast import forecast_sales_6_weeks_with_diagnostics


@dataclass(frozen=True)
class AnalysisPlan:
    """Minimal plan shared by the skeleton agents."""

    analysis_type: str
    steps: tuple[str, ...]
    intent: str = ""
    required_agents: tuple[str, ...] = ()
    required_views: tuple[str, ...] = ()
    followup_reference: str = ""


@dataclass(frozen=True)
class WorkflowResult:
    """End-to-end multi-agent output."""

    plan: AnalysisPlan
    data_analysis: DataAnalysis
    chart_type: str
    chart_html: str
    charts: list[dict[str, str]]
    recommendations: list[str]
    forecast: list[dict[str, float | str]]
    forecast_diagnostics: dict[str, object]


class WorkflowState(TypedDict, total=False):
    """Shared state passed between LangGraph agent nodes."""

    question: str
    generate_recommendations: bool
    plan: AnalysisPlan
    data_analysis: DataAnalysis
    chart_type: str
    chart_html: str
    charts: list[dict[str, str]]
    recommendations: list[str]
    forecast: list[dict[str, float | str]]
    forecast_diagnostics: dict[str, object]


def classify_question(question: str) -> str:
    """Classify a natural-language question into one of the four BI layers."""
    text = question.lower()
    if any(keyword in text for keyword in ("预测", "forecast", "未来", "future")):
        return "predictive"
    if any(keyword in text for keyword in ("建议", "策略", "优化", "改进", "降低", "三大", "recommend", "what-if")):
        return "prescriptive"
    if any(keyword in text for keyword in ("原因", "为什么", "延迟", "诊断", "why")):
        return "diagnostic"
    return "descriptive"


def _required_views(question: str, analysis_type: str) -> tuple[str, ...]:
    text = question.lower()
    views: list[str] = []
    if any(keyword in text for keyword in ("gmv", "销售", "销售额", "趋势", "月")):
        views.extend(["mv_monthly_sales", "mv_state_sales"])
    if any(keyword in text for keyword in ("州", "地图", "地理", "巴西", "区域", "东北")):
        views.extend(["mv_state_sales", "mv_state_geo"])
    if any(keyword in text for keyword in ("配送", "交付", "延迟", "准时", "delivery")):
        views.append("mv_delivery_perf")
    if any(keyword in text for keyword in ("支付", "分期", "payment")):
        views.append("mv_payment_dist")
    if any(keyword in text for keyword in ("品类", "类目", "category")):
        views.append("mv_category_sales")
    if any(keyword in text for keyword in ("差评", "低分", "评分", "评价", "评论", "退货", "review")):
        views.append("mv_review_category_perf")
    if any(keyword in text for keyword in ("卖家", "seller")):
        views.append("mv_seller_perf")
    if any(keyword in text for keyword in ("重量", "尺寸", "体积", "运费", "weight", "freight")):
        views.append("mv_weight_freight")
    if analysis_type == "predictive":
        views.extend(["mv_monthly_sales", "mv_weekly_sales"])
    if analysis_type == "prescriptive":
        views.extend(["mv_monthly_sales", "mv_state_sales", "mv_delivery_perf", "mv_category_sales", "mv_payment_dist", "mv_review_category_perf"])
    return tuple(dict.fromkeys(views))


def _followup_reference(question: str) -> str:
    text = question.lower()
    if any(keyword in text for keyword in ("继续", "刚才", "其中", "该", "这个", "那个", "重试")):
        return "previous_turn"
    return ""


def build_plan(question: str) -> AnalysisPlan:
    """Build a conservative multi-agent execution plan for a user question."""
    analysis_type = classify_question(question)
    return _plan_for_type(analysis_type, question)


def _plan_for_type(analysis_type: str, question: str = "") -> AnalysisPlan:
    """Create the shared agent path for a chosen BI analysis type."""
    common_steps = [
        "Orchestrator: classify question and choose agent path",
        "DataAnalyst: route SQL with mv_* priority and summarize data",
        "Visualizer: render chart/table from result shape",
    ]
    required_agents = ["orchestrator", "data_analyst", "visualizer"]
    if analysis_type == "predictive":
        steps = common_steps + ["ForecastModel: forecast requested time series", "DecisionMaker: summarize forecast implications"]
        required_agents.insert(2, "forecast_model")
    elif analysis_type == "prescriptive":
        steps = common_steps + ["DecisionMaker: generate actionable recommendations"]
    elif analysis_type == "diagnostic":
        steps = common_steps + ["DecisionMaker: explain likely root causes"]
    else:
        steps = common_steps + ["DecisionMaker: summarize descriptive findings"]
    required_agents.append("decision_maker")
    return AnalysisPlan(
        analysis_type=analysis_type,
        steps=tuple(steps),
        intent=question,
        required_agents=tuple(dict.fromkeys(required_agents)),
        required_views=_required_views(question, analysis_type),
        followup_reference=_followup_reference(question),
    )


def _plan_node(state: WorkflowState) -> WorkflowState:
    return {"plan": build_plan(state["question"])}


def _data_node(state: WorkflowState) -> WorkflowState:
    return {"data_analysis": analyze_question(state["question"])}


def _refine_plan_node(state: WorkflowState) -> WorkflowState:
    """Refine the route with the LLM-planned SQL tasks instead of only keywords."""
    question = state["question"]
    data_analysis = state["data_analysis"]
    original = state["plan"]
    text = " ".join(
        [
            question.lower(),
            " ".join(task.name.lower() for task in data_analysis.tasks),
            " ".join(task.purpose.lower() for task in data_analysis.tasks),
            " ".join(column.lower() for result in data_analysis.results.values() for column in result.columns),
        ]
    )
    if {"week_start", "total_gmv"}.issubset({column for result in data_analysis.results.values() for column in result.columns}):
        analysis_type = "predictive"
    elif any(keyword in text for keyword in ("建议", "策略", "优化", "改进", "recommend", "what-if")):
        analysis_type = "prescriptive"
    elif any(keyword in text for keyword in ("late", "delay", "review", "negative", "原因", "延迟", "差评", "诊断")):
        analysis_type = "diagnostic"
    else:
        analysis_type = original.analysis_type
    if analysis_type == original.analysis_type:
        return {"plan": original}
    return {"plan": _plan_for_type(analysis_type, question)}


def _forecast_node(state: WorkflowState) -> WorkflowState:
    data_analysis = state["data_analysis"]
    weekly_result = next(
        (
            result
            for result in data_analysis.results.values()
            if {"week_start", "total_gmv"}.issubset(result.columns)
        ),
        None,
    )
    if not weekly_result:
        return {"forecast": [], "forecast_diagnostics": {"model": "ETS", "point_count": 0, "warnings": ["未命中周度GMV序列"]}}
    forecast, diagnostics = forecast_sales_6_weeks_with_diagnostics(weekly_result.rows)
    return {"forecast": forecast, "forecast_diagnostics": diagnostics}


def _visualizer_node(state: WorkflowState) -> WorkflowState:
    data_analysis = state["data_analysis"]
    forecast = state.get("forecast", [])
    charts = render_charts(data_analysis.results, forecast)
    return {
        "chart_type": choose_chart(data_analysis.sql),
        "chart_html": "".join(f"<section class='chart-block'>{chart['html']}</section>" for chart in charts),
        "charts": charts,
    }


def _decision_node(state: WorkflowState) -> WorkflowState:
    if not state.get("generate_recommendations", True):
        return {"recommendations": []}
    data_analysis = state["data_analysis"]
    plan = state["plan"]
    return {
        "recommendations": build_recommendations(
            plan.analysis_type,
            data_analysis.result.rows,
            data_analysis.summary,
            question=state["question"],
            direct_answer=data_analysis.direct_answer,
        )
    }


def _build_workflow_graph():
    """Build the explicit multi-agent orchestration graph required by the assignment."""
    graph = StateGraph(WorkflowState)
    graph.add_node("orchestrator", _plan_node)
    graph.add_node("data_analyst", _data_node)
    graph.add_node("orchestrator_refine", _refine_plan_node)
    graph.add_node("forecast_model", _forecast_node)
    graph.add_node("visualizer", _visualizer_node)
    graph.add_node("decision_maker", _decision_node)
    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", "data_analyst")
    graph.add_edge("data_analyst", "orchestrator_refine")
    graph.add_conditional_edges(
        "orchestrator_refine",
        lambda state: "forecast_model" if state["plan"].analysis_type == "predictive" else "visualizer",
        {"forecast_model": "forecast_model", "visualizer": "visualizer"},
    )
    graph.add_edge("forecast_model", "visualizer")
    graph.add_edge("visualizer", "decision_maker")
    graph.add_edge("decision_maker", END)
    return graph.compile()


WORKFLOW_GRAPH = _build_workflow_graph()


def run_workflow(question: str, generate_recommendations: bool = True) -> WorkflowResult:
    """Run the LangGraph-backed multi-agent workflow."""
    state = WORKFLOW_GRAPH.invoke({"question": question, "generate_recommendations": generate_recommendations})
    plan = state["plan"]
    data_analysis = state["data_analysis"]
    return WorkflowResult(
        plan=plan,
        data_analysis=data_analysis,
        chart_type=state["chart_type"],
        chart_html=state["chart_html"],
        charts=state["charts"],
        recommendations=state["recommendations"],
        forecast=state.get("forecast", []),
        forecast_diagnostics=state.get("forecast_diagnostics", {}),
    )
