# 智能商务案例分析 期末项目

同济大学 2026

## 项目目标

本项目面向 Brazilian E-Commerce Public Dataset by Olist，建设一个 Agentic BI 驱动的多表电商运营分析与决策智能系统。系统目标是让非技术用户通过自然语言获得可验证的数据查询、图表、预测和运营建议。

核心能力：

- 自然语言问题解析与多 Agent 协作编排。
- MySQL 正式查询引擎与 SQLite 本地兜底双路径；数据必须来自真实 Olist CSV，Agent 查询优先命中 `mv_*` 预聚合表。
- 描述性、诊断性、预测性、规范性四层分析。
- Web 双栏界面：左侧对话，右侧 SQL、图表、建议与 JSON。
- 必须配置可用 Qwen/DashScope API Key；模型不可用时接口返回明确错误，不生成本地假建议。

## 当前实现状态

- `app.py`：FastAPI 入口，包含健康检查、数据初始化、同步分析接口与 WebSocket 流式接口。
- `agents/`：LangGraph 编排的 Orchestrator、DataAnalyst、ForecastModel、Visualizer、DecisionMaker 可运行实现。
- `utils/`：真实 CSV 校验、MySQL/SQLite 分析库、数据清洗导入、数据字典与 SQL 路由判断。
- `sql/`：MySQL 基础表结构与 10 张预聚合表刷新 SQL（另有 1 张 Python 侧主题表 `mv_review_topics`，共 11 张预聚合表）。
- `dashboard/`：原生 HTML/CSS/JS 双栏交互页面。
- `docs/`：骨架说明、API Key 说明、运行与验收手册。

## 快速启动

在类 Unix（Linux/macOS）终端下，使用 venv：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

如果使用 conda 管理环境，推荐新建项目环境：

```bash
conda create -n <虚拟环境名> python=3.11
conda activate <虚拟环境名>
pip install -r requirements.txt
uvicorn app:app --reload
```

启动后访问 <http://127.0.0.1:8000>。

首次提问时系统会校验 `data/raw/` 的 9 张真实 Olist CSV；若缺失会尝试从公开 Olist CSV 镜像下载真实文件，下载失败或下载后仍缺失会直接报错，不会生成模拟数据。

## 命令行验收

```bash
python cli.py --bootstrap "2017年各月GMV趋势？"
python cli.py "哪些州配送延迟严重？"
python cli.py "预测未来6期GMV。"
python cli.py --validate-assignment
```

`--validate-assignment` 会逐题调用真实大模型规划 SQL，批量检查任务书附录 10 个问题，不会使用本地写死 SQL 兜底。

## API Key

复制 `.env.example` 为 `.env` 后填入：

```bash
ENABLE_LLM=1
QWEN_API_KEY=你的key
QWEN_MODEL=qwen3.6-plus
```

默认一个 Qwen/DashScope Key 供所有 Agent 共享即可。详见 `docs/API_KEY.md`。

## MySQL 数据准备

正式运行口径使用 MySQL。确认 `.env` 已配置 `MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_DATABASE`，并设置：

```bash
PREFER_MYSQL=1
```

首次全量清洗导入并刷新预聚合表：

```bash
python -m utils.db_init --mysql-bootstrap --force
```

后续刷新和行数校验：

```bash
python -m utils.db_init --mysql-bootstrap
python -m utils.db_init --counts
```

性能对比数据：

```bash
python -m utils.perf_compare
```

## SQLite 数据准备(备用兜底)

真实 Olist CSV 文件应放入 `data/raw/`。原始 CSV、SQLite 本地库和生成产物已在 `.gitignore` 中排除，避免提交大文件。SQLite 本地库由真实 CSV 重建；MySQL 建表与预聚合刷新 SQL 位于 `sql/schema.sql` 与 `sql/materialized_views.sql`。

如需不用 MySQL 的本地兜底演示，可设置：

```bash
PREFER_MYSQL=0
```

SQLite 本地库会由真实 CSV 重建，表结构和预聚合字段尽量与 MySQL 保持一致。
