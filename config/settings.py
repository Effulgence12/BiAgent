"""Runtime settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


def _bool_env(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Application settings with safe local defaults."""

    qwen_api_key: str = os.getenv("QWEN_API_KEY", os.getenv("DASHSCOPE_API_KEY", ""))
    qwen_model: str = os.getenv("QWEN_MODEL", "qwen3.6-plus")
    qwen_base_url: str = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    enable_llm: bool = _bool_env("ENABLE_LLM", "0")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "512"))
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
    prefer_mysql: bool = _bool_env("PREFER_MYSQL", "0")
    auto_bootstrap_data: bool = _bool_env("AUTO_BOOTSTRAP_DATA", "1")


settings = Settings()
