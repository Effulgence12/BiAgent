"""FastAPI entry point for the Agentic BI Olist skeleton."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agents.data_analyst import draft_sql
from agents.decision_maker import build_recommendations
from agents.orchestrator import build_plan
from agents.visualizer import choose_chart

APP_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = APP_DIR / "dashboard"

app = FastAPI(title="Agentic BI Olist", version="0.1.0")
app.mount("/static", StaticFiles(directory=DASHBOARD_DIR / "static"), name="static")


class AnalyzeRequest(BaseModel):
    """Request body for the synchronous skeleton analysis endpoint."""

    question: str = Field(..., min_length=1, description="Natural-language business question.")


class AnalyzeResponse(BaseModel):
    """Structured response returned by the skeleton agents."""

    question: str
    analysis_type: str
    steps: list[str]
    sql: str
    route: str
    matched_views: list[str]
    chart_type: str
    recommendations: list[str]


@app.get("/")
def index() -> FileResponse:
    """Serve the two-column dashboard shell."""
    return FileResponse(DASHBOARD_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check for local debugging and deployment probes."""
    return {"status": "ok", "service": "agentic-bi-olist"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    """Run the deterministic first-pass agent workflow without external services."""
    plan = build_plan(payload.question)
    draft = draft_sql(payload.question)
    return AnalyzeResponse(
        question=payload.question,
        analysis_type=plan.analysis_type,
        steps=list(plan.steps),
        sql=draft.sql,
        route=draft.route.route,
        matched_views=list(draft.route.matched_views),
        chart_type=choose_chart(draft.sql),
        recommendations=build_recommendations(plan.analysis_type),
    )


@app.websocket("/ws/analyze")
async def analyze_ws(websocket: WebSocket) -> None:
    """Stream coarse agent milestones for the future LangGraph integration."""
    await websocket.accept()
    question = await websocket.receive_text()
    plan = build_plan(question)
    await websocket.send_json({"event": "plan", "analysis_type": plan.analysis_type, "steps": list(plan.steps)})
    draft = draft_sql(question)
    await websocket.send_json({"event": "sql", "sql": draft.sql, "route": draft.route.route})
    await websocket.send_json({"event": "chart", "chart_type": choose_chart(draft.sql)})
    await websocket.send_json({"event": "done", "recommendations": build_recommendations(plan.analysis_type)})
    await websocket.close()
