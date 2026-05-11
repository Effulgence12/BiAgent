"""Runtime settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    """Application settings with safe local defaults."""

    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/chat/completions")
    mysql_host: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user: str = os.getenv("MYSQL_USER", "root")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "")
    mysql_database: str = os.getenv("MYSQL_DATABASE", "agentic_bi_olist")
    data_dir: Path = Path(os.getenv("DATA_DIR", ROOT_DIR / "data" / "raw"))
    local_db_path: Path = Path(os.getenv("LOCAL_DB_PATH", ROOT_DIR / "data" / "local" / "agentic_bi_olist.sqlite"))
    prefer_mysql: bool = os.getenv("PREFER_MYSQL", "0") == "1"
    auto_bootstrap_data: bool = os.getenv("AUTO_BOOTSTRAP_DATA", "1") == "1"


settings = Settings()
