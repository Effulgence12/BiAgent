"""Local SQLite analytics store used for one-command demos and tests.

MySQL remains the target production engine in `sql/`, but this local store makes the
project immediately runnable on a fresh machine after dependencies are installed and
before a MySQL server is configured.
"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from config.settings import settings
from utils.data_bootstrap import ensure_dataset

CSV_TABLES = {
    "olist_customers_dataset.csv": "customers",
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
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def _import_csv(conn: sqlite3.Connection, csv_path: Path, table: str) -> None:
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
    ]
    for statement in statements:
        conn.execute(statement)


def refresh_materialized_views(conn: sqlite3.Connection) -> None:
    """Rebuild SQLite materialized aggregate tables mirroring the MySQL design."""
    for name in MATERIALIZED_VIEW_NAMES:
        conn.execute(f"DROP TABLE IF EXISTS {name}")

    conn.executescript(
        """
        CREATE TABLE mv_monthly_sales AS
        SELECT
          substr(o.order_purchase_timestamp, 1, 7) AS year_month,
          COUNT(DISTINCT o.order_id) AS total_orders,
          ROUND(SUM(CAST(oi.price AS REAL) + CAST(oi.freight_value AS REAL)), 2) AS total_gmv,
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
        """
    )


def bootstrap_local_store(force: bool = False, data_dir: Path | None = None, db_path: Path | None = None) -> str:
    """Create a local SQLite store from CSVs and refresh materialized tables."""
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
    if not stripped.lower().startswith("select"):
        raise ValueError("Only SELECT statements are allowed")
    if " limit " not in f" {stripped.lower()} ":
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
