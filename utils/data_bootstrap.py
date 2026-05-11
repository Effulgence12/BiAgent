"""Download real Olist CSV files or generate realistic demo CSVs.

The primary data source is the public GitHub mirror of the Kaggle Olist dataset.
If network access is unavailable, a deterministic multi-table demo dataset is generated
with the same table names and key relationships used by the project.
"""

from __future__ import annotations

import csv
import json
import random
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

RAW_FILES = {
    "olist_customers_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
}

GITHUB_CONTENTS_URL = "https://api.github.com/repos/spdrio/Brazilian-E-Commerce-Public-Dataset-by-Olist/contents/files"


def has_required_csvs(data_dir: Path) -> bool:
    """Return True when all required CSV files exist and are non-empty."""
    return all((data_dir / name).exists() and (data_dir / name).stat().st_size > 0 for name in RAW_FILES)


def download_olist_csvs(data_dir: Path, timeout: int = 30) -> bool:
    """Download Olist CSV files from a public GitHub mirror.

    Returns True on success. Any exception is swallowed so callers can fall back to
    generated data without making the app fail at startup.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(GITHUB_CONTENTS_URL, timeout=timeout) as response:
            items = json.loads(response.read().decode("utf-8"))
        downloads = {item["name"]: item["download_url"] for item in items if item["name"] in RAW_FILES}
        if set(downloads) != RAW_FILES:
            return False
        for name, url in downloads.items():
            dest = data_dir / name
            if dest.exists() and dest.stat().st_size > 0:
                continue
            urllib.request.urlretrieve(url, dest)
        return has_required_csvs(data_dir)
    except Exception:
        return False


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate_demo_csvs(data_dir: Path, orders_count: int = 2400, seed: int = 2026) -> None:
    """Generate a deterministic Olist-like multi-table dataset for offline demos."""
    rng = random.Random(seed)
    states = ["SP", "RJ", "MG", "RS", "PR", "BA", "SC", "GO", "PE", "CE", "DF", "ES"]
    cities = ["sao paulo", "rio de janeiro", "belo horizonte", "porto alegre", "curitiba", "salvador", "recife"]
    categories = [
        ("beleza_saude", "health_beauty"),
        ("cama_mesa_banho", "bed_bath_table"),
        ("esporte_lazer", "sports_leisure"),
        ("informatica_acessorios", "computers_accessories"),
        ("moveis_decoracao", "furniture_decor"),
        ("relogios_presentes", "watches_gifts"),
        ("telefonia", "telephony"),
        ("brinquedos", "toys"),
    ]

    customers = []
    for i in range(1, orders_count + 1):
        state = rng.choice(states)
        customers.append(
            {
                "customer_id": f"cust_{i:06d}",
                "customer_unique_id": f"unique_{rng.randint(1, orders_count // 2):06d}",
                "customer_zip_code_prefix": rng.randint(1000, 99999),
                "customer_city": rng.choice(cities),
                "customer_state": state,
            }
        )

    sellers = []
    for i in range(1, 181):
        sellers.append(
            {
                "seller_id": f"seller_{i:05d}",
                "seller_zip_code_prefix": rng.randint(1000, 99999),
                "seller_city": rng.choice(cities),
                "seller_state": rng.choice(states),
            }
        )

    products = []
    for i in range(1, 520):
        category, _ = rng.choice(categories)
        products.append(
            {
                "product_id": f"prod_{i:06d}",
                "product_category_name": category,
                "product_name_length": rng.randint(20, 80),
                "product_description_length": rng.randint(80, 2500),
                "product_photos_qty": rng.randint(1, 8),
                "product_weight_g": rng.randint(100, 12000),
                "product_length_cm": rng.randint(8, 80),
                "product_height_cm": rng.randint(2, 60),
                "product_width_cm": rng.randint(6, 70),
            }
        )

    start = datetime(2017, 1, 1, 8, 0, 0)
    orders = []
    order_items = []
    payments = []
    reviews = []
    for i, customer in enumerate(customers, start=1):
        order_id = f"order_{i:07d}"
        purchase = start + timedelta(days=rng.randint(0, 540), hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        approved = purchase + timedelta(hours=rng.randint(1, 30))
        carrier = approved + timedelta(days=rng.randint(1, 4))
        promised_days = rng.randint(8, 28)
        delivery_days = max(2, int(rng.gauss(13, 5)))
        if customer["customer_state"] in {"BA", "PE", "CE"}:
            delivery_days += rng.randint(3, 8)
        delivered = purchase + timedelta(days=delivery_days)
        estimated = purchase + timedelta(days=promised_days)
        status = "delivered" if rng.random() > 0.035 else rng.choice(["canceled", "shipped", "invoiced"])
        orders.append(
            {
                "order_id": order_id,
                "customer_id": customer["customer_id"],
                "order_status": status,
                "order_purchase_timestamp": purchase.isoformat(sep=" "),
                "order_approved_at": approved.isoformat(sep=" "),
                "order_delivered_carrier_date": carrier.isoformat(sep=" "),
                "order_delivered_customer_date": delivered.isoformat(sep=" ") if status == "delivered" else "",
                "order_estimated_delivery_date": estimated.isoformat(sep=" "),
            }
        )
        item_count = rng.choices([1, 2, 3, 4], weights=[72, 18, 7, 3], k=1)[0]
        total_value = 0.0
        for item_id in range(1, item_count + 1):
            product = rng.choice(products)
            seller = rng.choice(sellers)
            price = round(rng.lognormvariate(4.25, 0.55), 2)
            freight = round(8 + product["product_weight_g"] / 900 + rng.random() * 18, 2)
            total_value += price + freight
            order_items.append(
                {
                    "order_id": order_id,
                    "order_item_id": item_id,
                    "product_id": product["product_id"],
                    "seller_id": seller["seller_id"],
                    "shipping_limit_date": (purchase + timedelta(days=5)).isoformat(sep=" "),
                    "price": price,
                    "freight_value": freight,
                }
            )
        payment_type = rng.choices(["credit_card", "boleto", "voucher", "debit_card"], weights=[72, 17, 7, 4], k=1)[0]
        payments.append(
            {
                "order_id": order_id,
                "payment_sequential": 1,
                "payment_type": payment_type,
                "payment_installments": rng.choice([1, 1, 1, 2, 3, 4, 6, 10]),
                "payment_value": round(total_value, 2),
            }
        )
        late = delivered > estimated
        score = rng.choices([1, 2, 3, 4, 5], weights=[8 if late else 3, 8 if late else 5, 14, 25, 45 if not late else 20], k=1)[0]
        reviews.append(
            {
                "review_id": f"review_{i:07d}",
                "order_id": order_id,
                "review_score": score,
                "review_comment_message": "Entrega atrasada" if late and score <= 3 else ("Produto excelente" if score >= 4 else "Atendimento regular"),
            }
        )

    translations = [{"product_category_name": original, "product_category_name_english": english} for original, english in categories]
    _write_csv(data_dir / "olist_customers_dataset.csv", customers, list(customers[0]))
    _write_csv(data_dir / "olist_sellers_dataset.csv", sellers, list(sellers[0]))
    _write_csv(data_dir / "olist_products_dataset.csv", products, list(products[0]))
    _write_csv(data_dir / "olist_orders_dataset.csv", orders, list(orders[0]))
    _write_csv(data_dir / "olist_order_items_dataset.csv", order_items, list(order_items[0]))
    _write_csv(data_dir / "olist_order_payments_dataset.csv", payments, list(payments[0]))
    _write_csv(data_dir / "olist_order_reviews_dataset.csv", reviews, list(reviews[0]))
    _write_csv(data_dir / "product_category_name_translation.csv", translations, list(translations[0]))


def ensure_dataset(data_dir: Path) -> str:
    """Ensure CSV data exists and return the source label used."""
    if has_required_csvs(data_dir):
        return "existing_csv"
    if download_olist_csvs(data_dir):
        return "downloaded_olist_github_mirror"
    generate_demo_csvs(data_dir)
    return "generated_demo_csv"
