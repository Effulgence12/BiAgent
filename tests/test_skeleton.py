import csv
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import agents.data_analyst as data_analyst
import agents.orchestrator as orchestrator
from agents.data_analyst import DataAnalysis, QueryTask, draft_sql
from agents.orchestrator import build_plan, classify_question, run_workflow
from agents.visualizer import choose_chart, render_chart_html, render_charts
from models.forecast import linear_forecast, naive_forecast
import utils.data_bootstrap as data_bootstrap
from utils.data_bootstrap import DatasetValidationError, ensure_dataset, has_required_csvs
from utils.local_store import QueryResult, bootstrap_local_store
from utils.query_router import decide_query_route, referenced_relations
from utils.query_router import QueryRoute


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_minimal_real_csv_set(data_dir: Path) -> None:
    _write_csv(data_dir / "olist_customers_dataset.csv", [{"customer_id": "c1", "customer_unique_id": "u1", "customer_zip_code_prefix": 1000, "customer_city": "sao paulo", "customer_state": "SP"}])
    _write_csv(data_dir / "olist_geolocation_dataset.csv", [{"geolocation_zip_code_prefix": 1000, "geolocation_lat": -23.5, "geolocation_lng": -46.6, "geolocation_city": "sao paulo", "geolocation_state": "SP"}])
    _write_csv(data_dir / "olist_orders_dataset.csv", [{"order_id": "o1", "customer_id": "c1", "order_status": "delivered", "order_purchase_timestamp": "2017-01-10 10:00:00", "order_approved_at": "2017-01-10 11:00:00", "order_delivered_carrier_date": "2017-01-11 10:00:00", "order_delivered_customer_date": "2017-01-15 10:00:00", "order_estimated_delivery_date": "2017-01-20 10:00:00"}])
    _write_csv(data_dir / "olist_order_items_dataset.csv", [{"order_id": "o1", "order_item_id": 1, "product_id": "p1", "seller_id": "s1", "shipping_limit_date": "2017-01-12 10:00:00", "price": 100, "freight_value": 10}])
    _write_csv(data_dir / "olist_products_dataset.csv", [{"product_id": "p1", "product_category_name": "beleza_saude", "product_name_length": 10, "product_description_length": 20, "product_photos_qty": 1, "product_weight_g": 300, "product_length_cm": 10, "product_height_cm": 5, "product_width_cm": 8}])
    _write_csv(data_dir / "olist_sellers_dataset.csv", [{"seller_id": "s1", "seller_zip_code_prefix": 2000, "seller_city": "campinas", "seller_state": "SP"}])
    _write_csv(data_dir / "olist_order_payments_dataset.csv", [{"order_id": "o1", "payment_sequential": 1, "payment_type": "credit_card", "payment_installments": 1, "payment_value": 110}])
    _write_csv(data_dir / "olist_order_reviews_dataset.csv", [{"review_id": "r1", "order_id": "o1", "review_score": 5, "review_comment_message": "bom"}])
    _write_csv(data_dir / "product_category_name_translation.csv", [{"product_category_name": "beleza_saude", "product_category_name_english": "health_beauty"}])


def _local_test_dir(name: str) -> Path:
    """Use project-local temp dirs because the Windows pytest temp root is locked."""
    path = Path("data") / "local" / "test_runs" / f"{name}_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_question_classification():
    assert classify_question("预测未来6周销售额") == "predictive"
    assert classify_question("哪些州配送延迟严重，为什么？") == "diagnostic"
    assert classify_question("给出优化策略建议") == "prescriptive"
    assert classify_question("2017年各月GMV趋势") == "descriptive"


def test_query_router_detects_materialized_view():
    sql = "SELECT * FROM mv_monthly_sales ORDER BY year_month DESC LIMIT 20;"
    route = decide_query_route(sql)
    assert route.route == "materialized_view"
    assert route.matched_views == ("mv_monthly_sales",)
    assert referenced_relations(sql) == ("mv_monthly_sales",)


def test_sql_normalizer_wraps_ordered_union_all():
    sql = (
        "SELECT customer_state, total_orders FROM mv_state_geo ORDER BY total_orders DESC LIMIT 1 "
        "UNION ALL SELECT customer_state, total_orders FROM mv_state_geo ORDER BY total_orders ASC LIMIT 1"
    )
    normalized = data_analyst._validate_sql(sql)
    assert "FROM (SELECT customer_state" in normalized
    assert "UNION ALL SELECT * FROM" in normalized


def test_sql_normalizer_wraps_ordered_union_all_inside_cte():
    sql = (
        "WITH extreme_states AS (SELECT customer_state FROM mv_state_geo ORDER BY total_orders DESC LIMIT 1 "
        "UNION ALL SELECT customer_state FROM mv_state_geo ORDER BY total_orders ASC LIMIT 1) "
        "SELECT customer_state FROM extreme_states"
    )
    normalized = data_analyst._validate_sql(sql)
    assert normalized.startswith("WITH extreme_states AS (SELECT * FROM")
    assert "UNION ALL SELECT * FROM" in normalized


def test_data_analyst_payment_question_hits_payment_view(monkeypatch):
    payload = {
        "tasks": [
            {
                "name": "payment_distribution",
                "purpose": "支付方式偏好",
                "sql": "SELECT payment_type, SUM(payment_count) AS payment_count FROM mv_payment_dist GROUP BY payment_type ORDER BY payment_count DESC",
            }
        ]
    }
    monkeypatch.setattr(data_analyst, "chat_completion", lambda *args, **kwargs: LLMResponse(content=json.dumps(payload), used_api=True, model="test"))
    draft = draft_sql("支付方式和分期数分布如何？")
    assert "mv_payment_dist" in draft.sql
    assert draft.route.route == "materialized_view"
    assert choose_chart(draft.sql) == "heatmap_or_donut"


def test_direct_answer_sorts_state_rows_by_metric():
    result = QueryResult(
        columns=["customer_state", "total_orders", "avg_order_value"],
        rows=[
            {"customer_state": "MG", "total_orders": 11354, "avg_order_value": 158.38},
            {"customer_state": "RJ", "total_orders": 12350, "avg_order_value": 169.01},
            {"customer_state": "SP", "total_orders": 40501, "avg_order_value": 143.84},
        ],
        elapsed_ms=1.0,
        row_count=3,
        source="test",
    )
    answer = data_analyst.build_direct_answer_from_results("SP、RJ、MG三个州对比", {"state_compare": result})
    assert "订单量最高的州是 SP" in answer
    assert "最低的是 MG" in answer


def test_plan_and_forecast_placeholders():
    plan = build_plan("预测未来6周GMV")
    assert plan.analysis_type == "predictive"
    assert naive_forecast([1, 2, 3], periods=3) == [3.0, 3.0, 3.0]
    forecast = linear_forecast([{"total_gmv": 100}, {"total_gmv": 120}], periods=2)
    assert forecast[0]["yhat"] > 120


def test_missing_real_csvs_fail_loudly(monkeypatch):
    monkeypatch.setattr(data_bootstrap, "download_olist_csvs", lambda data_dir: False)
    try:
        ensure_dataset(_local_test_dir("missing") / "raw")
    except DatasetValidationError as exc:
        assert "真实 Olist CSV" in str(exc)
        assert "olist_geolocation_dataset.csv" in str(exc)
    else:
        raise AssertionError("missing real CSVs must fail loudly")


def test_real_csv_set_and_local_store():
    root = _local_test_dir("store")
    data_dir = root / "raw"
    db_path = root / "agentic_bi.sqlite"
    _write_minimal_real_csv_set(data_dir)
    assert has_required_csvs(data_dir)
    source = bootstrap_local_store(force=True, data_dir=data_dir, db_path=db_path)
    assert source == "existing_real_olist_csv"
    assert db_path.exists()


def test_workflow_returns_chart_and_recommendations(monkeypatch):
    query_result = QueryResult(
        columns=["year_month", "total_gmv"],
        rows=[{"year_month": "2017-01", "total_gmv": 110.0}],
        elapsed_ms=1.2,
        row_count=1,
        source="test",
    )
    data_analysis = DataAnalysis(
        question="哪些州配送延迟严重？",
        sql="SELECT * FROM mv_delivery_perf LIMIT 1;",
        tasks=(QueryTask("delivery_performance", "SELECT * FROM mv_delivery_perf LIMIT 1;", "配送测试"),),
        route=QueryRoute("materialized_view", ("mv_delivery_perf",), "test"),
        routes={"delivery_performance": QueryRoute("materialized_view", ("mv_delivery_perf",), "test")},
        result=query_result,
        results={"delivery_performance": query_result},
        summary="测试摘要",
        direct_answer="测试直接回答",
    )
    monkeypatch.setattr(orchestrator, "analyze_question", lambda question: data_analysis)
    monkeypatch.setattr(orchestrator, "build_recommendations", lambda *args, **kwargs: ["真实 LLM 建议占位"])
    workflow = run_workflow("哪些州配送延迟严重？")
    assert workflow.plan.analysis_type == "diagnostic"
    assert workflow.data_analysis.result.rows
    assert "<" in workflow.chart_html
    assert workflow.recommendations


def test_render_chart_html_table_fallback():
    html = render_chart_html("table", [{"a": 1, "b": "x"}])
    assert "data-table" in html
    assert "x" in html


def test_render_charts_returns_structured_plotly_specs():
    result = QueryResult(
        columns=["year_month", "total_gmv"],
        rows=[{"year_month": "2017-01", "total_gmv": 100.0}, {"year_month": "2017-02", "total_gmv": 130.0}],
        elapsed_ms=1.0,
        row_count=2,
        source="mv_monthly_sales",
    )
    charts = render_charts({"monthly_sales": result}, [{"week_start": "2017-03-01", "yhat": 140.0, "yhat_lower": 120.0, "yhat_upper": 160.0}])
    assert charts
    assert {"id", "title", "type", "source_view", "html", "summary"}.issubset(charts[0])
    assert "plotly" in charts[0]["html"].lower()
    assert "data-table" in charts[0]["html"]


def test_map_question_adds_geo_supplement(monkeypatch):
    state_result = QueryResult(
        columns=["customer_state", "total_gmv"],
        rows=[{"customer_state": "SP", "total_gmv": 100.0}],
        elapsed_ms=1.0,
        row_count=1,
        source="test",
    )
    geo_result = QueryResult(
        columns=["customer_state", "lat", "lng", "total_orders", "total_gmv", "avg_order_value"],
        rows=[{"customer_state": "SP", "lat": -23.5, "lng": -46.6, "total_orders": 10, "total_gmv": 100.0, "avg_order_value": 10.0}],
        elapsed_ms=1.0,
        row_count=1,
        source="test",
    )
    monkeypatch.setattr(
        data_analyst,
        "draft_tasks",
        lambda question: (QueryTask("state_sales", "SELECT customer_state,total_gmv FROM mv_state_sales LIMIT 10", "州销售"),),
    )
    monkeypatch.setattr(data_analyst, "run_query", lambda sql: geo_result if "mv_state_geo" in sql else state_result)
    monkeypatch.setattr(data_analyst, "decide_query_route", lambda sql: QueryRoute("materialized_view", ("mv_state_geo" if "mv_state_geo" in sql else "mv_state_sales",), "test"))
    analysis = data_analyst.analyze_question("用巴西地图展示各州销售分布")
    assert "state_geo_map" in analysis.results
    assert {"customer_state", "lat", "lng"}.issubset(analysis.results["state_geo_map"].columns)


def test_prediction_question_adds_monthly_and_weekly_evidence(monkeypatch):
    monthly_result = QueryResult(
        columns=["year_month", "total_orders", "total_gmv", "avg_price", "total_freight"],
        rows=[{"year_month": "2017-01", "total_orders": 10, "total_gmv": 100.0, "avg_price": 8.0, "total_freight": 20.0}],
        elapsed_ms=1.0,
        row_count=1,
        source="test",
    )
    weekly_result = QueryResult(
        columns=["week_start", "total_orders", "total_gmv", "avg_order_value"],
        rows=[{"week_start": f"2017-01-{day:02d}", "total_orders": 10, "total_gmv": 100.0 + day, "avg_order_value": 10.0} for day in range(1, 10)],
        elapsed_ms=1.0,
        row_count=9,
        source="test",
    )
    monkeypatch.setattr(
        data_analyst,
        "draft_tasks",
        lambda question: (QueryTask("llm_weekly", "SELECT week_start,total_gmv FROM mv_weekly_sales LIMIT 20", "周GMV"),),
    )
    monkeypatch.setattr(data_analyst, "run_query", lambda sql: monthly_result if "mv_monthly_sales" in sql else weekly_result)
    monkeypatch.setattr(data_analyst, "decide_query_route", lambda sql: QueryRoute("materialized_view", ("mv_monthly_sales" if "mv_monthly_sales" in sql else "mv_weekly_sales",), "test"))
    analysis = data_analyst.analyze_question("预测未来6周销售额")
    assert "monthly_sales" in analysis.results
    assert any({"week_start", "total_gmv"}.issubset(result.columns) for result in analysis.results.values())

import utils.llm_client as llm_client
import app as app_module
import cli as cli_module
from fastapi.testclient import TestClient
from agents.orchestrator import AnalysisPlan, WorkflowResult
from utils.llm_client import LLMStreamEvent
from utils.llm_client import LLMResponse, _iter_sse_lines, stream_chat_completion


def test_sse_parser_handles_qwen_chunks():
    lines = [
        b'data: {"choices":[{"delta":{"content":"hello"}}]}\n',
        b'data: {"usage":{"total_tokens":7},"choices":[]}\n',
        b'data: [DONE]\n',
    ]
    chunks = list(_iter_sse_lines(lines))
    assert chunks[0]["choices"][0]["delta"]["content"] == "hello"
    assert chunks[1]["usage"]["total_tokens"] == 7
    assert chunks[2] == "[DONE]"


def test_stream_chat_completion_disabled_reports_error(monkeypatch):
    monkeypatch.setattr(
        llm_client,
        "settings",
        SimpleNamespace(enable_llm=False, qwen_api_key="", deepseek_api_key="", qwen_model="test", qwen_base_url="https://example.com", llm_temperature=0.2, llm_max_tokens=64),
    )
    events = list(stream_chat_completion("system", "user"))
    assert events[0].event == "error"
    assert "disabled" in events[0].error


def test_websocket_emits_structured_agent_events(monkeypatch):
    query_result = QueryResult(
        columns=["year_month", "total_gmv"],
        rows=[{"year_month": "2017-01", "total_gmv": 100.0}],
        elapsed_ms=2.0,
        row_count=1,
        source="test",
    )
    data_analysis = DataAnalysis(
        question="2017年GMV趋势",
        sql="SELECT year_month,total_gmv FROM mv_monthly_sales LIMIT 1",
        tasks=(QueryTask("monthly_sales", "SELECT year_month,total_gmv FROM mv_monthly_sales LIMIT 1", "月度GMV"),),
        route=QueryRoute("materialized_view", ("mv_monthly_sales",), "test"),
        routes={"monthly_sales": QueryRoute("materialized_view", ("mv_monthly_sales",), "test")},
        result=query_result,
        results={"monthly_sales": query_result},
        summary="测试摘要",
        direct_answer="测试直答",
    )
    workflow = WorkflowResult(
        plan=AnalysisPlan("descriptive", ("Orchestrator", "DataAnalyst", "Visualizer", "DecisionMaker")),
        data_analysis=data_analysis,
        chart_type="line",
        chart_html="<div>chart</div>",
        charts=[{"id": "c1", "title": "GMV", "type": "plotly_line", "source_view": "mv_monthly_sales", "html": "<div>chart</div>", "summary": "summary"}],
        recommendations=[],
        forecast=[],
        forecast_diagnostics={},
    )
    monkeypatch.setattr(app_module, "build_plan", lambda question: workflow.plan)
    monkeypatch.setattr(app_module, "run_workflow", lambda question, generate_recommendations=False: workflow)
    monkeypatch.setattr(
        app_module,
        "stream_chat_completion",
        lambda *args, **kwargs: iter([LLMStreamEvent("delta", content="建议正文"), LLMStreamEvent("usage", total_tokens=8), LLMStreamEvent("done")]),
    )
    with TestClient(app_module.app).websocket_connect("/ws/analyze") as websocket:
        websocket.send_json({"session_id": "test_session", "question": "2017年GMV趋势"})
        events = []
        while True:
            try:
                event = websocket.receive_json()
            except Exception:
                break
            events.append(event)
            if event.get("event") == "final":
                break
    names = [event["event"] for event in events]
    assert "memory" in names
    assert "memory_updated" in names
    assert "sql_planned" in names
    assert "chart_done" in names
    assert any(event.get("event") == "llm_delta" and event.get("content") == "建议正文" for event in events)
    assert events[-1]["event"] == "final"


def test_general_validation_contract_uses_workflow_outputs(monkeypatch):
    query_result = QueryResult(
        columns=["customer_state", "total_gmv"],
        rows=[{"customer_state": "SP", "total_gmv": 100.0}],
        elapsed_ms=1.0,
        row_count=1,
        source="test",
    )
    all_views = (
        "mv_monthly_sales",
        "mv_state_sales",
        "mv_state_geo",
        "mv_delivery_perf",
        "mv_payment_dist",
        "mv_category_sales",
        "mv_review_category_perf",
        "mv_seller_perf",
        "mv_weight_freight",
        "mv_weekly_sales",
    )
    data_analysis = DataAnalysis(
        question="general",
        sql="SELECT * FROM mv_state_sales LIMIT 1",
        tasks=(QueryTask("general_task", "SELECT * FROM mv_state_sales LIMIT 1", "泛化验证"),),
        route=QueryRoute("materialized_view", all_views, "test"),
        routes={"general_task": QueryRoute("materialized_view", all_views, "test")},
        result=query_result,
        results={"general_task": query_result},
        summary="测试摘要",
        direct_answer="测试直答",
    )
    workflow = WorkflowResult(
        plan=AnalysisPlan("descriptive", ("DataAnalyst",), intent="general", required_agents=("data_analyst",), required_views=all_views),
        data_analysis=data_analysis,
        chart_type="bar",
        chart_html="<div>chart</div>",
        charts=[{"id": "c1", "title": "chart", "type": "plotly_bar", "source_view": "mv_state_sales", "html": "<div>chart</div>", "summary": "summary"}],
        recommendations=[],
        forecast=[{"week_start": "2018-09-01", "yhat": 1.0, "yhat_lower": 0.8, "yhat_upper": 1.2}],
        forecast_diagnostics={"model": "ETS"},
    )
    monkeypatch.setattr(cli_module, "run_workflow", lambda question, generate_recommendations=False: workflow)
    report = cli_module.run_general_validation()
    assert report["total"] >= 25
    assert report["passed"] is True
    assert report["pass_rate"] == 1.0


def test_websocket_failed_turn_records_original_question(monkeypatch):
    session_id = f"retry_session_{uuid.uuid4().hex}"
    app_module.SESSIONS.pop(session_id, None)
    plan = AnalysisPlan("descriptive", ("DataAnalyst",), intent="compare states", required_agents=("data_analyst",), required_views=("mv_state_geo",))

    monkeypatch.setattr(app_module, "build_plan", lambda question: plan)

    def fail_workflow(question, generate_recommendations=False):
        raise ValueError("SQL任务 best_worst_states 执行失败：ORDER BY clause should come after UNION ALL")

    monkeypatch.setattr(app_module, "run_workflow", fail_workflow)
    with TestClient(app_module.app).websocket_connect("/ws/analyze") as websocket:
        websocket.send_json({"session_id": session_id, "question": "对其中情况最好和最差的州分析情况并提出建议"})
        events = []
        while True:
            event = websocket.receive_json()
            events.append(event)
            if event.get("event") == "sql_error":
                break

    error_event = events[-1]
    assert error_event["question"] == "对其中情况最好和最差的州分析情况并提出建议"
    assert error_event["request_id"]
    assert app_module.SESSIONS[session_id][-1]["failed_turn"] is True
    assert "ORDER BY" in app_module.SESSIONS[session_id][-1]["error"]
