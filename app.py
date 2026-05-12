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
    recommendations: list[str]
    session_id: str


def _resolve_session(session_id: str | None) -> str:
    return session_id or uuid4().hex


def _contextual_question(session_id: str, question: str) -> str:
    history = SESSIONS.get(session_id, [])
    if not history:
        return question
    previous = history[-1]
    return (
        f"当前用户问题：{question}\n\n"
        "上一轮对话上下文，可用于理解“继续、刚才、该州、这个品类”等追问：\n"
        f"上一轮问题：{previous.get('question')}\n"
        f"上一轮直接答案：{previous.get('direct_answer')}\n"
        f"上一轮命中视图：{', '.join(previous.get('matched_views', []))}\n"
        "请优先回答当前问题；只有当前问题存在指代时才引用上一轮上下文。"
    )


def _remember(session_id: str, question: str, workflow, matched_views: list[str]) -> None:
    SESSIONS.setdefault(session_id, []).append(
        {
            "question": question,
            "direct_answer": workflow.data_analysis.direct_answer,
            "summary": workflow.data_analysis.summary,
            "matched_views": matched_views,
            "sql_tasks": [{"name": task.name, "purpose": task.purpose, "sql": task.sql.strip()} for task in workflow.data_analysis.tasks],
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
    contextual_question = _contextual_question(session_id, payload.question)
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
        recommendations=workflow.recommendations,
    )


@app.websocket("/ws/analyze")
async def analyze_ws(websocket: WebSocket) -> None:
    """Stream agent milestones and optional Qwen recommendation deltas."""
    await websocket.accept()
    raw_message = await websocket.receive_text()
    try:
        payload = json.loads(raw_message)
        question = str(payload.get("question") or "").strip()
        session_id = _resolve_session(payload.get("session_id"))
    except json.JSONDecodeError:
        question = raw_message
        session_id = _resolve_session(None)
    if not question:
        await websocket.send_json({"event": "sql_error", "error": "问题不能为空"})
        await websocket.close(code=1008)
        return
    contextual_question = _contextual_question(session_id, question)
    try:
        await websocket.send_json({"event": "session", "session_id": session_id})
        await websocket.send_json({"event": "agent_start", "agent": "orchestrator"})
        plan = build_plan(contextual_question)
        await websocket.send_json({"event": "plan", "analysis_type": plan.analysis_type, "steps": list(plan.steps)})
        await websocket.send_json({"event": "agent_done", "agent": "orchestrator"})
        await websocket.send_json({"event": "agent_start", "agent": "data_analyst"})
        workflow = run_workflow(contextual_question, generate_recommendations=False)
    except DatasetValidationError as exc:
        await websocket.send_json({"event": "data_error", "error": str(exc)})
        await websocket.close(code=1011)
        return
    except LLMClientError as exc:
        await websocket.send_json({"event": "llm_error", "error": str(exc)})
        await websocket.close(code=1011)
        return
    except ValueError as exc:
        await websocket.send_json({"event": "sql_error", "error": str(exc)})
        await websocket.close(code=1011)
        return
    if workflow.plan.analysis_type != plan.analysis_type:
        await websocket.send_json({"event": "agent_start", "agent": "orchestrator_refine"})
        await websocket.send_json(
            {
                "event": "plan",
                "analysis_type": workflow.plan.analysis_type,
                "steps": list(workflow.plan.steps),
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
    await websocket.send_json({"event": "agent_done", "agent": "forecast_model", "forecast_count": len(workflow.forecast)})
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
    for event in stream_chat_completion(DECISION_MAKER_SYSTEM_PROMPT, stream_prompt, max_tokens=1100):
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
        await websocket.close(code=1011)
        return
    matched_views = sorted({view for route in workflow.data_analysis.routes.values() for view in route.matched_views})
    _remember(session_id, question, workflow, matched_views)
    await websocket.send_json({"event": "agent_done", "agent": "decision_maker"})
    await websocket.send_json({"event": "final", "streamed_llm": streamed, "forecast": workflow.forecast, "recommendations": [], "session_id": session_id})
    await websocket.close()
