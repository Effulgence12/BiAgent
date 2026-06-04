"""Unsupervised topic mining over negative review text (BI insight layer).

商务智能的核心是把非结构化数据转成可执行的经营洞察。原 mv_review_category_perf 用
葡萄牙语关键词 LIKE 把差评粗分类，绝大多数评论落入“其他投诉”黑洞，无法支撑决策。
这里改用 TF-IDF + NMF 对负面评论文本做无监督主题建模，自动学习数据驱动的差评主题，
并按品类聚合成 mv_review_topics，供 DataAnalyst 取证、DecisionMaker 生成针对性建议。

模型在本地 ETL 阶段训练（秒级、无模型下载），运行时只查预聚合结果，零额外负担。
"""

from __future__ import annotations

import sqlite3

REVIEW_TOPICS_COLUMNS = (
    "product_category_name",
    "topic_id",
    "topic_label",
    "topic_keywords",
    "complaint_count",
    "topic_share",
)

# 葡萄牙语虚词停用词表：只移除无业务含义的功能词，保留 produto/entrega 等主题词。
PORTUGUESE_STOPWORDS = [
    "a", "ao", "aos", "as", "ate", "com", "como", "da", "das", "de", "dela", "dele",
    "demais", "depois", "do", "dos", "e", "ela", "elas", "ele", "eles", "em", "entre",
    "era", "essa", "essas", "esse", "esses", "esta", "estamos", "estao", "estas", "este",
    "estes", "eu", "foi", "fomos", "for", "foram", "isso", "isto", "ja", "la", "lhe",
    "lhes", "mais", "mas", "me", "mesmo", "meu", "minha", "muito", "na", "nao", "nas",
    "nem", "no", "nos", "nossa", "nosso", "num", "numa", "o", "os", "ou", "para", "pela",
    "pelo", "por", "porque", "pois", "qual", "quando", "que", "se", "sem", "ser", "seu",
    "sua", "tambem", "te", "tem", "ter", "teu", "tua", "um", "uma", "vc", "voce", "vos",
    "ainda", "so", "ja", "aqui", "esta", "estou", "fui", "ficou", "deu", "vez", "todo",
    "toda", "tudo", "coisa", "pra", "pro", "ne", "ate",
]


def _create_empty_table(conn: sqlite3.Connection) -> None:
    columns = ", ".join(
        f"{name} {'TEXT' if name in ('product_category_name', 'topic_label', 'topic_keywords') else 'REAL'}"
        for name in REVIEW_TOPICS_COLUMNS
    )
    conn.execute(f"CREATE TABLE mv_review_topics ({columns})")
    conn.execute("CREATE INDEX idx_mv_review_topics_cat ON mv_review_topics(product_category_name)")


_NEGATIVE_REVIEW_SQL = """
SELECT
  r.review_id AS review_id,
  COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS product_category_name,
  r.review_comment_message AS message
FROM order_reviews r
JOIN orders o ON r.order_id = o.order_id
JOIN order_items oi ON o.order_id = oi.order_id
LEFT JOIN products p ON oi.product_id = p.product_id
LEFT JOIN product_category_name_translation t ON p.product_category_name = t.product_category_name
WHERE CAST(r.review_score AS INTEGER) <= 2
  AND COALESCE(r.review_comment_message, '') <> ''
"""


def build_review_topic_table(
    conn: sqlite3.Connection,
    n_topics: int = 8,
    max_features: int = 800,
    top_terms: int = 8,
) -> None:
    """Mine negative-review topics with TF-IDF + NMF and aggregate them per category.

    失败或样本不足时建立空表（不阻断整条 ETL），保持与其他 mv_* 一致的查询契约。
    """
    conn.execute("DROP TABLE IF EXISTS mv_review_topics")
    try:
        from sklearn.decomposition import NMF
        from sklearn.feature_extraction.text import TfidfVectorizer
    except Exception:
        _create_empty_table(conn)
        return

    pairs = conn.execute(_NEGATIVE_REVIEW_SQL).fetchall()
    # 去重得到唯一评论文本用于训练（多商品订单会重复同一条评论，避免过采样偏差）。
    review_text: dict[str, str] = {}
    for row in pairs:
        review_id = row["review_id"]
        if review_id not in review_text:
            review_text[review_id] = (row["message"] or "").strip()
    review_ids = [rid for rid, text in review_text.items() if text]
    corpus = [review_text[rid] for rid in review_ids]
    if len(corpus) < max(50, n_topics * 5):
        _create_empty_table(conn)
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
    try:
        matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        # 词表为空等极端情况
        _create_empty_table(conn)
        return
    if matrix.shape[1] == 0:
        _create_empty_table(conn)
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

    # 每条唯一评论取主导主题（NMF 权重最大的成分）。
    dominant = weights.argmax(axis=1)
    review_topic = {review_ids[i]: int(dominant[i]) for i in range(len(review_ids))}

    # 按 (品类, 主题) 聚合；多品类评论按其所属每个品类各计一次，与既有评论视图口径一致。
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
        # 平台级 ALL 按唯一评论计数，避免多品类重复。
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

    _create_empty_table(conn)
    conn.executemany(
        "INSERT INTO mv_review_topics "
        "(product_category_name, topic_id, topic_label, topic_keywords, complaint_count, topic_share) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        records,
    )
