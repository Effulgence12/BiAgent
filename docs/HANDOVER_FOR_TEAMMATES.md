# Agentic BI Olist 项目接手手册

> 面向接手后续收尾工作的两名组员。  
> 当前项目目录：`E:\code\business\final`  
> 推荐环境：`conda activate bussiness_final`

## 1. 项目目标

本项目是“智能商务案例分析”期末项目，题目为：

**Agentic BI 驱动的多表电商运营分析与决策智能系统**

项目基于 Olist Brazilian E-Commerce 真实多表数据集，目标是让非技术业务用户通过自然语言提问，自动获得：

- 可验证的 SQL 查询结果；
- 多维统计分析；
- 可视化图表；
- 未来 6 周销售预测；
- 可执行的电商运营建议。

系统不是普通静态看板，而是一个多 Agent 协作的 Agentic BI 系统。

## 2. 当前项目状态

### 2.1 已完成内容

当前代码主体已经基本可演示：

- 已有 FastAPI Web 服务入口：`app.py`
- 已有双栏前端页面：`dashboard/`
- 已有多 Agent 模块：`agents/`
  - `orchestrator.py`：协调器 Agent
  - `data_analyst.py`：数据分析 Agent，负责自然语言转 SQL
  - `visualizer.py`：可视化 Agent
  - `decision_maker.py`：决策建议 Agent
- 已有预测模块：`models/forecast.py`
- 已有真实 Olist CSV 数据：`data/raw/`
- 已有 SQLite 本地分析库：`data/local/agentic_bi_olist.sqlite`
- 已有 MySQL 建表脚本：`sql/schema.sql`
- 已有 MySQL 预聚合表脚本：`sql/materialized_views.sql`
- 已维护 10 张预聚合表，超过任务书最低 4 张要求。

### 2.2 当前本地验证结果

在 `bussiness_final` 环境中，当前测试通过：

```bash
conda activate bussiness_final
python -m pytest -q tests -p no:cacheprovider
```

最近一次检查结果：

```text
33 passed
```

本地数据表状态也正常：

```bash
python -c "from utils.local_store import ensure_local_store, table_counts; print(ensure_local_store()); print(table_counts())"
```

已确认存在：

- 9 张 Olist 基础表；
- 10 张 `mv_*` 预聚合表；
- 91 周销售预测输入序列；
- 州级地图、评论、重量运费等扩展分析表。

## 3. 仍需完成的关键工作

当前项目最大问题不是代码主链路，而是**最终交付材料还不完整**。

后续重点如下：

1. 补齐预聚合视图性能对比截图。
2. 整理正式项目报告，而不是只保留草稿。
3. 重新跑一次任务书附录 10 题验收，并保存结果。
4. 整理 Web 演示截图和图表截图。
5. 明确 MySQL 与 SQLite 的交付口径。
6. 检查当前未提交代码改动，确认最终提交范围。

## 4. 环境启动方式

不要新建虚拟环境，直接使用当前 conda 环境：

```bash
conda activate bussiness_final
```

启动 Web：

```bash
uvicorn app:app --reload
```

浏览器访问：

```text
http://127.0.0.1:8000
```

如果要运行命令行分析：

```bash
python cli.py "2017年各月GMV趋势？"
python cli.py "哪些州配送延迟严重？"
python cli.py "预测未来6周GMV。"
```

如果要跑任务书附录 10 题验收：

```bash
python cli.py --validate-assignment
```

注意：该命令会真实调用 Qwen/DashScope 大模型，需要 `.env` 中配置可用 API Key。

## 5. 两名组员任务拆分

下面的分工按“互相独立、可并行、工作量尽量均分”的原则拆分。

## 6. 组员 A：数据层、SQL、性能对比、技术验证

### 6.1 任务边界

组员 A 负责数据和技术证据部分。

负责范围：

- `data/`
- `sql/`
- `utils/local_store.py`
- `utils/db_init.py`
- `config/views_desc.py`
- 报告中的数据层、预聚合层、性能优化章节

不负责：

- 前端页面美化；
- Web 截图排版；
- 决策建议文案；
- 最终报告整体整合。

除非发现 SQL 字段或预聚合表错误，否则不要改 Agent 主流程。

### 6.2 具体要做的工作

#### 任务 A1：确认真实数据完整

检查 `data/raw/` 下是否有 9 张 Olist CSV：

```bash
dir data\raw
```

应包含：

- `olist_customers_dataset.csv`
- `olist_geolocation_dataset.csv`
- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_payments_dataset.csv`
- `olist_order_reviews_dataset.csv`
- `olist_products_dataset.csv`
- `olist_sellers_dataset.csv`
- `product_category_name_translation.csv`

验收标准：

- 9 张文件都存在；
- 文件大小不是 0；
- 不使用模拟数据。

#### 任务 A2：确认本地 SQLite 库和预聚合表

运行：

```bash
python -c "from utils.local_store import ensure_local_store, table_counts; print(ensure_local_store()); print(table_counts())"
```

重点确认这些表存在：

- `mv_monthly_sales`
- `mv_state_sales`
- `mv_category_sales`
- `mv_delivery_perf`
- `mv_seller_perf`
- `mv_payment_dist`
- `mv_weekly_sales`
- `mv_state_geo`
- `mv_review_category_perf`
- `mv_weight_freight`

验收标准：

- 所有 `mv_*` 表 row count 大于 0；
- 至少任务书要求的前 6 张视图能正常查询。

#### 任务 A3：整理预聚合视图说明表

把下面内容整理进最终报告：

| 视图名 | 粒度 | 主要用途 |
| --- | --- | --- |
| `mv_monthly_sales` | 年月 | GMV 趋势、订单量、客单价 |
| `mv_state_sales` | 年月 + 州 | 州销售排行、区域市场对比 |
| `mv_category_sales` | 年月 + 品类 | 品类销售表现 |
| `mv_delivery_perf` | 年月 + 州 | 配送时长、延迟率、准时率 |
| `mv_seller_perf` | 年月 + 卖家 | 卖家绩效、评分、风险定位 |
| `mv_payment_dist` | 年月 + 支付方式 + 分期数 | 支付偏好、分期分布 |
| `mv_weekly_sales` | 周 | 未来 6 周销售预测 |
| `mv_state_geo` | 州 | 地图可视化 |
| `mv_review_category_perf` | 品类 | 差评率和差评原因 |
| `mv_weight_freight` | 重量区间 + 配送状态 | 重量、体积与运费关系 |

#### 任务 A4：制作性能对比材料

这是任务书明确要求，优先级最高。

需要做至少一组“使用预聚合表前后”的查询耗时对比。建议做 3 组，报告里至少放 1 组截图。

建议对比 1：月度 GMV

基础表 JOIN 查询：

```sql
SELECT
  substr(o.order_purchase_timestamp, 1, 7) AS year_month,
  COUNT(DISTINCT o.order_id) AS total_orders,
  SUM(oi.price + oi.freight_value) AS total_gmv
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_status = 'delivered'
GROUP BY year_month
ORDER BY year_month;
```

预聚合表查询：

```sql
SELECT
  year_month,
  total_orders,
  total_gmv
FROM mv_monthly_sales
ORDER BY year_month;
```

建议对比 2：州销售排行

基础表 JOIN 查询：

```sql
SELECT
  c.customer_state,
  COUNT(DISTINCT o.order_id) AS total_orders,
  SUM(oi.price + oi.freight_value) AS total_gmv
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_status = 'delivered'
GROUP BY c.customer_state
ORDER BY total_gmv DESC;
```

预聚合表查询：

```sql
SELECT
  customer_state,
  SUM(total_orders) AS total_orders,
  SUM(total_gmv) AS total_gmv
FROM mv_state_sales
GROUP BY customer_state
ORDER BY total_gmv DESC;
```

建议对比 3：配送延迟

基础表 JOIN 查询：

```sql
SELECT
  c.customer_state,
  COUNT(DISTINCT o.order_id) AS total_orders,
  AVG(julianday(o.order_delivered_customer_date) - julianday(o.order_purchase_timestamp)) AS avg_delivery_days,
  SUM(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 ELSE 0 END) AS late_orders
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
GROUP BY c.customer_state
ORDER BY late_orders DESC;
```

预聚合表查询：

```sql
SELECT
  customer_state,
  SUM(total_orders) AS total_orders,
  AVG(avg_delivery_days) AS avg_delivery_days,
  SUM(late_orders) AS late_orders
FROM mv_delivery_perf
GROUP BY customer_state
ORDER BY late_orders DESC;
```

建议输出格式：

| 查询问题 | 基础表耗时 | 预聚合表耗时 | 加速效果 |
| --- | ---: | ---: | ---: |
| 月度 GMV | xx ms | xx ms | x.x 倍 |
| 州销售排行 | xx ms | xx ms | x.x 倍 |
| 配送延迟 | xx ms | xx ms | x.x 倍 |

截图要求：

- 截图里要能看到 SQL；
- 要能看到耗时；
- 要能看出预聚合表明显更快；
- 放入最终报告的“预聚合性能优化”章节。

#### 任务 A5：确认 MySQL 可迁移口径

项目当前运行时主要使用 SQLite，但任务书要求 MySQL。

如果有 MySQL 环境，执行：

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p agentic_bi_olist < sql/schema.sql
mysql -h 127.0.0.1 -P 3306 -u root -p agentic_bi_olist < sql/materialized_views.sql
```

然后至少验证：

```sql
SELECT COUNT(*) FROM mv_monthly_sales;
SELECT COUNT(*) FROM mv_state_sales;
SELECT COUNT(*) FROM mv_delivery_perf;
SELECT COUNT(*) FROM mv_payment_dist;
```

如果没有 MySQL 环境，报告中要明确说明：

> 当前项目演示环境使用 SQLite 本地分析库，所有数据来自真实 Olist CSV；同时提供 MySQL 建表与预聚合刷新脚本，表名、字段和预聚合层保持 MySQL 可迁移。

### 6.3 组员 A 最终交付物

组员 A 需要交给组员 B：

- 预聚合视图说明表；
- 性能对比截图；
- 性能对比数据表；
- MySQL/SQLite 运行口径说明；
- 报告中的“数据预处理”“预聚合视图”“性能优化”“查询策略”章节文字。

## 7. 组员 B：Web 演示、可视化截图、业务分析、最终报告

### 7.1 任务边界

组员 B 负责展示和最终交付材料。

负责范围：

- `dashboard/`
- `docs/`
- `tests/visual_acceptance.py`
- Web 演示截图
- 图表截图
- 业务解读
- 最终报告整合

不负责：

- 数据库建表；
- 预聚合 SQL；
- 性能 SQL 对比；
- 数据导入逻辑。

不要随意修改 `sql/` 和 `utils/local_store.py`，避免和组员 A 冲突。

### 7.2 具体要做的工作

#### 任务 B1：启动 Web 并确认页面可用

运行：

```bash
conda activate bussiness_final
uvicorn app:app --reload
```

打开：

```text
http://127.0.0.1:8000
```

验收标准：

- 页面能打开；
- 左侧能输入问题；
- 右侧能显示 SQL、图表、建议或 JSON；
- 模型失败时页面显示明确错误，而不是假结果。

#### 任务 B2：准备演示问题

建议使用以下 6 个问题作为最终演示问题：

```text
2017年GMV是多少？按月和各州排名的趋势怎样？
```

```text
平台整体准时交付率是多少？哪些州延迟最严重？
```

```text
哪种支付方式最受欢迎？平均分期数是多少？
```

```text
产品重量、尺寸与运费之间有什么关系？
```

```text
根据历史订单趋势，预测未来6周的销售额，并给出趋势解读。
```

```text
基于全部分析结果，给出平台3个月内的三大优先改进策略。
```

验收标准：

- 每个问题至少有直接回答；
- 至少 4 个问题有图表；
- 预测问题必须有未来 6 周预测值和置信区间；
- 策略问题必须有具体运营建议。

#### 任务 B3：整理 6 类图表截图

任务书要求不少于 6 种图表。建议截图以下图表：

| 图表类型 | 对应内容 |
| --- | --- |
| 折线图 | 月度 GMV 趋势 |
| 预测折线图 | 未来 6 周 GMV + 置信区间 |
| 地图/气泡图 | 巴西州级销售或延迟地图 |
| 柱状图 | 州销售排行、品类 Top10、支付方式排行 |
| 热力图 | 支付方式 × 分期数 |
| 散点/气泡图 | 产品重量/体积与运费关系 |

已有截图目录：

```text
docs/screenshots/visual_acceptance/
```

注意筛选，不要把失败截图放进最终报告，文件名中带 `failed` 的截图一般不要用于报告正文。

#### 任务 B4：运行视觉验收脚本

完整运行：

```bash
python tests/visual_acceptance.py
```

如果模型额度紧张，可以分场景运行：

```bash
python tests/visual_acceptance.py --scenario 02_delivery_map
python tests/visual_acceptance.py --scenario 03_payment_heatmap
```

如果要检查移动端：

```bash
python tests/visual_acceptance.py --include-mobile
```

验收标准：

- 生成截图；
- 页面图表不空白；
- 图表区域和文字不严重重叠；
- 能看到真实建议输出。

#### 任务 B5：补正式报告

当前报告草稿在：

```text
docs/REPORT_DRAFT.md
```

需要扩展成正式报告，建议结构如下：

```text
1. 项目背景与目标
2. 数据集说明与预处理
3. 系统架构设计
4. 多 Agent 协作流程
5. 预聚合视图设计
6. Agent 查询命中策略与回退机制
7. 四层分析能力
   7.1 描述性分析
   7.2 诊断性分析
   7.3 预测性分析
   7.4 规范性/决策智能分析
8. 可视化与 Web 交互
9. 性能优化对比
10. 运行结果截图
11. 技术挑战与解决方案
12. 小组分工与贡献比例
```

### 7.3 组员 B 最终交付物

组员 B 需要最终产出：

- 正式项目报告；
- Web 页面截图；
- 6 类图表截图；
- 演示问题清单；
- 答辩演示流程；
- 小组分工表。

## 8. 推荐最终报告分工比例

如果现在由三人共同收尾，建议分工比例写成：

| 成员 | 负责内容 | 建议比例 |
| --- | --- | ---: |
| 原主要开发者 | Agent 主链路、后端接口、LLM SQL 规划、核心代码 | 40% |
| 组员 A | 数据验证、预聚合 SQL、性能对比、MySQL/SQLite 说明 | 30% |
| 组员 B | Web 演示、可视化截图、业务解读、最终报告整合 | 30% |

如果实际贡献不同，可以按真实情况调整。

## 9. 交付前总检查清单

最终提交前按下面清单逐项确认。

### 9.1 代码检查

```bash
conda activate bussiness_final
python -m pytest -q tests -p no:cacheprovider
```

要求：

```text
33 passed
```

### 9.2 数据检查

```bash
python -c "from utils.local_store import table_counts; print(table_counts())"
```

要求：

- 9 张基础表存在；
- 10 张 `mv_*` 表存在；
- 核心视图行数不为 0。

### 9.3 附录问题验收

```bash
python cli.py --validate-assignment
```

要求：

- 10 个任务书附录问题通过；
- 有命中 `mv_*` 的记录；
- 预测题有 `yhat/yhat_lower/yhat_upper`。

### 9.4 Web 检查

```bash
uvicorn app:app --reload
```

访问：

```text
http://127.0.0.1:8000
```

要求：

- 页面可打开；
- 问答可运行；
- 图表可显示；
- 建议可输出；
- 错误时明确报错。

### 9.5 报告检查

报告必须包含：

- 项目背景；
- 架构图；
- 多 Agent 流程；
- 数据预处理；
- 预聚合视图 SQL 或核心定义；
- Agent 命中预聚合视图策略；
- 回退基础表机制；
- 性能对比截图；
- 至少 6 类图表截图；
- 预测结果；
- 决策建议；
- 小组分工比例。

## 10. 当前风险提醒

### 风险 1：Qwen 模型额度

`.env.example` 默认是：

```text
QWEN_MODEL=qwen3.6-plus
```

但文档里记录过 `qwen3.6-plus` 额度可能耗尽。如果验收失败，先检查 `.env` 中的模型名和 Key。

### 风险 2：当前运行时不是 MySQL

任务书要求 MySQL，但当前项目实际演示主要走 SQLite。

处理方式：

- 能跑 MySQL 就尽量跑；
- 如果不跑，报告里必须明确说明 SQLite 是本地演示引擎，MySQL 脚本已提供，保持可迁移。

### 风险 3：报告还不够正式

`docs/REPORT_DRAFT.md` 目前只是草稿，不能直接当最终报告交。

必须补：

- 截图；
- 性能对比；
- SQL 定义；
- 分工比例；
- 演示结果解释。

### 风险 4：工作区有未提交改动

当前项目存在多处未提交修改和新增文件。最终提交前需要统一确认：

```bash
git status --short
```

不要随意丢弃已有修改。

## 11. 最短收尾路线

如果时间很紧，按这个顺序做：

1. 组员 A 做 1 组性能对比截图。
2. 组员 B 跑 Web，截 6 类图表。
3. 有 Key 的人跑 `python cli.py --validate-assignment`。
4. 把结果写进正式报告。
5. 检查 `pytest` 是否通过。
6. 统一整理提交。

最低交付目标：

- 代码能跑；
- 10 题能验收；
- 报告有性能截图；
- 报告有 6 类图表；
- 说明 SQLite/MySQL 口径；
- 小组分工清楚。

