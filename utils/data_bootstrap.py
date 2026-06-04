"""Validate or download the real Olist CSV files required by the assignment.

The assignment source is Kaggle's Brazilian E-Commerce Public Dataset by Olist.
For one-command startup we download the same real CSV files from a public GitHub
mirror when local files are missing. We never generate substitute data.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAW_FILES = {
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
}

GITHUB_RAW_BASE_URLS = (
    "https://raw.githubusercontent.com/Athospd/work-at-olist-data/master/datasets",
    "https://raw.githubusercontent.com/spdrio/Brazilian-E-Commerce-Public-Dataset-by-Olist/master/files",
)


class DatasetValidationError(RuntimeError):
    """Raised when the real Olist CSV set is incomplete."""


def missing_required_csvs(data_dir: Path) -> list[str]:
    """Return required CSV names that are absent or empty."""
    return sorted(name for name in RAW_FILES if not (data_dir / name).exists() or (data_dir / name).stat().st_size <= 0)


def has_required_csvs(data_dir: Path) -> bool:
    """Return True when all required CSV files exist and are non-empty."""
    return not missing_required_csvs(data_dir)


def download_olist_csvs(data_dir: Path, timeout: int = 30) -> bool:
    """Download Olist CSV files from a public GitHub mirror.

    Kaggle is the assignment source, but browser/API downloads require Kaggle
    credentials. The mirror stores the original CSV files as ordinary raw URLs,
    which keeps startup reproducible without creating fake data.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for name in sorted(RAW_FILES):
        dest = data_dir / name
        if dest.exists() and dest.stat().st_size > 0:
            continue
        for base_url in GITHUB_RAW_BASE_URLS:
            url = f"{base_url}/{urllib.parse.quote(name)}"
            try:
                urllib.request.urlretrieve(url, dest)
                break
            except (urllib.error.URLError, OSError) as exc:
                last_error = exc
                if dest.exists() and dest.stat().st_size == 0:
                    dest.unlink()
        else:
            raise DatasetValidationError(f"下载 {name} 失败：{last_error}")
    return has_required_csvs(data_dir)


def ensure_dataset(data_dir: Path) -> str:
    """Ensure CSV data exists and return the source label used."""
    missing = missing_required_csvs(data_dir)
    if not missing:
        return "existing_real_olist_csv"
    try:
        if download_olist_csvs(data_dir):
            return "downloaded_real_olist_csv_github_mirror"
    except (urllib.error.URLError, OSError, DatasetValidationError) as exc:
        joined = ", ".join(missing)
        raise DatasetValidationError(f"缺少真实 Olist 原始 CSV：{joined}；自动下载失败：{exc}") from exc
    remaining = ", ".join(missing_required_csvs(data_dir))
    raise DatasetValidationError(f"真实 Olist CSV 下载后仍不完整：{remaining}")
