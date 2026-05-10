# Agentic BI 电商运营分析系统 — 项目规划文档

> 课程：智能商务案例分析 | 小组：3人 | 数据集：Olist Brazilian E-Commerce

---

## 一、项目目标摘要

构建一个多智能体协作的 BI 分析系统，使非技术用户能通过**自然语言**提问，自动完成：

- 跨表 SQL 查询（优先命中预聚合视图）
- 四层分析（描述→诊断→预测→规范性）
- 自动生成 ≥6 种可视化图表
- 在 Web 界面中展示分析结论与决策建议

---

## 二、技术栈选型

| 层次 | 选型 | 理由 |
|------|------|------|
| LLM | DeepSeek API（`deepseek-chat`） | 免费额度充足、中文友好、Function Calling 完善 |
| Agent 框架 | LangGraph | 任务书明确推荐；支持有状态 StateGraph + MemorySaver |
| 数据库 | MySQL | 任务书明确要求；适合多表 JOIN、预聚合表、索引优化和性能对比演示 |
| 预测模型 | Prophet（主）| 时序预测首选，自带置信区间；无需 GPU |
| 可视化 | Plotly（图表）+ Folium（地图） | Plotly 输出 HTML 可直接嵌 Web；Folium 渲染巴西州热力图 |
| Web 后端 | FastAPI + WebSocket | 轻量；支持流式返回 Agent 中间过程 |
| Web 前端 | 原生 HTML/CSS/JS | 无需构建工具；双栏布局简单实现 |

> **MySQL 使用说明**：原始表与预聚合表统一驻留在 MySQL 中。系统通过 `utils/db_init.py` 完成建库、导入、索引创建与预聚合表刷新；DataAnalyst Agent 生成的 SQL 优先查询 `mv_*` 预聚合表，无法覆盖时再回退到基础表 JOIN。

---

## 三、目录结构

```
AgenticBI_Final_Olist/
├── data/
│   └── raw/                    # Olist 原始 9 张 CSV
├── agents/
│   ├── orchestrator.py         # 协调器 Agent
│   ├── data_analyst.py         # 数据分析 Agent（NL→SQL）
│   ├── visualizer.py           # 可视化 Agent
│   └── decision_maker.py       # 决策智能 Agent
├── utils/
│   ├── db_init.py              # 数据清洗 + 建库 + 预聚合视图创建
│   ├── schema.py               # 数据字典（表结构 + 视图说明，注入 Prompt）
│   └── query_router.py         # 视图命中判断 / 回退逻辑
├── sql/
│   ├── schema.sql              # MySQL 基础表结构、索引
│   └── materialized_views.sql  # 预聚合表创建与刷新 SQL
├── models/
│   └── forecast.py             # Prophet 时序预测封装
├── config/
│   ├── prompts.py              # 各 Agent 的 System Prompt 模板
│   └── views_desc.py           # 预聚合视图说明（给 Agent 看）
├── dashboard/
│   ├── index.html              # 双栏 Web 界面
│   └── static/                 # JS/CSS
├── app.py                      # FastAPI 入口
├── requirements.txt
└── README.md
```

---

## 四、Agent 设计

系统由 4 个 Agent 组成，通过 LangGraph StateGraph 编排。

### 4.1 协调器 Agent（Orchestrator）

**职责**：解析用户问题 → 判断分析类型 → 规划子任务序列 → 汇总最终输出

```
用户输入 → [Orchestrator]
              ├─ 描述性问题 → DataAnalyst → Visualizer → DecisionMaker
              ├─ 诊断性问题 → DataAnalyst（多次查询）→ DecisionMaker
              ├─ 预测性问题 → DataAnalyst → ForecastModel → Visualizer
              └─ 规范性问题 → 以上全部 → DecisionMaker
```

### 4.2 数据分析 Agent（DataAnalyst）

**职责**：自然语言 → SQL → 执行 → 返回结构化数据

**核心逻辑**：
1. Prompt 中注入所有预聚合视图的名称、粒度、字段
2. LLM 优先生成针对视图的 SQL
3. `query_router.py` 验证：若 SQL 引用的视图存在则直接执行；否则切换到基础表回退 SQL
4. 输出：DataFrame 摘要（前 20 行 + 统计信息）

### 4.3 可视化 Agent（Visualizer）

**职责**：根据数据类型自动选择图表 → 生成 Plotly/Folium HTML 片段

图表类型映射：
- 时序数据 → 折线图（含预测置信区间）
- 州维度数据 → 地理热力图（Folium + 巴西 GeoJSON）
- 类别对比 → 柱状图/条形图
- 交叉矩阵 → 热力图（payment × installments）
- 相关性 → 散点/气泡图（重量 vs 运费）
- 占比 → 饼图/环形图（支付方式）

### 4.4 决策智能 Agent（DecisionMaker）

**职责**：整合数据摘要 + 预测结果 → 调用 LLM 推理 → 输出可操作建议

Prompt 格式：
```
你是 Olist 平台的数据科学顾问，根据以下分析结果给出 3 条具体改进建议：
[分析数据摘要]
要求：每条建议包含 问题定位 / 根因 / 具体行动 / 预期效果
```

---

## 五、预聚合视图设计

在 MySQL 中维护以下 6 张预聚合表，并通过 `utils/db_init.py` 或 `sql/materialized_views.sql` 一键刷新：

| 视图名 | 粒度 | 主要用途 |
|--------|------|---------|
| `mv_monthly_sales` | 年-月 | GMV 趋势、环比增长 |
| `mv_state_sales` | 年-月-州 | 区域销售排名 |
| `mv_category_sales` | 年-月-品类 | 品类表现分析 |
| `mv_delivery_perf` | 年-月-州 | 准时率、延迟诊断 |
| `mv_seller_perf` | 年-月-卖家 | 卖家绩效、差评定位 |
| `mv_payment_dist` | 年-月-支付类型 | 支付偏好分析 |

创建方式（MySQL 用预聚合表保存结果，必要字段建立索引）：
```sql
-- 示例：mv_monthly_sales
DROP TABLE IF EXISTS mv_monthly_sales;
CREATE TABLE mv_monthly_sales AS
SELECT
    DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m') AS year_month,
    COUNT(DISTINCT o.order_id)                  AS total_orders,
    SUM(oi.price + oi.freight_value)            AS total_gmv,
    AVG(oi.price)                               AS avg_price,
    SUM(oi.freight_value)                       AS total_freight
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_status = 'delivered'
GROUP BY year_month;

CREATE INDEX idx_mv_monthly_sales_year_month
ON mv_monthly_sales (year_month);
```

Agent 在 Prompt 中获得每张视图的字段描述，匹配成功则直接 `SELECT * FROM mv_*`，无匹配时回退到基础表 JOIN。

---

## 六、四层分析覆盖

| 分析层 | 实现方式 | 示例问题 |
|--------|---------|---------|
| 描述性 | DataAnalyst 查视图 + 统计摘要 | "2017年各月GMV趋势？" |
| 诊断性 | 多次查询（视图 + 基础表下钻）+ 关联分析 | "哪些州配送延迟严重？" |
| 预测性 | Prophet 基于 `mv_monthly_sales` 建模，预测未来 6 周 | "预测未来6周销售额" |
| 规范性 | DecisionMaker 综合前三层 + LLM 推理 | "给出东北部降低退货率的方案" |

---

## 七、可视化清单（≥6种）

| 序号 | 图表类型 | 数据来源 |
|------|---------|---------|
| 1 | 时序折线图（含预测曲线+置信区间） | `mv_monthly_sales` + Prophet |
| 2 | 巴西州地理热力图 | `mv_state_sales` + GeoJSON |
| 3 | 各州客单价柱状图 | `mv_state_sales` |
| 4 | 支付方式×分期数热力矩阵 | `mv_payment_dist` |
| 5 | 重量 vs 运费气泡散点图 | 基础表（products + order_items） |
| 6 | 品类销售额 Top10 条形图 | `mv_category_sales` |
| 7 | 支付方式占比环形图 | `mv_payment_dist` |

---

## 八、Web 界面设计

双栏布局（参考任务书建议）：

```
┌─────────────────────────────────────────────────────┐
│  Header: Agentic BI — Olist 运营分析系统              │
├───────────────────────┬─────────────────────────────┤
│   左栏：对话区（40%） │  右栏：可视化区（60%）        │
│                       │                              │
│  [历史消息气泡]        │  [Plotly 图表嵌入]           │
│                       │  [决策建议卡片]               │
│  [输入框] [发送]       │  [图表切换 Tab]              │
└───────────────────────┴─────────────────────────────┘
```

- WebSocket 实时流式返回 Agent 中间步骤
- 支持多轮对话（LangGraph MemorySaver 维护上下文）
- 图表区 Tab 切换，不刷新页面

---

## 九、小组分工

> 3人小组，按模块划分，每人负责一个完整垂直切面。

### 成员 A — 数据工程 + Agent 框架（核心后端）

**负责模块**：`utils/` + `agents/` + `config/`

具体任务：
1. 数据清洗脚本（处理 9 张原始 CSV，处理缺失值、时间格式、类别翻译）
2. MySQL 建库 + 6 张预聚合表 SQL 编写、索引设计与验证
3. LangGraph StateGraph 搭建（4 个 Agent 节点 + 条件边 + MemorySaver）
4. 数据分析 Agent 实现（Prompt 设计、视图路由逻辑、SQL 执行）
5. 协调器 Agent 实现（问题分类、子任务规划）
6. 编写 `schema.py` 数据字典

预期工作量：**约 40%**

### 成员 B — 可视化 + 预测模型

**负责模块**：`models/` + `agents/visualizer.py` + 图表集成

具体任务：
1. Prophet 预测模型封装（输入历史序列，输出未来 6 周预测 + 置信区间）
2. 可视化 Agent 实现（7 种图表的 Plotly/Folium 代码）
3. 巴西 GeoJSON 数据获取与州热力图渲染
4. 图表 HTML 片段与 Web 界面的集成对接
5. 性能对比截图（预聚合视图 vs 基础表查询时间对比）

预期工作量：**约 35%**

### 成员 C — Web 界面 + 决策 Agent + 报告

**负责模块**：`dashboard/` + `agents/decision_maker.py` + `app.py` + 项目报告

具体任务：
1. FastAPI 后端入口（路由、WebSocket 流式接口）
2. 前端双栏界面（HTML/CSS/JS，对话气泡 + 图表 Tab 展示）
3. 决策智能 Agent 实现（Prompt 设计、建议格式化输出）
4. 系统整体联调测试（覆盖附录 10 个验证问题）
5. 撰写项目报告（架构图、技术选型说明、运行截图、性能对比）

预期工作量：**约 25%**

---

## 十、开发里程碑

| 周次 | 里程碑 | 验收标准 |
|------|--------|---------|
| 第1周 | 数据准备完成 | MySQL 建库成功，6张预聚合表可查询，索引生效，性能对比数据有记录 |
| 第2周 | Agent 框架跑通 | 4个Agent节点联通，能回答"2017年GMV是多少"（命中mv_monthly_sales） |
| 第3周 | 可视化 + 预测集成 | 7种图表正常渲染，Prophet预测输出置信区间 |
| 第4周 | Web界面 + 联调 | 多轮对话正常，附录10个问题全部可回答，报告初稿完成 |

---

## 十一、加分项规划（选做）

| 加分项 | 分值 | 实现思路 | 负责人 |
|--------|------|---------|--------|
| 情感分析融入决策建议 | +3 | 用 `transformers` 对 review_comment_message 做情感分类，结果注入 DecisionMaker Prompt | 成员 B |
| 多轮关联记忆模块 | +2 | LangGraph MemorySaver 已内置，需在 Prompt 中显式引用上轮分析结论 | 成员 A |

> What-if Agent 和本地开源LLM暂不列入计划（工作量风险较大）。

---

## 十二、关键风险与应对

| 风险 | 应对 |
|------|------|
| LLM 生成 SQL 语法错误 | 捕获异常 → 将报错信息回传 LLM 要求修正（最多3次重试） |
| Prophet 数据量不足（月粒度仅~25个点） | 补充周粒度数据；或改用 ARIMA |
| 地图热力图 GeoJSON 边界不准 | 使用 IBGE 官方巴西州 GeoJSON（CC-BY 授权） |
| DeepSeek API 限速 | 本地缓存常见问题的分析结果；控制并发请求数 |
