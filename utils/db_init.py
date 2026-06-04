"""Database initialization helpers for the Olist MySQL project.

This first skeleton intentionally avoids automatic downloads or destructive imports.
Run the printed MySQL commands after placing CSV data in data/raw/ and reviewing SQL.
"""

from __future__ import annotations

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
    """Print reproducible next-step commands for database setup."""
    print("1. Create schema and base tables:")
    print(mysql_command(SCHEMA_SQL))
    print("2. Import Olist CSV files into the base tables.")
    print("3. Refresh pre-aggregated tables:")
    print(mysql_command(VIEWS_SQL))


if __name__ == "__main__":
    main()
