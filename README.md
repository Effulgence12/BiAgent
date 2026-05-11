# 智能商务案例分析 期末项目

同济大学 2026

## 项目目标

本项目面向 Brazilian E-Commerce Public Dataset by Olist，建设一个 Agentic BI 驱动的多表电商运营分析与决策智能系统。系统目标是让非技术用户通过自然语言获得可验证的数据查询、图表、预测和运营建议。

核心能力：

- 自然语言问题解析与多 Agent 协作编排。
- MySQL 生产 SQL 与本地 SQLite 一键演示双路径；Agent 查询优先命中 `mv_*` 预聚合表。
- 描述性、诊断性、预测性、规范性四层分析。
- Web 双栏界面：左侧对话，右侧 SQL、图表、建议与 JSON。
- 可选 Qwen/DashScope API Key；未配置 Key 时仍可使用本地确定性 Agent 完成演示。

## 当前实现状态

- `app.py`：FastAPI 入口，包含健康检查、数据初始化、同步分析接口与 WebSocket 流式接口。
- `agents/`：Orchestrator、DataAnalyst、Visualizer、DecisionMaker 的可运行实现。
- `utils/`：数据下载/模拟生成、本地分析库、数据字典与 SQL 路由判断。
- `sql/`：MySQL 基础表结构与 6 张预聚合表刷新 SQL。
- `dashboard/`：原生 HTML/CSS/JS 双栏交互页面。
- `docs/`：骨架说明、API Key 说明、运行与验收手册。

## 快速启动

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

启动后访问 <http://127.0.0.1:8000>。

首次提问时系统会自动准备数据：优先使用 `data/raw/` 的 Olist CSV；若缺失则尝试从公开 GitHub 镜像下载；若下载失败则生成 Olist-like 模拟数据，保证系统可运行。

## 命令行验收

```bash
python cli.py --bootstrap "2017年各月GMV趋势？"
python cli.py "哪些州配送延迟严重？"
python cli.py "预测未来6期GMV。"
```

## API Key

复制 `.env.example` 为 `.env` 后填入：

```bash
ENABLE_LLM=1
QWEN_API_KEY=你的key
QWEN_MODEL=qwen3.6-plus
```

默认一个 Qwen/DashScope Key 供所有 Agent 共享即可。详见 `docs/API_KEY.md`。

## 数据准备

真实 Olist CSV 文件应放入 `data/raw/`。原始 CSV、SQLite 本地库和生成产物已在 `.gitignore` 中排除，避免提交大文件。MySQL 建表与预聚合刷新 SQL 位于 `sql/schema.sql` 与 `sql/materialized_views.sql`。
