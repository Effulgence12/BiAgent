# 队友使用组员 A 版本说明

> 适用场景：其他组员拉取/复制当前版本后，需要在自己的电脑上复现 MySQL 数据层、运行 Web/CLI，并理解组员 A 对数据层和 Agent 查询逻辑做过哪些修改。

## 1. 队友前置准备

### 1.1 Conda 环境

推荐统一使用项目环境名：

```bash
conda create -n bussiness_final python=3.11 -y
conda activate bussiness_final
cd /Users/salad/Desktop/final
pip install -r requirements.txt
```

说明：`requirements.txt` 中新增了 `cryptography`，这是 PyMySQL 连接 MySQL 8 默认 `caching_sha2_password` 认证方式所需依赖。没有它时可能报：

```text
cryptography package is required for sha256_password or caching_sha2_password
```

### 1.2 数据文件

9 张 Olist 原始 CSV 需要放在：

```text
data/raw/
```

必须包含：

```text
olist_customers_dataset.csv
olist_geolocation_dataset.csv
olist_orders_dataset.csv
olist_order_items_dataset.csv
olist_products_dataset.csv
olist_sellers_dataset.csv
olist_order_payments_dataset.csv
olist_order_reviews_dataset.csv
product_category_name_translation.csv
```

### 1.3 MySQL

本版本正式查询口径为 MySQL。队友需要本地或远程可用 MySQL。

本地 macOS 可参考：

```bash
brew install mysql
brew services start mysql
```

如果使用远程 MySQL，只要 `.env` 指向同一个远程库即可。

### 1.4 `.env` 配置

复制示例配置：

```bash
cp .env.example .env
```

至少需要配置：

```bash
ENABLE_LLM=1
QWEN_API_KEY=你的key
QWEN_MODEL=qwen3.6-plus

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=你的MySQL密码
MYSQL_DATABASE=agentic_bi_olist
PREFER_MYSQL=1

DATA_DIR=data/raw
LOCAL_DB_PATH=data/local/agentic_bi_olist.sqlite
```

注意：`PREFER_MYSQL=1` 表示系统统一查询入口会走 MySQL；如果设为 `0`，则使用 SQLite 兜底演示路径。

## 2. MySQL 初始化与刷新

首次全量建库、清洗导入 CSV、刷新预聚合表：

```bash
conda activate bussiness_final
cd /Users/salad/Desktop/final
python -m utils.db_init --mysql-bootstrap --force
```

后续只刷新预聚合表：

```bash
python -m utils.db_init --mysql-bootstrap
```

查看基础表和预聚合表行数：

```bash
python -m utils.db_init --counts
```

当前组员 A 本机成功校验过的核心行数：

```text
orders: 99441
order_items: 112650
geolocation: 1000163
mv_monthly_sales: 23
mv_state_sales: 556
mv_delivery_perf: 556
mv_seller_perf: 16068
mv_review_topics: 455
```

## 3. 运行与验证

启动 Web：

```bash
uvicorn app:app --reload
```

浏览器访问：

```text
http://127.0.0.1:8000
```

CLI 测试：

```bash
python cli.py "2017年GMV是多少？按月和各州排名的趋势怎样？"
python cli.py "平台整体准时交付率是多少？哪些州延迟最严重？"
python cli.py "为什么某些州的平均配送时长显著高于全国均值？哪些卖家的差评率最高？"
```

单元测试：

```bash
python -m pytest -q tests -p no:cacheprovider
```

组员 A 当前验证结果：

```text
34 passed, 1 warning
```

确认当前查询入口是否真的走 MySQL：

```bash
python -c "from utils.local_store import run_query; r=run_query('SELECT year_month,total_gmv FROM mv_monthly_sales ORDER BY year_month LIMIT 1'); print(r.source, r.rows)"
```

应输出：

```text
mysql [...]
```

## 4. 性能对比与截图

性能对比脚本：

```bash
python -m utils.perf_compare
```

它会自动跑 3 组：

```text
基础表 JOIN vs mv_monthly_sales
基础表 JOIN vs mv_state_sales
基础表 JOIN vs mv_delivery_perf
```

组员 A 本机一次运行结果：

```text
月度 GMV: 284.59ms -> 1.34ms, 约 212.03x
州销售排行: 464.05ms -> 8.87ms, 约 52.31x
配送延迟: 233.41ms -> 1.29ms, 约 181.11x
```

正式报告截图时请以自己机器重新运行结果为准。

## 5. 组员 A 对数据层做了什么

### 5.1 新增 MySQL 数据层

新增：

```text
utils/mysql_store.py
```

作用：

- 连接 MySQL。
- 执行 `sql/schema.sql` 和 `sql/materialized_views.sql`。
- 清洗导入 9 张 Olist CSV。
- 刷新全部 `mv_*` 预聚合表。
- 在 MySQL 中生成 `mv_review_topics`。
- 提供 MySQL 只读查询入口和表行数校验。

### 5.2 升级统一查询入口

修改：

```text
utils/local_store.py
```

现在逻辑是：

- `PREFER_MYSQL=1`：`run_query()`、`table_counts()`、`bootstrap_local_store()` 走 MySQL。
- `PREFER_MYSQL=0`：保留 SQLite 本地兜底。

这样 Agent 和前端无需关心底层是 MySQL 还是 SQLite。

### 5.3 数据清洗策略

MySQL 导入时完成：

- CSV 空字符串转 `NULL`。
- 时间字段转 MySQL `DATETIME`。
- 金额字段转 `DECIMAL(12,2)`。
- 分期数、评分、邮编、商品重量/尺寸等转整数或数值。
- 修正 Kaggle 产品字段拼写：
  - `product_name_lenght` -> `product_name_length`
  - `product_description_lenght` -> `product_description_length`
- 保留评论字段：
  - `review_comment_title`
  - `review_comment_message`
  - `review_creation_date`
  - `review_answer_timestamp`
- 预聚合中默认使用 `order_status='delivered'` 的已交付订单计算 GMV、配送、支付和预测指标。

### 5.4 修正 MySQL schema 与视图字段

修改：

```text
sql/schema.sql
sql/materialized_views.sql
config/views_desc.py
utils/schema.py
```

主要补充：

- `order_reviews` 增加评论标题和评论时间字段。
- `mv_monthly_sales` 增加 `unique_customers`。
- `mv_state_sales` 增加 `unique_customers`。
- `mv_category_sales` 增加 `product_category_english`、`avg_price`。
- `mv_delivery_perf` 增加 `delayed_orders`、`on_time_orders`、`on_time_rate`。
- `mv_payment_dist` 增加 `total_transactions`、`avg_installments`。
- `mv_seller_perf` 增加：
  - `total_reviews`
  - `negative_reviews`
  - `negative_rate`

其中 `negative_rate` 使用 distinct review 口径，避免多商品订单 JOIN 后重复计数导致差评率大于 1。

## 6. 组员 A 对 Agent 查询逻辑做了什么

修改文件：

```text
agents/data_analyst.py
```

### 6.1 提示词约束

DataAnalyst 的 SQL 规划提示词新增了历史数据约束：

- Olist 是 2016-09 到 2018-10 的静态历史数据。
- 除非用户明确要求当前时间，否则不要使用 `CURDATE()`、`NOW()` 或“最近 12 个月”过滤。

这样可以避免模型在 2026 年运行时生成“过去 12 个月”的 SQL，导致历史数据被过滤为空。

### 6.2 卖家差评率优先走 `mv_seller_perf`

以前用户问“哪些卖家的差评率最高”，系统容易被“差评”关键词带到 `mv_review_category_perf`，最后回答成“差评品类”。

现在逻辑改为：

- 如果问题同时包含“卖家/seller”和“差评/评分/review/negative”，优先使用 `seller_review` 任务。
- `seller_review` 查询直接基于 `mv_seller_perf.negative_rate` 排序。

核心 SQL 形态：

```sql
SELECT seller_id,
       seller_state,
       SUM(total_orders) AS total_orders,
       SUM(total_reviews) AS total_reviews,
       SUM(negative_reviews) AS negative_reviews,
       ROUND(1.0 * SUM(negative_reviews) / NULLIF(SUM(total_reviews), 0), 4) AS negative_rate,
       ROUND(AVG(avg_review_score), 2) AS avg_review_score
FROM mv_seller_perf
GROUP BY seller_id, seller_state
HAVING total_reviews >= 3
ORDER BY negative_rate DESC, total_reviews DESC, avg_review_score ASC
LIMIT 20;
```

### 6.3 配送时长问题增加标准证据

新增固定证据任务：

```text
delivery_duration_by_state
```

用于回答：

```text
为什么某些州的平均配送时长显著高于全国均值？
```

它按州聚合 `mv_delivery_perf`，按 `avg_delivery_days` 降序展示高配送时长州，并配合 `delivery_overall` 给出全国平均值。

### 6.4 摘要证据排序与过滤

对“配送 + 卖家差评率”这类标准问题，现在会优先把以下标准证据放到直答摘要前面：

```text
seller_review
delivery_overall
delivery_duration_by_state
delivery_by_state
```

同时减少 LLM 自由 SQL 对最终直答的干扰，避免出现非标准口径或空结果污染答案。

## 7. 当前修复后的代表性问题

建议队友重点测试：

```text
为什么某些州的平均配送时长显著高于全国均值？哪些卖家的差评率最高？
```

修复后应看到：

- 命中视图包含 `mv_seller_perf` 和 `mv_delivery_perf`。
- 主 SQL 使用 `mv_seller_perf`。
- 卖家结果包含 `negative_rate`，且范围为 `0-1`。
- 配送回答使用全国平均配送时长约 `12.09` 天。
- 示例结论类似：

```text
RR 州平均配送时长约 28.98 天，显著高于全国均值 12.09 天；
差评率最高卖家如 8d92f3ea807b89465643c219455e7369，negative_rate=1.0。
```

## 8. 注意事项

- 如果 Web 页面仍显示旧结果，先刷新页面或重启 `uvicorn`。
- 如果 MySQL 字段不存在，重新执行：

```bash
python -m utils.db_init --mysql-bootstrap
```

- 如果基础 CSV 重新替换过，执行：

```bash
python -m utils.db_init --mysql-bootstrap --force
```

- 如果队友不配置 MySQL，可以临时使用 `PREFER_MYSQL=0` 跑 SQLite，但正式报告和演示建议统一使用 MySQL。
