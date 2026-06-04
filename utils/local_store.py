"""Local SQLite analytics store used before the MySQL server is ready.

SQLite is only a temporary query engine. It must be rebuilt from the real Olist CSV
files and keep the same base-table / mv_* boundary as the MySQL scripts, so the
later migration can swap the connection layer without changing Agent behavior.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from config.settings import settings
from utils.data_bootstrap import ensure_dataset
from utils.review_topics import build_review_topic_table

CSV_TABLES = {
    "olist_customers_dataset.csv": "customers",
    "olist_geolocation_dataset.csv": "geolocation",
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_products_dataset.csv": "products",
    "olist_sellers_dataset.csv": "sellers",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "product_category_name_translation.csv": "product_category_name_translation",
}

MATERIALIZED_VIEW_NAMES = (
    "mv_monthly_sales",
    "mv_state_sales",
    "mv_category_sales",
    "mv_delivery_perf",
    "mv_seller_perf",
    "mv_payment_dist",
    "mv_weekly_sales",
    "mv_state_geo",
    "mv_review_category_perf",
    "mv_review_topics",
    "mv_weight_freight",
)


@dataclass(frozen=True)
class QueryResult:
    """Query rows with execution metadata."""

    columns: list[str]
    rows: list[dict[str, object]]
    elapsed_ms: float
    row_count: int
    source: str


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or settings.local_db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    # 当前项目放在 E 盘，部分 Windows 环境对 SQLite 默认 rollback journal
    # 文件锁支持不稳定；使用内存 journal 避免误报 disk I/O error。
    conn.execute("PRAGMA journal_mode=MEMORY")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def _import_csv(conn: sqlite3.Connection, csv_path: Path, table: str) -> None:
    """Import one real CSV as TEXT columns to avoid lossy type conversion."""
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        quoted_columns = ", ".join(f'"{column}" TEXT' for column in columns)
        conn.execute(f'DROP TABLE IF EXISTS "{table}"')
        conn.execute(f'CREATE TABLE "{table}" ({quoted_columns})')
        placeholders = ", ".join("?" for _ in columns)
        quoted_names = ", ".join(f'"{column}"' for column in columns)
        insert_sql = f'INSERT INTO "{table}" ({quoted_names}) VALUES ({placeholders})'
        batch = []
        for row in reader:
            batch.append([row.get(column, "") for column in columns])
            if len(batch) >= 5000:
                conn.executemany(insert_sql, batch)
                batch.clear()
        if batch:
            conn.executemany(insert_sql, batch)


def _create_indexes(conn: sqlite3.Connection) -> None:
    """Create indexes matching the high-frequency JOIN and mv_* refresh paths."""
    statements = [
        "CREATE INDEX IF NOT EXISTS idx_orders_id ON orders(order_id)",
        "CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_orders_purchase_status ON orders(order_purchase_timestamp, order_status)",
        "CREATE INDEX IF NOT EXISTS idx_customers_id ON customers(customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_customers_state ON customers(customer_state)",
        "CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id)",
        "CREATE INDEX IF NOT EXISTS idx_items_product ON order_items(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_items_seller ON order_items(seller_id)",
        "CREATE INDEX IF NOT EXISTS idx_products_id ON products(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_sellers_id ON sellers(seller_id)",
        "CREATE INDEX IF NOT EXISTS idx_payments_order ON order_payments(order_id)",
        "CREATE INDEX IF NOT EXISTS idx_reviews_order ON order_reviews(order_id)",
        "CREATE INDEX IF NOT EXISTS idx_geolocation_zip ON geolocation(geolocation_zip_code_prefix)",
        "CREATE INDEX IF NOT EXISTS idx_geolocation_state ON geolocation(geolocation_state)",
    ]
    for statement in statements:
        conn.execute(statement)


def refresh_materialized_views(conn: sqlite3.Connection) -> None:
    """Rebuild SQLite materialized aggregate tables mirroring the MySQL design.

    这些 mv_* 表是作业要求的预聚合层：Agent 命中常见问题时先查它们，
    不命中时才回退到基础表 JOIN。
    """
    for name in MATERIALIZED_VIEW_NAMES:
        conn.execute(f"DROP TABLE IF EXISTS {name}")

    conn.executescript(
        """
        CREATE TABLE mv_monthly_sales AS
        SELECT
          substr(o.order_purchase_timestamp, 1, 7) AS year_month,
          COUNT(DISTINCT o.order_id) AS total_orders,
          ROUND(SUM(CAST(oi.price AS REAL) + CAST(oi.freight_value AS REAL)), 2) AS total_gmv,
          ROUND(SUM(CAST(oi.price AS REAL) + CAST(oi.freight_value AS REAL)) / COUNT(DISTINCT o.order_id), 2) AS avg_basket,
          ROUND(AVG(CAST(oi.price AS REAL)), 2) AS avg_price,
          ROUND(SUM(CAST(oi.freight_value AS REAL)), 2) AS total_freight
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.order_status = 'delivered'
        GROUP BY year_month;
        CREATE INDEX idx_mv_monthly_sales_year_month ON mv_monthly_sales(year_month);

        CREATE TABLE mv_state_sales AS
        SELECT
          substr(o.order_purchase_timestamp, 1, 7) AS year_month,
          c.customer_state,
          COUNT(DISTINCT o.order_id) AS total_orders,
          ROUND(SUM(CAST(oi.price AS REAL) + CAST(oi.freight_value AS REAL)), 2) AS total_gmv,
          ROUND(SUM(CAST(oi.price AS REAL) + CAST(oi.freight_value AS REAL)) / COUNT(DISTINCT o.order_id), 2) AS avg_order_value
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.order_status = 'delivered'
        GROUP BY year_month, c.customer_state;
        CREATE INDEX idx_mv_state_sales_month_state ON mv_state_sales(year_month, customer_state);

        CREATE TABLE mv_category_sales AS
        SELECT
          substr(o.order_purchase_timestamp, 1, 7) AS year_month,
          COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS product_category_name,
          COUNT(DISTINCT o.order_id) AS total_orders,
          COUNT(*) AS total_items,
          ROUND(SUM(CAST(oi.price AS REAL) + CAST(oi.freight_value AS REAL)), 2) AS total_gmv
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        LEFT JOIN products p ON oi.product_id = p.product_id
        LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
        WHERE o.order_status = 'delivered'
        GROUP BY year_month, COALESCE(t.product_category_name_english, p.product_category_name, 'unknown');
        CREATE INDEX idx_mv_category_sales_month_category ON mv_category_sales(year_month, product_category_name);

        CREATE TABLE mv_delivery_perf AS
        SELECT
          substr(o.order_purchase_timestamp, 1, 7) AS year_month,
          c.customer_state,
          COUNT(DISTINCT o.order_id) AS total_orders,
          ROUND(AVG(julianday(o.order_delivered_customer_date) - julianday(o.order_purchase_timestamp)), 2) AS avg_delivery_days,
          SUM(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 ELSE 0 END) AS late_orders,
          ROUND(1.0 * SUM(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 ELSE 0 END) / COUNT(DISTINCT o.order_id), 4) AS late_rate
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date <> ''
        GROUP BY year_month, c.customer_state;
        CREATE INDEX idx_mv_delivery_perf_month_state ON mv_delivery_perf(year_month, customer_state);

        CREATE TABLE mv_seller_perf AS
        SELECT
          substr(o.order_purchase_timestamp, 1, 7) AS year_month,
          s.seller_id,
          s.seller_state,
          COUNT(DISTINCT o.order_id) AS total_orders,
          ROUND(SUM(CAST(oi.price AS REAL) + CAST(oi.freight_value AS REAL)), 2) AS total_gmv,
          ROUND(AVG(CAST(r.review_score AS REAL)), 2) AS avg_review_score
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN sellers s ON oi.seller_id = s.seller_id
        LEFT JOIN order_reviews r ON o.order_id = r.order_id
        WHERE o.order_status = 'delivered'
        GROUP BY year_month, s.seller_id, s.seller_state;
        CREATE INDEX idx_mv_seller_perf_month_seller ON mv_seller_perf(year_month, seller_id);

        CREATE TABLE mv_payment_dist AS
        SELECT
          substr(o.order_purchase_timestamp, 1, 7) AS year_month,
          op.payment_type,
          CAST(op.payment_installments AS INTEGER) AS payment_installments,
          COUNT(*) AS payment_count,
          ROUND(SUM(CAST(op.payment_value AS REAL)), 2) AS payment_value
        FROM orders o
        JOIN order_payments op ON o.order_id = op.order_id
        WHERE o.order_status = 'delivered'
        GROUP BY year_month, op.payment_type, CAST(op.payment_installments AS INTEGER);
        CREATE INDEX idx_mv_payment_dist_month_type ON mv_payment_dist(year_month, payment_type, payment_installments);

        CREATE TABLE mv_weekly_sales AS
        SELECT
          date(o.order_purchase_timestamp, '-' || strftime('%w', o.order_purchase_timestamp) || ' days') AS week_start,
          COUNT(DISTINCT o.order_id) AS total_orders,
          ROUND(SUM(CAST(oi.price AS REAL) + CAST(oi.freight_value AS REAL)), 2) AS total_gmv,
          ROUND(SUM(CAST(oi.price AS REAL) + CAST(oi.freight_value AS REAL)) / COUNT(DISTINCT o.order_id), 2) AS avg_order_value
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.order_status = 'delivered'
        GROUP BY week_start;
        CREATE INDEX idx_mv_weekly_sales_week ON mv_weekly_sales(week_start);

        CREATE TABLE mv_state_geo AS
        WITH state_sales AS (
          SELECT
            customer_state,
            SUM(total_orders) AS total_orders,
            ROUND(SUM(total_gmv), 2) AS total_gmv,
            ROUND(SUM(total_gmv) / NULLIF(SUM(total_orders), 0), 2) AS avg_order_value
          FROM mv_state_sales
          GROUP BY customer_state
        ),
        state_centroid AS (
          SELECT
            geolocation_state AS customer_state,
            ROUND(AVG(CAST(geolocation_lat AS REAL)), 6) AS lat,
            ROUND(AVG(CAST(geolocation_lng AS REAL)), 6) AS lng
          FROM geolocation
          WHERE geolocation_lat <> '' AND geolocation_lng <> ''
          GROUP BY geolocation_state
        )
        SELECT
          s.customer_state,
          g.lat,
          g.lng,
          s.total_orders,
          s.total_gmv,
          s.avg_order_value
        FROM state_sales s
        LEFT JOIN state_centroid g ON s.customer_state = g.customer_state;
        CREATE INDEX idx_mv_state_geo_state ON mv_state_geo(customer_state);

        CREATE TABLE mv_review_category_perf AS
        SELECT
          COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS product_category_name,
          COUNT(DISTINCT r.review_id) AS total_reviews,
          ROUND(AVG(CAST(r.review_score AS REAL)), 2) AS avg_review_score,
          SUM(CASE WHEN CAST(r.review_score AS INTEGER) <= 2 THEN 1 ELSE 0 END) AS negative_reviews,
          ROUND(1.0 * SUM(CASE WHEN CAST(r.review_score AS INTEGER) <= 2 THEN 1 ELSE 0 END) / NULLIF(COUNT(DISTINCT r.review_id), 0), 4) AS negative_rate,
          SUM(CASE WHEN CAST(r.review_score AS INTEGER) <= 2 AND lower(COALESCE(r.review_comment_message, '')) LIKE '%atras%' THEN 1 ELSE 0 END) AS delay_complaints,
          SUM(CASE WHEN CAST(r.review_score AS INTEGER) <= 2 AND (
            lower(COALESCE(r.review_comment_message, '')) LIKE '%defeit%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%quebr%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%qualidade%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%ruim%'
          ) THEN 1 ELSE 0 END) AS quality_complaints,
          SUM(CASE WHEN CAST(r.review_score AS INTEGER) <= 2 AND (
            lower(COALESCE(r.review_comment_message, '')) LIKE '%errad%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%diferente%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%troca%'
          ) THEN 1 ELSE 0 END) AS wrong_item_complaints,
          SUM(CASE WHEN CAST(r.review_score AS INTEGER) <= 2 AND (
            lower(COALESCE(r.review_comment_message, '')) LIKE '%atend%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%respost%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%contat%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%comunic%'
          ) THEN 1 ELSE 0 END) AS service_complaints,
          SUM(CASE WHEN CAST(r.review_score AS INTEGER) <= 2 AND NOT (
            lower(COALESCE(r.review_comment_message, '')) LIKE '%atras%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%defeit%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%quebr%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%qualidade%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%ruim%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%errad%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%diferente%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%troca%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%atend%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%respost%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%contat%' OR
            lower(COALESCE(r.review_comment_message, '')) LIKE '%comunic%'
          ) THEN 1 ELSE 0 END) AS other_complaints
        FROM order_reviews r
        JOIN orders o ON r.order_id = o.order_id
        JOIN order_items oi ON o.order_id = oi.order_id
        LEFT JOIN products p ON oi.product_id = p.product_id
        LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
        GROUP BY COALESCE(t.product_category_name_english, p.product_category_name, 'unknown');
        CREATE INDEX idx_mv_review_category_perf_rate ON mv_review_category_perf(negative_rate);

        CREATE TABLE mv_weight_freight AS
        SELECT
          CASE
            WHEN CAST(p.product_weight_g AS REAL) < 500 THEN '<0.5kg'
            WHEN CAST(p.product_weight_g AS REAL) < 2000 THEN '0.5-2kg'
            WHEN CAST(p.product_weight_g AS REAL) < 5000 THEN '2-5kg'
            WHEN CAST(p.product_weight_g AS REAL) < 10000 THEN '5-10kg'
            ELSE '10kg+'
          END AS weight_bucket,
          CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 'late' ELSE 'on_time' END AS delivery_status,
          COUNT(*) AS order_count,
          ROUND(AVG(CAST(p.product_weight_g AS REAL)), 2) AS avg_weight_g,
          ROUND(AVG(CAST(p.product_length_cm AS REAL) * CAST(p.product_height_cm AS REAL) * CAST(p.product_width_cm AS REAL)), 2) AS avg_volume_cm3,
          ROUND(AVG(CAST(oi.freight_value AS REAL)), 2) AS avg_freight,
          ROUND(AVG(CAST(oi.price AS REAL)), 2) AS avg_price
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN products p ON oi.product_id = p.product_id
        WHERE o.order_status = 'delivered'
          AND p.product_weight_g <> ''
          AND oi.freight_value <> ''
        GROUP BY weight_bucket, delivery_status;
        CREATE INDEX idx_mv_weight_freight_bucket_status ON mv_weight_freight(weight_bucket, delivery_status);
        """
    )

    # 负面评论主题建模（TF-IDF + NMF）：用 Python 在基础表上训练，产出 mv_review_topics。
    build_review_topic_table(conn)


def bootstrap_local_store(force: bool = False, data_dir: Path | None = None, db_path: Path | None = None) -> str:
    """Create a local SQLite store from real CSVs and refresh materialized tables."""
    source = ensure_dataset(data_dir or settings.data_dir)
    conn = _connect(db_path)
    try:
        if force or not all(_table_exists(conn, table) for table in CSV_TABLES.values()):
            for csv_name, table in CSV_TABLES.items():
                _import_csv(conn, (data_dir or settings.data_dir) / csv_name, table)
            _create_indexes(conn)
            refresh_materialized_views(conn)
            conn.commit()
        elif not all(_table_exists(conn, view) for view in MATERIALIZED_VIEW_NAMES):
            refresh_materialized_views(conn)
            conn.commit()
    finally:
        conn.close()
    return source


def ensure_local_store() -> str:
    """Ensure the local database exists and return the CSV source label."""
    return bootstrap_local_store(force=False)


def run_query(sql: str, limit: int = 200) -> QueryResult:
    """Execute a read-only SQL query against the local analytics store."""
    ensure_local_store()
    stripped = sql.strip().rstrip(";")
    lowered = stripped.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise ValueError("Only SELECT statements are allowed")
    if not re.search(r"\blimit\s+\d+\b", lowered):
        stripped = f"{stripped} LIMIT {limit}"
    start = perf_counter()
    conn = _connect()
    try:
        cursor = conn.execute(stripped)
        rows = [dict(row) for row in cursor.fetchall()]
        columns = [description[0] for description in cursor.description or []]
    finally:
        conn.close()
    elapsed_ms = (perf_counter() - start) * 1000
    return QueryResult(columns=columns, rows=rows, elapsed_ms=elapsed_ms, row_count=len(rows), source="sqlite_local")


def table_counts() -> dict[str, int]:
    """Return row counts for base and aggregate tables."""
    ensure_local_store()
    conn = _connect()
    try:
        return {table: conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"] for table in (*CSV_TABLES.values(), *MATERIALIZED_VIEW_NAMES)}
    finally:
        conn.close()
