from pathlib import Path

from agents.data_analyst import analyze_question, draft_sql
from agents.orchestrator import build_plan, classify_question, run_workflow
from agents.visualizer import choose_chart, render_chart_html
from models.forecast import linear_forecast, naive_forecast
from utils.data_bootstrap import generate_demo_csvs, has_required_csvs
from utils.local_store import bootstrap_local_store, table_counts
from utils.query_router import decide_query_route, referenced_relations


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


def test_data_analyst_payment_question_hits_payment_view():
    draft = draft_sql("支付方式和分期数分布如何？")
    assert "mv_payment_dist" in draft.sql
    assert draft.route.route == "materialized_view"
    assert choose_chart(draft.sql) == "heatmap_or_donut"


def test_plan_and_forecast_placeholders():
    plan = build_plan("预测未来6周GMV")
    assert plan.analysis_type == "predictive"
    assert naive_forecast([1, 2, 3], periods=3) == [3.0, 3.0, 3.0]
    forecast = linear_forecast([{"total_gmv": 100}, {"total_gmv": 120}], periods=2)
    assert forecast[0]["yhat"] > 120


def test_demo_dataset_and_local_store(tmp_path: Path):
    data_dir = tmp_path / "raw"
    db_path = tmp_path / "agentic_bi.sqlite"
    generate_demo_csvs(data_dir, orders_count=80)
    assert has_required_csvs(data_dir)
    source = bootstrap_local_store(force=True, data_dir=data_dir, db_path=db_path)
    assert source == "existing_csv"
    assert db_path.exists()


def test_workflow_returns_chart_and_recommendations():
    workflow = run_workflow("哪些州配送延迟严重？")
    assert workflow.plan.analysis_type == "diagnostic"
    assert workflow.data_analysis.result.rows
    assert "<" in workflow.chart_html
    assert workflow.recommendations


def test_render_chart_html_table_fallback():
    html = render_chart_html("table", [{"a": 1, "b": "x"}])
    assert "data-table" in html
    assert "x" in html
