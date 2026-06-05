"""Run MySQL base-table vs pre-aggregated-view performance comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from utils.mysql_store import _connect


@dataclass(frozen=True)
class PerfCase:
    """One comparable base-table and mv_* query pair."""

    name: str
    base_sql: str
    mv_sql: str


PERF_CASES = (
    PerfCase(
        name="月度 GMV",
        base_sql="""
        SELECT DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS `year_month`,
               COUNT(DISTINCT o.order_id) AS total_orders,
               SUM(oi.price + oi.freight_value) AS total_gmv
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.order_status = 'delivered'
        GROUP BY `year_month`
        ORDER BY `year_month`
        """,
        mv_sql="""
        SELECT `year_month`, total_orders, total_gmv
        FROM mv_monthly_sales
        ORDER BY `year_month`
        """,
    ),
    PerfCase(
        name="州销售排行",
        base_sql="""
        SELECT c.customer_state,
               COUNT(DISTINCT o.order_id) AS total_orders,
               SUM(oi.price + oi.freight_value) AS total_gmv
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.order_status = 'delivered'
        GROUP BY c.customer_state
        ORDER BY total_gmv DESC
        """,
        mv_sql="""
        SELECT customer_state,
               SUM(total_orders) AS total_orders,
               SUM(total_gmv) AS total_gmv
        FROM mv_state_sales
        GROUP BY customer_state
        ORDER BY total_gmv DESC
        """,
    ),
    PerfCase(
        name="配送延迟",
        base_sql="""
        SELECT c.customer_state,
               COUNT(DISTINCT o.order_id) AS total_orders,
               AVG(TIMESTAMPDIFF(DAY, o.order_purchase_timestamp, o.order_delivered_customer_date)) AS avg_delivery_days,
               SUM(o.order_delivered_customer_date > o.order_estimated_delivery_date) AS delayed_orders
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL
        GROUP BY c.customer_state
        ORDER BY delayed_orders DESC
        """,
        mv_sql="""
        SELECT customer_state,
               SUM(total_orders) AS total_orders,
               SUM(avg_delivery_days * total_orders) / NULLIF(SUM(total_orders), 0) AS avg_delivery_days,
               SUM(delayed_orders) AS delayed_orders
        FROM mv_delivery_perf
        GROUP BY customer_state
        ORDER BY delayed_orders DESC
        """,
    ),
)


def _time_query(cursor, sql: str) -> tuple[float, int]:
    start = perf_counter()
    cursor.execute(sql)
    rows = cursor.fetchall()
    elapsed_ms = (perf_counter() - start) * 1000
    return elapsed_ms, len(rows)


def run_perf_comparison() -> list[dict[str, object]]:
    """Return elapsed-time evidence for all performance comparison cases."""
    conn = _connect()
    try:
        with conn.cursor() as cursor:
            results = []
            for case in PERF_CASES:
                base_ms, base_rows = _time_query(cursor, case.base_sql)
                mv_ms, mv_rows = _time_query(cursor, case.mv_sql)
                speedup = base_ms / mv_ms if mv_ms > 0 else None
                results.append(
                    {
                        "case": case.name,
                        "base_ms": round(base_ms, 2),
                        "mv_ms": round(mv_ms, 2),
                        "speedup": round(speedup, 2) if speedup is not None else None,
                        "base_rows": base_rows,
                        "mv_rows": mv_rows,
                        "base_sql": " ".join(case.base_sql.split()),
                        "mv_sql": " ".join(case.mv_sql.split()),
                    }
                )
            return results
    finally:
        conn.close()


def main() -> None:
    results = run_perf_comparison()
    print("| 对比项 | 基础表耗时(ms) | 预聚合耗时(ms) | 加速倍数 | 基础表行数 | 预聚合行数 |")
    print("| --- | ---: | ---: | ---: | ---: | ---: |")
    for item in results:
        print(
            f"| {item['case']} | {item['base_ms']} | {item['mv_ms']} | "
            f"{item['speedup']}x | {item['base_rows']} | {item['mv_rows']} |"
        )
    print("\nSQL 明细：")
    for item in results:
        print(f"\n[{item['case']}] 基础表 SQL:\n{item['base_sql']}")
        print(f"[{item['case']}] 预聚合 SQL:\n{item['mv_sql']}")


if __name__ == "__main__":
    main()
