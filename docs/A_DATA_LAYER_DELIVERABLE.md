# 组员 A 数据层交付说明

## 1. 数据源与运行口径

本项目使用 Kaggle Brazilian E-Commerce Public Dataset by Olist 的 9 张原始 CSV，数据放置在 `data/raw/`。当前已完成 MySQL 查询引擎接入，`.env` 中 `PREFER_MYSQL=1` 时，Agent 的统一查询入口 `utils.local_store.run_query()` 会连接 MySQL；`PREFER_MYSQL=0` 时保留 SQLite 作为本地兜底演示引擎。

MySQL 数据库名统一为 `agentic_bi_olist`。基础表与预聚合表共同驻留在 MySQL 中，满足作业“使用 MySQL 作为查询引擎”的要求。

## 2. MySQL 初始化与刷新命令

推荐团队统一使用 conda 环境：

```bash
conda activate bussiness_final
cd /Users/salad/Desktop/final
```

首次全量导入或需要重建时执行：

```bash
python -m utils.db_init --mysql-bootstrap --force
```

后续只刷新预聚合层和校验行数：

```bash
python -m utils.db_init --mysql-bootstrap
python -m utils.db_init --counts
```

正式演示 MySQL 查询路径时 `.env` 需设置：

```bash
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=你的密码
MYSQL_DATABASE=agentic_bi_olist
PREFER_MYSQL=1
```

## 3. 数据清洗与类型处理

清洗逻辑在 `utils/mysql_store.py` 中实现，导入时完成以下处理：

| 类别 | 处理方式 |
| --- | --- |
| 空值 | CSV 空字符串统一转为 `NULL`，避免空字符串参与数值和时间计算。 |
| 时间字段 | `order_purchase_timestamp`、`order_approved_at`、`order_delivered_carrier_date`、`order_delivered_customer_date`、`order_estimated_delivery_date`、`shipping_limit_date`、`review_creation_date`、`review_answer_timestamp` 导入为 MySQL `DATETIME`。 |
| 金额字段 | `price`、`freight_value`、`payment_value` 导入为 `DECIMAL(12,2)`。 |
| 整数字段 | 邮编、分期数、评分、商品重量和尺寸等字段导入为 `INT`。 |
| 产品字段拼写 | Kaggle 原始列 `product_name_lenght`、`product_description_lenght` 统一映射为 `product_name_length`、`product_description_length`。 |
| 评论文本 | 保留 `review_comment_title`、`review_comment_message`、`review_creation_date`、`review_answer_timestamp`，支撑 NLP/主题建模。 |
| 葡语品类 | 通过 `product_category_name_translation` 将葡语品类映射为英文品类，预聚合层优先使用英文名。 |
| 业务过滤 | GMV、配送、支付、预测等核心运营指标默认统计 `order_status='delivered'` 的已交付订单。 |

SQLite 本地导入也同步做了产品字段拼写标准化和评论字段补齐，保证 MySQL 与 SQLite 的基础字段口径一致。

## 4. 预聚合视图设计

当前共维护 11 张预聚合表，超过作业至少 4 张的要求：

| 视图 | 粒度 | 核心用途 |
| --- | --- | --- |
| `mv_monthly_sales` | 年月 | 月度 GMV、订单数、独立客户数、客单价、运费趋势。 |
| `mv_state_sales` | 年月 + 州 | 各州 GMV、订单数、独立客户数和客单价排名。 |
| `mv_category_sales` | 年月 + 品类 | 品类 GMV、订单数、件数、均价表现。 |
| `mv_delivery_perf` | 年月 + 州 | 平均配送时长、延迟单量、准时率和延迟率。 |
| `mv_seller_perf` | 年月 + 卖家 | 卖家 GMV、订单数、平均评分。 |
| `mv_payment_dist` | 年月 + 支付方式 + 分期数 | 支付方式偏好、交易次数、平均分期和支付金额。 |
| `mv_weekly_sales` | 周 | 未来 6 周预测使用的周 GMV 序列。 |
| `mv_state_geo` | 州 | 州级销售指标与经纬度质心，用于地图。 |
| `mv_review_category_perf` | 品类 | 差评率、平均评分和关键词投诉原因分类。 |
| `mv_review_topics` | 品类 + NMF 主题 | 负面评论 TF-IDF + NMF 主题建模结果，支撑差评原因洞察。 |
| `mv_weight_freight` | 重量区间 + 配送状态 | 商品重量/体积与运费关系。 |

Agent 的数据字典在 `config/views_desc.py` 中维护，DataAnalyst Prompt 要求优先选择 `mv_*`，无法覆盖时才回退基础表。

## 5. 当前 MySQL 行数校验

```text
customers: 99441
geolocation: 1000163
orders: 99441
order_items: 112650
products: 32951
sellers: 3095
order_payments: 103886
order_reviews: 99224
product_category_name_translation: 71
mv_monthly_sales: 23
mv_state_sales: 556
mv_category_sales: 1273
mv_delivery_perf: 556
mv_seller_perf: 16068
mv_payment_dist: 378
mv_weekly_sales: 91
mv_state_geo: 27
mv_review_category_perf: 74
mv_review_topics: 455
mv_weight_freight: 10
```

## 6. 性能对比命令

性能对比脚本不负责截图，但会输出 SQL、耗时和加速倍数，便于报告截图：

```bash
python -m utils.perf_compare
```

本机一次运行结果如下：

| 对比项 | 基础表耗时(ms) | 预聚合耗时(ms) | 加速倍数 |
| --- | ---: | ---: | ---: |
| 月度 GMV | 284.59 | 1.34 | 212.03x |
| 州销售排行 | 464.05 | 8.87 | 52.31x |
| 配送延迟 | 233.41 | 1.29 | 181.11x |

正式报告截图时建议重新运行一次，以当时终端输出为准。
