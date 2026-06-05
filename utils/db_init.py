"""Database initialization helpers for the Olist MySQL project."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = ROOT / "sql" / "schema.sql"
VIEWS_SQL = ROOT / "sql" / "materialized_views.sql"


def mysql_command(sql_file: Path) -> str:
    """Build a mysql client command for a given SQL file from environment variables."""
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "root")
    database = os.getenv("MYSQL_DATABASE", "agentic_bi_olist")
    password_flag = "-p" if os.getenv("MYSQL_PASSWORD") is None else f"-p{os.getenv('MYSQL_PASSWORD')}"
    return f"mysql -h {host} -P {port} -u {user} {password_flag} {database} < {sql_file}"


def main() -> None:
    """Run or print reproducible database setup commands."""
    parser = argparse.ArgumentParser(description="Initialize the Olist Agentic BI database.")
    parser.add_argument("--print-commands", action="store_true", help="Only print the manual mysql commands.")
    parser.add_argument("--mysql-bootstrap", action="store_true", help="Create schema, import cleaned CSVs, and refresh mv_* in MySQL.")
    parser.add_argument("--force", action="store_true", help="Reload base CSVs before refreshing MySQL pre-aggregations.")
    parser.add_argument("--counts", action="store_true", help="Print MySQL base and mv_* table row counts.")
    args = parser.parse_args()

    if args.mysql_bootstrap:
        from utils.mysql_store import bootstrap_mysql_store, table_counts_mysql

        source = bootstrap_mysql_store(force=args.force)
        print(json.dumps({"source": source, "counts": table_counts_mysql()}, ensure_ascii=False, indent=2))
        return

    if args.counts:
        from utils.mysql_store import table_counts_mysql

        print(json.dumps(table_counts_mysql(), ensure_ascii=False, indent=2))
        return

    print("1. Create schema and base tables:")
    print(mysql_command(SCHEMA_SQL))
    print("2. Import Olist CSV files into the base tables.")
    print("3. Refresh pre-aggregated tables:")
    print(mysql_command(VIEWS_SQL))


if __name__ == "__main__":
    main()
