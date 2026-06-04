"""FastAPI entry point for the Agentic BI Olist application."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4
import json

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agents.decision_maker import build_recommendation_prompt
from agents.orchestrator import build_plan, run_workflow
from config.prompts import DECISION_MAKER_SYSTEM_PROMPT
from utils.data_bootstrap import DatasetValidationError
from utils.llm_client import LLMClientError, stream_chat_completion
from utils.local_store import bootstrap_local_store, table_counts

APP_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = APP_DIR / "dashboard"

app = FastAPI(title="Agentic BI Olist", version="0.3.0")
app.mount("/static", StaticFiles(directory=DASHBOARD_DIR / "static"), name="static")

SESSIONS: dict[str, list[dict[str, Any]]] = {}


class AnalyzeRequest(BaseModel):
    """Request body for analysis endpoints."""

    question: str = Field(..., min_length=1, description="Natural-language business question.")
    session_id: str | None = Field(default=None, description="Optional conversation session id.")
    retry_of: str | None = Field(default=None, description="Optional failed request id to retry.")
    error_context: str | None = Field(default=None, description="Optional previous error used to repair SQL.")


class AnalyzeResponse(BaseModel):
    """Structured response returned by the multi-agent workflow."""

    question: str
    analysis_type: str
    steps: list[str]
    sql: str
    sql_tasks: list[dict[str, Any]]
    route: str
    matched_views: list[str]
    chart_type: str
    chart_html: str
    charts: list[dict[str, str]]
    direct_answer: str
    summary: str
    rows: list[dict[str, Any]]
    elapsed_ms: float
    forecast: list[dict[str, float | str]]
    forecast_diagnostics: dict[str, Any]
    recommendations: list[str]
    session_id: str
    planner_plan: dict[str, Any]


def _resolve_session(session_id: str | None) -> str:
    return session_id or uuid4().hex


def _memory_snapshot(session_id: str) -> dict[str, Any]:
    history = SESSIONS.get(session_id, [])
    last_turn = history[-1] if history else {}
    last_failed = next((item for item in reversed(history) if item.get("failed_turn")), {})
    return {
        "turn_count": len(history),
        "last_question": last_turn.get("question", ""),
        "last_views": last_turn.get("matched_views", []),
        "last_answer": last_turn.get("direct_answer", ""),
        "last_failed_question": last_failed.get("question", ""),
        "last_failed_error": last_failed.get("error", ""),
    }


def _needs_conversation_context(question: str, error_context: str = "") -> bool:
    """仅在真实追问或失败重试时注入历史，避免独立问题被上一轮污染。"""
    if error_context:
        return True
    text = question.lower()
    return any(
        keyword in text
        for keyword in (
            "继续",
            "刚才",
            "刚刚",
            "其中",
            "该州",
            "该品类",
            "该图",
            "该趋势",
            "这个州",
            "这个品类",
            "这个趋势",
            "那个州",
            "那个品类",
            "上述",
            "前面",
            "上轮",
            "上一轮",
            "重试",
            "原问题",
            "retry",
        )
    )


def _contextual_question(session_id: str, question: str, error_context: str = "") -> str:
    history = SESSIONS.get(session_id, [])
    if not history or not _needs_conversation_context(question, error_context):
        return f"当前用户问题：{question}\n\n上一轮失败错误：{error_context}\n请修复并回答原问题。" if error_context else question
    recent = history[-3:]
    turns = []
    for index, item in enumerate(recent, start=max(1, len(history) - len(recent) + 1)):
        tasks = item.get("sql_tasks", [])
        task_names = ", ".join(task.get("name", "") for task in tasks[:3]) if tasks else ""
        turns.append(
            "\n".join(
                [
                    f"第{index}轮问题：{item.get('question')}",
                    f"第{index}轮直答：{item.get('direct_answer')}",
                    f"第{index}轮摘要：{item.get('summary')}",
                    f"第{index}轮命中视图：{', '.join(item.get('matched_views', []))}",
                    f"第{index}轮SQL任务：{task_names}",
                    f"第{index}轮是否失败：{bool(item.get('failed_turn'))}",
                    f"第{index}轮错误：{item.get('error', '')}",
                ]
            )
        )
    return (
        f"当前用户问题：{question}\n\n"
        f"本轮重试/错误上下文：{error_context}\n\n"
        "最近对话上下文，可用于理解“继续、刚才、该州、这个品类、这个趋势”等追问：\n"
        f"{chr(10).join(turns)}\n\n"
        "请优先回答当前问题；如果这是重试，请修复并回答原问题，而不是把“重试”当作业务问题。只有当前问题存在指代、延续或省略主语时才引用历史上下文。"
    )


def _remember(session_id: str, question: str, workflow, matched_views: list[str]) -> None:
    SESSIONS.setdefault(session_id, []).append(
        {
            "question": question,
            "direct_answer": workflow.data_analysis.direct_answer,
            "summary": workflow.data_analysis.summary,
            "matched_views": matched_views,
            "sql_tasks": [{"name": task.name, "purpose": task.purpose, "sql": task.sql.strip()} for task in workflow.data_analysis.tasks],
            "planner_plan": workflow.plan.to_context(),
        }
    )
    SESSIONS[session_id] = SESSIONS[session_id][-6:]


def _remember_failed(session_id: str, question: str, error: str, error_type: str, request_id: str, retry_of: str = "") -> None:
    SESSIONS.setdefault(session_id, []).append(
        {
            "question": question,
            "direct_answer": "",
            "summary": "",
            "matched_views": [],
            "sql_tasks": [],
            "failed_turn": True,
            "error": error,
            "error_type": error_type,
            "request_id": request_id,
            "retry_of": retry_of,
        }
    )
    SESSIONS[session_id] = SESSIONS[session_id][-6:]


@app.get("/")
def index() -> FileResponse:
    """Serve the two-column dashboard."""
    return FileResponse(DASHBOARD_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check for local debugging and deployment probes."""
    return {"status": "ok", "service": "agentic-bi-olist"}


@app.post("/api/bootstrap")
def bootstrap(force: bool = False) -> dict[str, object]:
    """Validate real CSVs, build the local analytics DB, and refresh mv_* tables."""
    try:
        source = bootstrap_local_store(force=force)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=424, detail=str(exc)) from exc
    return {"status": "ok", "source": source, "counts": table_counts()}


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    """Run the local multi-agent Agentic BI workflow."""
    session_id = _resolve_session(payload.session_id)
    contextual_question = _contextual_question(session_id, payload.question, payload.error_context or "")
    try:
        workflow = run_workflow(contextual_question)
    except DatasetValidationError as exc:
        raise HTTPException(status_code=424, detail=str(exc)) from exc
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = workflow.data_analysis.result
    matched_views = sorted({view for route in workflow.data_analysis.routes.values() for view in route.matched_views})
    _remember(session_id, payload.question, workflow, matched_views)
    return AnalyzeResponse(
        question=payload.question,
        session_id=session_id,
        analysis_type=workflow.plan.analysis_type,
        steps=list(workflow.plan.steps),
        sql=workflow.data_analysis.sql,
        sql_tasks=[
            {"name": task.name, "purpose": task.purpose, "sql": task.sql.strip()}
            for task in workflow.data_analysis.tasks
        ],
        route=workflow.data_analysis.route.route,
        matched_views=matched_views,
        chart_type=workflow.chart_type,
        chart_html=workflow.chart_html,
        charts=workflow.charts,
        direct_answer=workflow.data_analysis.direct_answer,
        summary=workflow.data_analysis.summary,
        rows=result.rows,
        elapsed_ms=round(result.elapsed_ms, 2),
        forecast=workflow.forecast,
        forecast_diagnostics=workflow.forecast_diagnostics,
        recommendations=workflow.recommendations,
        planner_plan=workflow.plan.to_context(),
    )


@app.websocket("/ws/analyze")
async def analyze_ws(websocket: WebSocket) -> None:
    """Stream agent milestones and optional Qwen recommendation deltas."""
    await websocket.accept()
    raw_message = await websocket.receive_text()
    request_id = uuid4().hex
    retry_of = ""
    error_context = ""
    try:
        payload = json.loads(raw_message)
        question = str(payload.get("question") or "").strip()
        session_id = _resolve_session(payload.get("session_id"))
        retry_of = str(payload.get("retry_of") or "").strip()
        error_context = str(payload.get("error_context") or "").strip()
    except json.JSONDecodeError:
        question = raw_message
        session_id = _resolve_session(None)
    if question in {"重试", "retry", "重新执行"}:
        snapshot = _memory_snapshot(session_id)
        if snapshot.get("last_failed_question"):
            question = str(snapshot["last_failed_question"])
            error_context = error_context or str(snapshot.get("last_failed_error") or "")
    if not question:
        await websocket.send_json({"event": "sql_error", "error": "问题不能为空"})
        await websocket.close(code=1008)
        return
    contextual_question = _contextual_question(session_id, question, error_context)
    try:
        await websocket.send_json({"event": "session", "session_id": session_id, "request_id": request_id, "retry_of": retry_of})
        await websocket.send_json({"event": "memory", **_memory_snapshot(session_id)})
        await websocket.send_json({"event": "agent_start", "agent": "orchestrator"})
        plan = build_plan(contextual_question)
        await websocket.send_json(
            {
                "event": "plan",
                "analysis_type": plan.analysis_type,
                "steps": list(plan.steps),
                "intent": plan.intent,
                "required_agents": list(plan.required_agents),
                "required_views": list(plan.required_views),
                "followup_reference": plan.followup_reference,
                "metrics": list(plan.metrics),
                "dimensions": list(plan.dimensions),
                "filters": plan.filters,
                "chart_requirements": list(plan.chart_requirements),
                "confidence": plan.confidence,
                "reasoning_summary": plan.reasoning_summary,
                "planner_raw": plan.planner_raw,
            }
        )
        await websocket.send_json({"event": "agent_done", "agent": "orchestrator"})
        await websocket.send_json({"event": "agent_start", "agent": "data_analyst"})
        workflow = run_workflow(contextual_question, generate_recommendations=False, initial_plan=plan)
    except DatasetValidationError as exc:
        _remember_failed(session_id, question, str(exc), "data_error", request_id, retry_of)
        await websocket.send_json({"event": "data_error", "error": str(exc), "request_id": request_id, "question": question})
        await websocket.close(code=1011)
        return
    except LLMClientError as exc:
        _remember_failed(session_id, question, str(exc), "llm_error", request_id, retry_of)
        await websocket.send_json({"event": "llm_error", "error": str(exc), "request_id": request_id, "question": question})
        await websocket.close(code=1011)
        return
    except ValueError as exc:
        _remember_failed(session_id, question, str(exc), "sql_error", request_id, retry_of)
        await websocket.send_json({"event": "sql_error", "error": str(exc), "request_id": request_id, "question": question})
        await websocket.close(code=1011)
        return
    if workflow.plan.analysis_type != plan.analysis_type:
        await websocket.send_json({"event": "agent_start", "agent": "orchestrator_refine"})
        await websocket.send_json(
            {
                "event": "plan",
                "analysis_type": workflow.plan.analysis_type,
                "steps": list(workflow.plan.steps),
                "intent": workflow.plan.intent,
                "required_agents": list(workflow.plan.required_agents),
                "required_views": list(workflow.plan.required_views),
                "followup_reference": workflow.plan.followup_reference,
                "metrics": list(workflow.plan.metrics),
                "dimensions": list(workflow.plan.dimensions),
                "filters": workflow.plan.filters,
                "chart_requirements": list(workflow.plan.chart_requirements),
                "confidence": workflow.plan.confidence,
                "reasoning_summary": workflow.plan.reasoning_summary,
                "planner_raw": workflow.plan.planner_raw,
                "refined": True,
            }
        )
        await websocket.send_json({"event": "agent_done", "agent": "orchestrator_refine"})
    await websocket.send_json(
        {
            "event": "sql_planned",
            "sql": workflow.data_analysis.sql,
            "sql_tasks": [
                {"name": task.name, "purpose": task.purpose, "sql": task.sql.strip()}
                for task in workflow.data_analysis.tasks
            ],
            "route": workflow.data_analysis.route.route,
            "matched_views": sorted({view for route in workflow.data_analysis.routes.values() for view in route.matched_views}),
            "task_count": len(workflow.data_analysis.tasks),
        }
    )
    await websocket.send_json({"event": "agent_done", "agent": "data_analyst"})
    await websocket.send_json(
        {
            "event": "query_done",
            "summary": workflow.data_analysis.summary,
            "direct_answer": workflow.data_analysis.direct_answer,
            "elapsed_ms": round(workflow.data_analysis.result.elapsed_ms, 2),
        }
    )
    await websocket.send_json({"event": "agent_start", "agent": "forecast_model"})
    await websocket.send_json({"event": "agent_done", "agent": "forecast_model", "forecast_count": len(workflow.forecast), "forecast_diagnostics": workflow.forecast_diagnostics})
    await websocket.send_json({"event": "agent_start", "agent": "visualizer"})
    await websocket.send_json({"event": "chart_done", "chart_type": workflow.chart_type, "chart_html": workflow.chart_html, "charts": workflow.charts})
    await websocket.send_json({"event": "agent_done", "agent": "visualizer"})
    stream_prompt = build_recommendation_prompt(
        workflow.plan.analysis_type,
        workflow.data_analysis.summary,
        question=question,
        direct_answer=workflow.data_analysis.direct_answer,
        rows=workflow.data_analysis.result.rows,
    )
    streamed = False
    llm_error = ""
    await websocket.send_json({"event": "agent_start", "agent": "decision_maker"})
    for event in stream_chat_completion(DECISION_MAKER_SYSTEM_PROMPT, stream_prompt, timeout=120, max_tokens=1100):
        if event.event == "delta":
            streamed = True
            await websocket.send_json({"event": "llm_delta", "content": event.content, "reasoning_content": event.reasoning_content})
        elif event.event == "usage":
            await websocket.send_json({"event": "llm_usage", "total_tokens": event.total_tokens})
        elif event.event == "error":
            llm_error = event.error
            await websocket.send_json({"event": "llm_error", "error": event.error})
            break
        elif event.event == "done":
            break
    if llm_error:
        _remember_failed(session_id, question, llm_error, "llm_error", request_id, retry_of)
        await websocket.close(code=1011)
        return
    matched_views = sorted({view for route in workflow.data_analysis.routes.values() for view in route.matched_views})
    _remember(session_id, question, workflow, matched_views)
    await websocket.send_json({"event": "memory_updated", **_memory_snapshot(session_id)})
    await websocket.send_json({"event": "agent_done", "agent": "decision_maker"})
    await websocket.send_json(
        {
            "event": "final",
            "streamed_llm": streamed,
            "forecast": workflow.forecast,
            "forecast_diagnostics": workflow.forecast_diagnostics,
            "recommendations": [],
            "session_id": session_id,
            "request_id": request_id,
        }
    )
    await websocket.close()
