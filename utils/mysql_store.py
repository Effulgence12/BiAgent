"""MySQL analytics store for the Olist Agentic BI project.

The runtime can still fall back to SQLite for lightweight local demos, but the
assignment asks for MySQL as the query engine. This module owns the reproducible
MySQL path: typed CSV import, pre-aggregation refresh, read-only query execution,
and row-count validation.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from time import perf_counter
from typing import Callable, Iterable

import pymysql
from pymysql.cursors import DictCursor

from config.settings import ROOT_DIR, settings
from utils.data_bootstrap import ensure_dataset
from utils.review_topics import PORTUGUESE_STOPWORDS

SCHEMA_SQL = ROOT_DIR / "sql" / "schema.sql"
VIEWS_SQL = ROOT_DIR / "sql" / "materialized_views.sql"

BASE_TABLE_NAMES = (
    "customers",
    "geolocation",
    "orders",
    "order_items",
    "products",
    "sellers",
    "order_payments",
    "order_reviews",
    "product_category_name_translation",
)

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
class ImportSpec:
    """One CSV-to-MySQL table import contract."""

    csv_name: str
    table: str
    columns: tuple[str, ...]
    source_columns: dict[str, str]
    converters: dict[str, Callable[[str | None], object]]


def _connect(*, database: bool = True, autocommit: bool = False):
    return pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database if database else None,
        charset="utf8mb4",
        autocommit=autocommit,
        cursorclass=DictCursor,
        local_infile=True,
    )


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _clean_int(value: str | None) -> int | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def _clean_decimal(value: str | None) -> Decimal | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _clean_datetime(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    # Olist timestamps are already ISO-like strings accepted by MySQL DATETIME.
    return cleaned


def _identity(value: str | None) -> str | None:
    return _clean_text(value)


def _spec(
    csv_name: str,
    table: str,
    columns: Iterable[str],
    converters: dict[str, Callable[[str | None], object]] | None = None,
    source_columns: dict[str, str] | None = None,
) -> ImportSpec:
    cols = tuple(columns)
    return ImportSpec(
        csv_name=csv_name,
        table=table,
        columns=cols,
        source_columns=source_columns or {},
        converters={column: (converters or {}).get(column, _identity) for column in cols},
    )


IMPORT_SPECS = (
    _spec(
        "olist_customers_dataset.csv",
        "customers",
        ("customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"),
        {"customer_zip_code_prefix": _clean_int},
    ),
    _spec(
        "olist_geolocation_dataset.csv",
        "geolocation",
        ("geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng", "geolocation_city", "geolocation_state"),
        {
            "geolocation_zip_code_prefix": _clean_int,
            "geolocation_lat": _clean_decimal,
            "geolocation_lng": _clean_decimal,
        },
    ),
    _spec(
        "olist_products_dataset.csv",
        "products",
        (
            "product_id",
            "product_category_name",
            "product_name_length",
            "product_description_length",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ),
        {
            "product_name_length": _clean_int,
            "product_description_length": _clean_int,
            "product_photos_qty": _clean_int,
            "product_weight_g": _clean_int,
            "product_length_cm": _clean_int,
            "product_height_cm": _clean_int,
            "product_width_cm": _clean_int,
        },
        {
            # Kaggle ships these two columns with the historical "lenght" typo.
            "product_name_length": "product_name_lenght",
            "product_description_length": "product_description_lenght",
        },
    ),
    _spec(
        "olist_sellers_dataset.csv",
        "sellers",
        ("seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"),
        {"seller_zip_code_prefix": _clean_int},
    ),
    _spec(
        "product_category_name_translation.csv",
        "product_category_name_translation",
        ("product_category_name", "product_category_name_english"),
    ),
    _spec(
        "olist_orders_dataset.csv",
        "orders",
        (
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ),
        {
            "order_purchase_timestamp": _clean_datetime,
            "order_approved_at": _clean_datetime,
            "order_delivered_carrier_date": _clean_datetime,
            "order_delivered_customer_date": _clean_datetime,
            "order_estimated_delivery_date": _clean_datetime,
        },
    ),
    _spec(
        "olist_order_items_dataset.csv",
        "order_items",
        ("order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"),
        {
            "order_item_id": _clean_int,
            "shipping_limit_date": _clean_datetime,
            "price": _clean_decimal,
            "freight_value": _clean_decimal,
        },
    ),
    _spec(
        "olist_order_payments_dataset.csv",
        "order_payments",
        ("order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"),
        {
            "payment_sequential": _clean_int,
            "payment_installments": _clean_int,
            "payment_value": _clean_decimal,
        },
    ),
    _spec(
        "olist_order_reviews_dataset.csv",
        "order_reviews",
        (
            "review_id",
            "order_id",
            "review_score",
            "review_comment_title",
            "review_comment_message",
            "review_creation_date",
            "review_answer_timestamp",
        ),
        {
            "review_score": _clean_int,
            "review_creation_date": _clean_datetime,
            "review_answer_timestamp": _clean_datetime,
        },
    ),
)


def _split_sql_script(script: str) -> list[str]:
    """Split project SQL scripts into executable statements."""
    statements: list[str] = []
    current: list[str] = []
    quote: str | None = None
    line_comment = False
    index = 0
    while index < len(script):
        char = script[index]
        next_char = script[index + 1] if index + 1 < len(script) else ""
        if line_comment:
            current.append(char)
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            index += 1
            continue
        if char == "-" and next_char == "-":
            line_comment = True
            current.append(char)
            current.append(next_char)
            index += 2
            continue
        if char in ("'", '"', "`"):
            quote = char
            current.append(char)
            index += 1
            continue
        if char == ";":
            statement = "\n".join(
                line for line in "".join(current).splitlines() if not line.strip().startswith("--")
            ).strip()
            if statement:
                statements.append(statement)
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    tail = "\n".join(line for line in "".join(current).splitlines() if not line.strip().startswith("--")).strip()
    if tail:
        statements.append(tail)
    return statements


def execute_sql_file(path: Path) -> None:
    """Execute a project SQL file through PyMySQL without exposing passwords."""
    conn = _connect(database=False)
    try:
        with conn.cursor() as cursor:
            for statement in _split_sql_script(path.read_text(encoding="utf-8")):
                cursor.execute(statement)
        conn.commit()
    finally:
        conn.close()


def ensure_schema_compatibility() -> None:
    """Add columns introduced after earlier local MySQL bootstraps."""
    required_columns = {
        "order_reviews": {
            "review_comment_title": "TEXT NULL",
            "review_creation_date": "DATETIME NULL",
            "review_answer_timestamp": "DATETIME NULL",
        }
    }
    conn = _connect()
    try:
        with conn.cursor() as cursor:
            for table, columns in required_columns.items():
                cursor.execute(
                    """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    """,
                    (settings.mysql_database, table),
                )
                existing = {row["COLUMN_NAME"] for row in cursor.fetchall()}
                for column, definition in columns.items():
                    if column not in existing:
                        cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")
        conn.commit()
    finally:
        conn.close()


def reset_base_tables() -> None:
    """Truncate base tables in FK-safe order before a clean CSV import."""
    conn = _connect()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS=0")
            for table in reversed(BASE_TABLE_NAMES):
                cursor.execute(f"TRUNCATE TABLE {table}")
            cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        conn.commit()
    finally:
        conn.close()


def import_csvs_to_mysql(data_dir: Path | None = None, batch_size: int = 5000) -> dict[str, int]:
    """Import the Olist CSV set into typed MySQL base tables with explicit cleaning."""
    raw_dir = data_dir or settings.data_dir
    ensure_dataset(raw_dir)
    counts: dict[str, int] = {}
    conn = _connect()
    try:
        with conn.cursor() as cursor:
            for spec in IMPORT_SPECS:
                placeholders = ", ".join(["%s"] * len(spec.columns))
                columns = ", ".join(f"`{column}`" for column in spec.columns)
                insert_sql = f"INSERT INTO `{spec.table}` ({columns}) VALUES ({placeholders})"
                batch: list[tuple[object, ...]] = []
                imported = 0
                with (raw_dir / spec.csv_name).open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        values = []
                        for column in spec.columns:
                            source_column = spec.source_columns.get(column, column)
                            values.append(spec.converters[column](row.get(source_column)))
                        batch.append(tuple(values))
                        if len(batch) >= batch_size:
                            cursor.executemany(insert_sql, batch)
                            imported += len(batch)
                            batch.clear()
                    if batch:
                        cursor.executemany(insert_sql, batch)
                        imported += len(batch)
                counts[spec.table] = imported
                conn.commit()
    finally:
        conn.close()
    return counts


def _create_review_topics_table(conn) -> None:
    with conn.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS mv_review_topics")
        cursor.execute(
            """
            CREATE TABLE mv_review_topics (
              product_category_name VARCHAR(128),
              topic_id INT,
              topic_label VARCHAR(255),
              topic_keywords TEXT,
              complaint_count INT,
              topic_share DECIMAL(10, 4),
              INDEX idx_mv_review_topics_cat (product_category_name)
            )
            """
        )


def build_review_topics_mysql(n_topics: int = 8, max_features: int = 800, top_terms: int = 8) -> None:
    """Build the NMF negative-review topic table in MySQL."""
    try:
        from sklearn.decomposition import NMF
        from sklearn.feature_extraction.text import TfidfVectorizer
    except Exception:
        conn = _connect()
        try:
            _create_review_topics_table(conn)
            conn.commit()
        finally:
            conn.close()
        return

    conn = _connect()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  r.review_id AS review_id,
                  COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS product_category_name,
                  r.review_comment_message AS message
                FROM order_reviews r
                JOIN orders o ON r.order_id = o.order_id
                JOIN order_items oi ON o.order_id = oi.order_id
                LEFT JOIN products p ON oi.product_id = p.product_id
                LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
                WHERE r.review_score <= 2
                  AND COALESCE(r.review_comment_message, '') <> ''
                """
            )
            pairs = cursor.fetchall()
        review_text: dict[str, str] = {}
        for row in pairs:
            review_id = row["review_id"]
            if review_id not in review_text:
                review_text[review_id] = (row["message"] or "").strip()
        review_ids = [rid for rid, text in review_text.items() if text]
        corpus = [review_text[rid] for rid in review_ids]
        if len(corpus) < max(50, n_topics * 5):
            _create_review_topics_table(conn)
            conn.commit()
            return

        vectorizer = TfidfVectorizer(
            strip_accents="unicode",
            lowercase=True,
            stop_words=PORTUGUESE_STOPWORDS,
            token_pattern=r"(?u)\b[a-zA-Z]{3,}\b",
            ngram_range=(1, 2),
            min_df=5,
            max_df=0.5,
            max_features=max_features,
        )
        matrix = vectorizer.fit_transform(corpus)
        if matrix.shape[1] == 0:
            _create_review_topics_table(conn)
            conn.commit()
            return

        topics = min(n_topics, matrix.shape[1], len(corpus))
        model = NMF(n_components=topics, init="nndsvda", max_iter=400, random_state=42)
        weights = model.fit_transform(matrix)
        terms = vectorizer.get_feature_names_out()

        topic_keywords: dict[int, str] = {}
        topic_label: dict[int, str] = {}
        for topic_id, component in enumerate(model.components_):
            ranked = component.argsort()[::-1]
            keywords = [terms[i] for i in ranked[:top_terms]]
            topic_keywords[topic_id] = ", ".join(keywords)
            topic_label[topic_id] = " · ".join(keywords[:3])

        dominant = weights.argmax(axis=1)
        review_topic = {review_ids[i]: int(dominant[i]) for i in range(len(review_ids))}

        category_topic_counts: dict[tuple[str, int], int] = {}
        overall_counts: dict[int, int] = {}
        seen_overall: set[tuple[str, int]] = set()
        for row in pairs:
            review_id = row["review_id"]
            if review_id not in review_topic:
                continue
            topic_id = review_topic[review_id]
            category = row["product_category_name"]
            key = (category, topic_id)
            category_topic_counts[key] = category_topic_counts.get(key, 0) + 1
            overall_key = (review_id, topic_id)
            if overall_key not in seen_overall:
                seen_overall.add(overall_key)
                overall_counts[topic_id] = overall_counts.get(topic_id, 0) + 1

        category_totals: dict[str, int] = {}
        for (category, _topic), count in category_topic_counts.items():
            category_totals[category] = category_totals.get(category, 0) + count
        overall_total = sum(overall_counts.values())

        records: list[tuple[str, int, str, str, int, float]] = []
        for (category, topic_id), count in category_topic_counts.items():
            share = round(count / category_totals[category], 4) if category_totals[category] else 0.0
            records.append((category, topic_id, topic_label[topic_id], topic_keywords[topic_id], count, share))
        for topic_id, count in overall_counts.items():
            share = round(count / overall_total, 4) if overall_total else 0.0
            records.append(("ALL", topic_id, topic_label[topic_id], topic_keywords[topic_id], count, share))

        _create_review_topics_table(conn)
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO mv_review_topics
                  (product_category_name, topic_id, topic_label, topic_keywords, complaint_count, topic_share)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                records,
            )
        conn.commit()
    finally:
        conn.close()


def refresh_materialized_views_mysql() -> None:
    """Refresh all SQL pre-aggregations and Python-built review topics."""
    execute_sql_file(VIEWS_SQL)
    build_review_topics_mysql()


def bootstrap_mysql_store(force: bool = False) -> str:
    """Create schema, optionally reload CSVs, and refresh MySQL pre-aggregations."""
    source = ensure_dataset(settings.data_dir)
    execute_sql_file(SCHEMA_SQL)
    ensure_schema_compatibility()
    if force or not _base_tables_have_rows():
        reset_base_tables()
        import_csvs_to_mysql(settings.data_dir)
    refresh_materialized_views_mysql()
    return f"mysql:{source}"


def _base_tables_have_rows() -> bool:
    try:
        counts = table_counts_mysql(base_only=True)
    except Exception:
        return False
    return all(counts.get(table, 0) > 0 for table in BASE_TABLE_NAMES)


def _normalize_value(value: object) -> object:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def run_query_mysql(sql: str, limit: int = 200) -> tuple[list[str], list[dict[str, object]], float, str]:
    """Execute a read-only query against MySQL and return normalized rows."""
    stripped = sql.strip().rstrip(";")
    stripped = re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)\.year_month\b", r"\1.`year_month`", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"(?<![`.'\"])\byear_month\b(?![`'\"])", "`year_month`", stripped, flags=re.IGNORECASE)
    lowered = stripped.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise ValueError("Only SELECT statements are allowed")
    if ";" in stripped:
        raise ValueError("Only one SELECT statement is allowed")
    if not re.search(r"\blimit\s+\d+\b", lowered):
        stripped = f"{stripped} LIMIT {limit}"
    start = perf_counter()
    conn = _connect()
    try:
        with conn.cursor() as cursor:
            cursor.execute(stripped)
            raw_rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description or []]
    finally:
        conn.close()
    elapsed_ms = (perf_counter() - start) * 1000
    rows = [{key: _normalize_value(value) for key, value in row.items()} for row in raw_rows]
    return columns, rows, elapsed_ms, "mysql"


def table_counts_mysql(*, base_only: bool = False) -> dict[str, int]:
    """Return row counts for MySQL base and aggregate tables."""
    tables = BASE_TABLE_NAMES if base_only else (*BASE_TABLE_NAMES, *MATERIALIZED_VIEW_NAMES)
    conn = _connect()
    counts: dict[str, int] = {}
    try:
        with conn.cursor() as cursor:
            for table in tables:
                cursor.execute("SHOW TABLES LIKE %s", (table,))
                if cursor.fetchone() is None:
                    counts[table] = 0
                    continue
                cursor.execute(f"SELECT COUNT(*) AS n FROM `{table}`")
                counts[table] = int(cursor.fetchone()["n"])
    finally:
        conn.close()
    return counts
