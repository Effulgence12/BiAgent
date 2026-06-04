"""Orchestrator agent for the runnable Agentic BI workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import json
import re
from typing import Any, TypedDict

from agents.data_analyst import DataAnalysis, analyze_question
from agents.decision_maker import build_recommendations
from agents.visualizer import choose_chart, render_charts
from config.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from langgraph.graph import END, StateGraph
from models.forecast import forecast_sales_6_weeks_with_diagnostics
from utils.llm_client import chat_completion
from utils.schema import render_schema_context


ANALYSIS_TYPES = {"descriptive", "diagnostic", "predictive", "prescriptive"}
KNOWN_AGENTS = {"orchestrator", "data_analyst", "forecast_model", "visualizer", "decision_maker"}
KNOWN_VIEWS = {
    "mv_monthly_sales",
    "mv_state_sales",
    "mv_category_sales",
    "mv_delivery_perf",
    "mv_seller_perf",
    "mv_payment_dist",
    "mv_weekly_sales",
    "mv_state_geo",
    "mv_review_category_perf",
    "mv_weight_freight",
}


@dataclass(frozen=True)
class AnalysisPlan:
    """LLM-generated structured plan shared by all downstream agents."""

    analysis_type: str
    steps: tuple[str, ...]
    intent: str = ""
    required_agents: tuple[str, ...] = ()
    required_views: tuple[str, ...] = ()
    followup_reference: str = ""
    metrics: tuple[str, ...] = ()
    dimensions: tuple[str, ...] = ()
    filters: dict[str, Any] = field(default_factory=dict)
    chart_requirements: tuple[dict[str, Any], ...] = ()
    confidence: float = 0.0
    reasoning_summary: str = ""
    planner_raw: dict[str, Any] = field(default_factory=dict)

    def to_context(self) -> dict[str, Any]:
        """Return a JSON-serializable plan for prompts, API events, and UI evidence."""
        return asdict(self)


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
    """Keyword guardrail kept for tests and validation, not the primary planner."""
    text = question.lower()
    if any(keyword in text for keyword in ("预测", "forecast", "未来", "future", "未来6周", "未来 6 周")):
        return "predictive"
    if any(keyword in text for keyword in ("建议", "策略", "优化", "改进", "降低", "三大", "recommend", "what-if")):
        return "prescriptive"
    if any(keyword in text for keyword in ("原因", "为什么", "延迟", "诊断", "why", "差评")):
        return "diagnostic"
    return "descriptive"


def _required_views(question: str, analysis_type: str) -> tuple[str, ...]:
    """Rule-based view hints used only as guardrails around the LLM plan."""
    text = question.lower()
    views: list[str] = []
    if any(keyword in text for keyword in ("gmv", "销售", "销售额", "趋势", "月")):
        views.extend(["mv_monthly_sales", "mv_state_sales"])
    if any(keyword in text for keyword in ("州", "地图", "地理", "巴西", "区域", "东北")):
        views.extend(["mv_state_sales", "mv_state_geo"])
    if any(keyword in text for keyword in ("配送", "交付", "延迟", "准时", "履约", "delivery", "物流")):
        views.append("mv_delivery_perf")
    if any(keyword in text for keyword in ("支付", "分期", "payment")):
        views.append("mv_payment_dist")
    if any(keyword in text for keyword in ("品类", "类目", "category")):
        views.append("mv_category_sales")
    if any(keyword in text for keyword in ("差评", "低分", "评分", "评价", "评论", "退货", "review", "体验")):
        views.append("mv_review_category_perf")
    if any(keyword in text for keyword in ("卖家", "seller")):
        views.append("mv_seller_perf")
    if any(keyword in text for keyword in ("重量", "尺寸", "体积", "运费", "weight", "freight")):
        views.append("mv_weight_freight")
    if analysis_type == "predictive":
        views.extend(["mv_monthly_sales", "mv_weekly_sales"])
    if analysis_type == "prescriptive":
        views.extend(["mv_monthly_sales", "mv_state_sales", "mv_delivery_perf", "mv_category_sales", "mv_payment_dist", "mv_review_category_perf"])
    return tuple(dict.fromkeys(view for view in views if view in KNOWN_VIEWS))


def _followup_reference(question: str) -> str:
    """Rule-based context hint used only as a guardrail around the LLM plan."""
    text = question.lower()
    if any(keyword in text for keyword in ("继续", "刚才", "刚刚", "其中", "该", "这个", "那个", "重试", "上轮", "前面")):
        return "previous_turn"
    return ""


def _extract_json_object(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Orchestrator Planner 未返回 JSON 对象，无法生成多 Agent 计划")
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Orchestrator Planner JSON 解析失败：{exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Orchestrator Planner 返回值不是 JSON 对象")
    return parsed


def _as_string_tuple(value: object, *, limit: int = 12, allowed: set[str] | None = None) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    items: list[str] = []
    for raw in value[:limit]:
        item = str(raw).strip()
        if not item:
            continue
        if allowed and item not in allowed:
            continue
        items.append(item)
    return tuple(dict.fromkeys(items))


def _as_chart_requirements(value: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    requirements: list[dict[str, Any]] = []
    for raw in value[:8]:
        if not isinstance(raw, dict):
            continue
        requirement = {
            "chart_type": str(raw.get("chart_type") or raw.get("type") or "").strip(),
            "metric": str(raw.get("metric") or "").strip(),
            "dimension": str(raw.get("dimension") or "").strip(),
            "source_view": str(raw.get("source_view") or "").strip(),
            "purpose": str(raw.get("purpose") or "").strip(),
        }
        requirements.append({key: val for key, val in requirement.items() if val})
    return tuple(requirements)


def _steps_for_agents(required_agents: tuple[str, ...], analysis_type: str) -> tuple[str, ...]:
    labels = {
        "orchestrator": "Orchestrator: use LLM structured planning to parse intent and choose agent path",
        "data_analyst": "DataAnalyst: generate view-first SQL from the planner output and summarize evidence",
        "forecast_model": "ForecastModel: build ETS forecast and expose diagnostics when a future series is required",
        "visualizer": "Visualizer: render charts from planner chart requirements and query result shape",
        "decision_maker": "DecisionMaker: generate data-grounded recommendations with the real LLM",
    }
    ordered = [agent for agent in ("orchestrator", "data_analyst", "forecast_model", "visualizer", "decision_maker") if agent in required_agents]
    if analysis_type != "predictive":
        ordered = [agent for agent in ordered if agent != "forecast_model"]
    return tuple(labels[agent] for agent in ordered)


def _normalize_plan(payload: dict[str, Any], question: str) -> AnalysisPlan:
    analysis_type = str(payload.get("analysis_type") or "").strip().lower()
    if analysis_type not in ANALYSIS_TYPES:
        raise ValueError(f"Orchestrator Planner 返回了无效 analysis_type：{analysis_type or '<empty>'}")

    required_agents = _as_string_tuple(payload.get("required_agents"), allowed=KNOWN_AGENTS)
    if "data_analyst" not in required_agents or "visualizer" not in required_agents:
        raise ValueError("Orchestrator Planner 缺少必需 Agent：data_analyst / visualizer")
    if "orchestrator" not in required_agents:
        required_agents = ("orchestrator", *required_agents)
    if "decision_maker" not in required_agents:
        required_agents = (*required_agents, "decision_maker")
    if analysis_type == "predictive" and "forecast_model" not in required_agents:
        required_agents = (*required_agents, "forecast_model")
    if analysis_type != "predictive":
        required_agents = tuple(agent for agent in required_agents if agent != "forecast_model")

    required_views = _as_string_tuple(payload.get("required_views"), allowed=KNOWN_VIEWS)
    if not required_views:
        raise ValueError("Orchestrator Planner 缺少 required_views，无法证明视图优先规划")
    # 本地规则只补明显缺口，不替代 LLM 的主判断。
    guardrail_views = _required_views(question, analysis_type)
    required_views = tuple(dict.fromkeys((*required_views, *guardrail_views)))

    followup_reference = str(payload.get("followup_reference") or "").strip()
    if not followup_reference:
        followup_reference = _followup_reference(question)

    filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
    try:
        confidence = float(payload.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0

    return AnalysisPlan(
        analysis_type=analysis_type,
        steps=_steps_for_agents(required_agents, analysis_type),
        intent=str(payload.get("intent") or question).strip(),
        required_agents=tuple(dict.fromkeys(required_agents)),
        required_views=required_views,
        followup_reference=followup_reference,
        metrics=_as_string_tuple(payload.get("metrics")),
        dimensions=_as_string_tuple(payload.get("dimensions")),
        filters=filters,
        chart_requirements=_as_chart_requirements(payload.get("chart_requirements")),
        confidence=max(0.0, min(1.0, confidence)),
        reasoning_summary=str(payload.get("reasoning_summary") or "").strip(),
        planner_raw=payload,
    )


def build_plan(question: str) -> AnalysisPlan:
    """Ask the real LLM to produce the Orchestrator's structured agent plan."""
    prompt = f"""
用户问题：{question}

数据字典：
{render_schema_context()}

请作为 Agentic BI 协调器生成结构化计划。要求：
1. 只返回 JSON，不要 Markdown。
2. analysis_type 只能是 descriptive、diagnostic、predictive、prescriptive。
3. required_agents 必须从 orchestrator、data_analyst、forecast_model、visualizer、decision_maker 中选择；至少包含 data_analyst、visualizer、decision_maker。
4. required_views 必须优先选择 mv_* 预聚合视图；只有视图无法覆盖时才由 DataAnalyst 后续回退基础表。
5. chart_requirements 要写明图表类型、指标、维度、来源视图。地图题请明确 metric，例如 sales_gmv、delivery_late_rate、delivery_on_time_rate、seller_review_risk。
6. 预测题必须包含 forecast_model、mv_weekly_sales，并要求输出置信区间。
7. 追问题用 followup_reference="previous_turn"，独立新问题用空字符串。

JSON 格式：
{{
  "analysis_type": "diagnostic",
  "intent": "一句话概括用户真实意图",
  "metrics": ["delivery_late_rate"],
  "dimensions": ["customer_state"],
  "filters": {{"time_range": "", "states": [], "categories": []}},
  "required_agents": ["orchestrator", "data_analyst", "visualizer", "decision_maker"],
  "required_views": ["mv_state_geo", "mv_delivery_perf"],
  "chart_requirements": [
    {{"chart_type": "folium_map", "metric": "delivery_late_rate", "dimension": "customer_state", "source_view": "mv_state_geo + mv_delivery_perf", "purpose": "展示延迟配送风险州"}}
  ],
  "followup_reference": "",
  "confidence": 0.9,
  "reasoning_summary": "一句话说明为什么这样分派 Agent 和视图"
}}
""".strip()
    response = chat_completion(ORCHESTRATOR_SYSTEM_PROMPT, prompt, max_tokens=1500)
    return _normalize_plan(_extract_json_object(response.content), question)


def _plan_node(state: WorkflowState) -> WorkflowState:
    if "plan" in state:
        return {"plan": state["plan"]}
    return {"plan": build_plan(state["question"])}


def _data_node(state: WorkflowState) -> WorkflowState:
    return {"data_analysis": analyze_question(state["question"], plan_context=state["plan"].to_context())}


def _refine_plan_node(state: WorkflowState) -> WorkflowState:
    """Validate the LLM plan against executed data without replacing it by keyword routing."""
    data_analysis = state["data_analysis"]
    original = state["plan"]
    columns = {column for result in data_analysis.results.values() for column in result.columns}
    if {"week_start", "total_gmv"}.issubset(columns) and original.analysis_type != "predictive":
        required_agents = tuple(dict.fromkeys((*original.required_agents, "forecast_model")))
        return {"plan": replace(original, analysis_type="predictive", required_agents=required_agents, steps=_steps_for_agents(required_agents, "predictive"))}
    return {"plan": original}


def _forecast_node(state: WorkflowState) -> WorkflowState:
    data_analysis = state["data_analysis"]
    def forecast_score(task_name: str, result: Any) -> int:
        if not {"week_start", "total_gmv"}.issubset(result.columns):
            return -1
        valid_rows = sum(1 for row in result.rows if row.get("week_start") and row.get("total_gmv") not in (None, ""))
        if valid_rows <= 0:
            return -1
        name_bonus = 100 if any(keyword in task_name.lower() for keyword in ("weekly", "forecast", "预测")) else 0
        return name_bonus + valid_rows

    weekly_candidates = [
        (forecast_score(task_name, result), result)
        for task_name, result in data_analysis.results.items()
    ]
    weekly_result = max(weekly_candidates, key=lambda item: item[0])[1] if weekly_candidates else None
    if weekly_candidates and max(score for score, _result in weekly_candidates) < 0:
        weekly_result = None
    if not weekly_result:
        return {"forecast": [], "forecast_diagnostics": {"model": "ETS", "point_count": 0, "warnings": ["未命中周度 GMV 序列"]}}
    forecast, diagnostics = forecast_sales_6_weeks_with_diagnostics(weekly_result.rows)
    return {"forecast": forecast, "forecast_diagnostics": diagnostics}


def _visualizer_node(state: WorkflowState) -> WorkflowState:
    data_analysis = state["data_analysis"]
    forecast = state.get("forecast", [])
    chart_requirements = state["plan"].chart_requirements
    charts = render_charts(data_analysis.results, forecast, chart_requirements=chart_requirements)
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


def run_workflow(question: str, generate_recommendations: bool = True, initial_plan: AnalysisPlan | None = None) -> WorkflowResult:
    """Run the LangGraph-backed multi-agent workflow."""
    initial_state: WorkflowState = {"question": question, "generate_recommendations": generate_recommendations}
    if initial_plan is not None:
        initial_state["plan"] = initial_plan
    state = WORKFLOW_GRAPH.invoke(initial_state)
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
