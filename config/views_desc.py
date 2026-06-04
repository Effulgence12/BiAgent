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
    "mv_weekly_sales": {
        "grain": "week_start",
        "purpose": "Weekly GMV series used for the required six-week sales forecast.",
        "columns": ["week_start", "total_orders", "total_gmv", "avg_order_value"],
    },
    "mv_state_geo": {
        "grain": "customer_state",
        "purpose": "State-level sales joined with geolocation centroids for maps.",
        "columns": ["customer_state", "lat", "lng", "total_orders", "total_gmv", "avg_order_value"],
    },
    "mv_review_category_perf": {
        "grain": "product_category_name",
        "purpose": "Category review score, negative review rate, and bad-review reason signals.",
        "columns": [
            "product_category_name",
            "total_reviews",
            "avg_review_score",
            "negative_reviews",
            "negative_rate",
            "delay_complaints",
            "quality_complaints",
            "wrong_item_complaints",
            "service_complaints",
            "other_complaints",
        ],
    },
    "mv_review_topics": {
        "grain": "product_category_name + topic_id ('ALL' 行为平台级)",
        "purpose": "负面评论 TF-IDF+NMF 主题建模结果：每个品类的差评集中在哪些数据驱动主题（topic_label/topic_keywords 为葡语关键词），用于回答差评原因并支撑改进建议；优于关键词分类。",
        "columns": [
            "product_category_name",
            "topic_id",
            "topic_label",
            "topic_keywords",
            "complaint_count",
            "topic_share",
        ],
    },
    "mv_weight_freight": {
        "grain": "weight_bucket + delivery_status",
        "purpose": "Product weight/volume versus freight relationship for bubble scatter charts.",
        "columns": [
            "weight_bucket",
            "delivery_status",
            "order_count",
            "avg_weight_g",
            "avg_volume_cm3",
            "avg_freight",
            "avg_price",
        ],
    },
}

VIEW_NAMES = tuple(MATERIALIZED_VIEWS.keys())
