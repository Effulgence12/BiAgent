"""Pre-aggregated view descriptions injected into DataAnalyst prompts."""

MATERIALIZED_VIEWS = {
    "mv_monthly_sales": {
        "grain": "year_month",
        "purpose": "GMV trend, order volume, average price, and freight trend analysis.",
        "columns": ["year_month", "total_orders", "total_gmv", "avg_price", "total_freight"],
    },
    "mv_state_sales": {
        "grain": "year_month + customer_state",
        "purpose": "Regional sales ranking and state-level AOV comparison.",
        "columns": ["year_month", "customer_state", "total_orders", "total_gmv", "avg_order_value"],
    },
    "mv_category_sales": {
        "grain": "year_month + product_category_name",
        "purpose": "Product category contribution and category Top-N analysis.",
        "columns": ["year_month", "product_category_name", "total_orders", "total_items", "total_gmv"],
    },
    "mv_delivery_perf": {
        "grain": "year_month + customer_state",
        "purpose": "Delivery timeliness, late-order diagnosis, and logistics bottlenecks.",
        "columns": ["year_month", "customer_state", "total_orders", "avg_delivery_days", "late_orders", "late_rate"],
    },
    "mv_seller_perf": {
        "grain": "year_month + seller_id",
        "purpose": "Seller GMV, order count, average review score, and negative review diagnosis.",
        "columns": ["year_month", "seller_id", "seller_state", "total_orders", "total_gmv", "avg_review_score"],
    },
    "mv_payment_dist": {
        "grain": "year_month + payment_type + payment_installments",
        "purpose": "Payment preference, installment mix, and payment heatmap analysis.",
        "columns": ["year_month", "payment_type", "payment_installments", "payment_count", "payment_value"],
    },
}

VIEW_NAMES = tuple(MATERIALIZED_VIEWS.keys())
