"""FastAPI entry point for the Agentic BI Olist application."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agents.orchestrator import build_plan, run_workflow
from config.prompts import DECISION_MAKER_SYSTEM_PROMPT
from utils.llm_client import stream_chat_completion
from utils.local_store import bootstrap_local_store, table_counts

APP_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = APP_DIR / "dashboard"

app = FastAPI(title="Agentic BI Olist", version="0.3.0")
app.mount("/static", StaticFiles(directory=DASHBOARD_DIR / "static"), name="static")


class AnalyzeRequest(BaseModel):
    """Request body for analysis endpoints."""

    question: str = Field(..., min_length=1, description="Natural-language business question.")


class AnalyzeResponse(BaseModel):
    """Structured response returned by the multi-agent workflow."""

    question: str
    analysis_type: str
    steps: list[str]
    sql: str
    route: str
    matched_views: list[str]
    chart_type: str
    chart_html: str
    summary: str
    rows: list[dict[str, Any]]
    elapsed_ms: float
    forecast: list[dict[str, float | int]]
    recommendations: list[str]


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
    """Download/generate CSVs, build the local analytics DB, and refresh mv_* tables."""
    source = bootstrap_local_store(force=force)
    return {"status": "ok", "source": source, "counts": table_counts()}


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    """Run the local multi-agent Agentic BI workflow."""
    workflow = run_workflow(payload.question)
    result = workflow.data_analysis.result
    return AnalyzeResponse(
        question=payload.question,
        analysis_type=workflow.plan.analysis_type,
        steps=list(workflow.plan.steps),
        sql=workflow.data_analysis.sql,
        route=workflow.data_analysis.route.route,
        matched_views=list(workflow.data_analysis.route.matched_views),
        chart_type=workflow.chart_type,
        chart_html=workflow.chart_html,
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
    question = await websocket.receive_text()
    plan = build_plan(question)
    await websocket.send_json({"event": "plan", "analysis_type": plan.analysis_type, "steps": list(plan.steps)})
    workflow = run_workflow(question)
    await websocket.send_json({"event": "sql", "sql": workflow.data_analysis.sql, "route": workflow.data_analysis.route.route})
    await websocket.send_json({"event": "summary", "summary": workflow.data_analysis.summary, "elapsed_ms": round(workflow.data_analysis.result.elapsed_ms, 2)})
    await websocket.send_json({"event": "chart", "chart_type": workflow.chart_type, "chart_html": workflow.chart_html})
    stream_prompt = (
        f"问题：{question}\n分析类型：{workflow.plan.analysis_type}\n"
        f"数据摘要：{workflow.data_analysis.summary}\n样例前三行：{workflow.data_analysis.result.rows[:3]}\n"
        "请流式输出3条中文运营建议，每条包含问题定位、根因、具体行动和预期效果。"
    )
    streamed = False
    for event in stream_chat_completion(DECISION_MAKER_SYSTEM_PROMPT, stream_prompt, max_tokens=420):
        if event.event == "delta":
            streamed = True
            await websocket.send_json({"event": "llm_delta", "content": event.content, "reasoning_content": event.reasoning_content})
        elif event.event == "usage":
            await websocket.send_json({"event": "llm_usage", "total_tokens": event.total_tokens})
        elif event.event == "error":
            await websocket.send_json({"event": "llm_fallback", "error": event.error})
        elif event.event == "done":
            break
    await websocket.send_json({"event": "done", "streamed_llm": streamed, "forecast": workflow.forecast, "recommendations": workflow.recommendations})
    await websocket.close()
