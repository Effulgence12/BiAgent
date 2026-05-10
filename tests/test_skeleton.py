from agents.data_analyst import draft_sql
from agents.orchestrator import build_plan, classify_question
from agents.visualizer import choose_chart
from models.forecast import naive_forecast
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
