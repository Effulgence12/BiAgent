"""Central data dictionary for Olist base tables and pre-aggregated views."""

from config.views_desc import MATERIALIZED_VIEWS

BASE_TABLES = {
    "orders": [
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "order_items": [
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "shipping_limit_date",
        "price",
        "freight_value",
    ],
    "customers": ["customer_id", "customer_unique_id", "customer_city", "customer_state"],
    "products": [
        "product_id",
        "product_category_name",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ],
    "sellers": ["seller_id", "seller_city", "seller_state"],
    "order_payments": ["order_id", "payment_type", "payment_installments", "payment_value"],
    "order_reviews": ["review_id", "order_id", "review_score", "review_comment_message"],
}


def render_schema_context() -> str:
    """Return a compact schema description suitable for prompt injection."""
    base = [f"- {table}: {', '.join(columns)}" for table, columns in BASE_TABLES.items()]
    views = [
        f"- {name} ({meta['grain']}): {', '.join(meta['columns'])}; {meta['purpose']}"
        for name, meta in MATERIALIZED_VIEWS.items()
    ]
    return "Base tables:\n" + "\n".join(base) + "\n\nPre-aggregated views:\n" + "\n".join(views)
