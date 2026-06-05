"""Pre-aggregated view descriptions injected into DataAnalyst prompts."""

MATERIALIZED_VIEWS = {
    "mv_monthly_sales": {
        "grain": "year_month",
        "purpose": "GMV trend, order volume, average price, and freight trend analysis.",
        "columns": ["year_month", "total_orders", "unique_customers", "total_gmv", "avg_basket", "avg_price", "total_freight"],
    },
    "mv_state_sales": {
        "grain": "year_month + customer_state",
        "purpose": "Regional sales ranking and state-level AOV comparison.",
        "columns": ["year_month", "customer_state", "total_orders", "unique_customers", "total_gmv", "avg_order_value"],
    },
    "mv_category_sales": {
        "grain": "year_month + product_category_name",
        "purpose": "Product category contribution and category Top-N analysis.",
        "columns": ["year_month", "product_category_name", "product_category_english", "total_orders", "total_items", "avg_price", "total_gmv"],
    },
    "mv_delivery_perf": {
        "grain": "year_month + customer_state",
        "purpose": "Delivery timeliness, late-order diagnosis, and logistics bottlenecks.",
        "columns": [
            "year_month",
            "customer_state",
            "total_orders",
            "avg_delivery_days",
            "late_orders",
            "delayed_orders",
            "on_time_orders",
            "late_rate",
            "on_time_rate",
        ],
    },
    "mv_seller_perf": {
        "grain": "year_month + seller_id",
        "purpose": "Seller GMV, order count, negative review rate, average review score, and seller risk diagnosis.",
        "columns": [
            "year_month",
            "seller_id",
            "seller_state",
            "total_orders",
            "total_gmv",
            "total_reviews",
            "negative_reviews",
            "negative_rate",
            "avg_review_score",
        ],
    },
    "mv_payment_dist": {
        "grain": "year_month + payment_type + payment_installments",
        "purpose": "Payment preference, installment mix, and payment heatmap analysis.",
        "columns": [
            "year_month",
            "payment_type",
            "payment_installments",
            "payment_count",
            "total_transactions",
            "avg_installments",
            "payment_value",
        ],
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
        "purpose": "品类评分、差评率与差评数量的快速汇总，以及物流/质量/错发/客服四类**可明确识别**的差评计数。注意：这四类关键词分类只能覆盖少数措辞明确的差评，**不可据此推断'主要差评原因'**——回答'差评原因/主要差评原因/为什么差评'必须使用 mv_review_topics（NMF 主题）。本视图仅用于差评量、差评率，以及对已识别的物流/质量/错发/客服做补充佐证。",
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
        ],
    },
    "mv_review_topics": {
        "grain": "product_category_name + topic_id ('ALL' 行为平台级)",
        "purpose": "负面评论 TF-IDF+NMF 主题建模结果：每个品类的差评集中在哪些数据驱动主题（topic_label/topic_keywords 为葡语关键词，topic_id='ALL' 为平台级）。**回答'差评原因/主要差评原因/为什么差评'时必须优先使用本视图，按 complaint_count 取该品类 Top 主题**，并把葡语 topic_label/keywords 翻译为中文业务原因（如 `comprei dois·recebi apenas`=漏发缺件、`entrega·prazo`=配送超期、`produto·qualidade`=质量差）；这是对 mv_review_category_perf 关键词分类的升级替代，结论更可信。",
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
