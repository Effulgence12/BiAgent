# 智能商务案例分析 期末项目

同济大学 2026

## 项目目标

本项目面向 Brazilian E-Commerce Public Dataset by Olist，建设一个 Agentic BI 驱动的多表电商运营分析与决策智能系统。系统目标是让非技术用户通过自然语言获得可验证的数据查询、图表、预测和运营建议。

核心能力规划：

- 自然语言问题解析与多 Agent 协作编排。
- MySQL 多表查询与 `mv_*` 预聚合表优先命中。
- 描述性、诊断性、预测性、规范性四层分析。
- Plotly/Folium 可视化与 FastAPI Web 双栏界面。
- DeepSeek API / LangGraph / Prophet 的后续集成。

## 当前骨架状态

当前仓库已具备最小可运行项目骨架：

- `app.py`：FastAPI 入口，包含健康检查、同步分析接口与 WebSocket 流式占位。
- `agents/`：Orchestrator、DataAnalyst、Visualizer、DecisionMaker 的确定性最小实现。
- `utils/`：数据字典、预聚合视图说明与 SQL 路由判断。
- `sql/`：MySQL 基础表结构与 6 张预聚合表刷新 SQL。
- `dashboard/`：原生 HTML/CSS/JS 双栏调试页面。
- `docs/skeleton.md`：本次骨架搭建说明与下一步计划。

## 快速启动

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

启动后访问 <http://127.0.0.1:8000>，输入 Olist 业务问题即可查看当前骨架返回的分析类型、执行步骤、视图优先 SQL、图表类型和建议占位。

## 数据准备

请将 Olist 原始 CSV 文件放入 `data/raw/`。原始 CSV 已在 `.gitignore` 中排除，避免提交大文件。MySQL 建表与预聚合刷新 SQL 位于 `sql/schema.sql` 与 `sql/materialized_views.sql`。
