# 项目骨架与当前进展说明

## 本次已完成

- 按 `plan.md` 的路线创建并扩展 Python Web 项目基础目录：`agents/`、`utils/`、`models/`、`config/`、`sql/`、`dashboard/`、`data/`、`docs/`。
- 新增可运行 FastAPI 入口 `app.py`，提供：
  - `GET /`：双栏 Web 页面。
  - `GET /health`：健康检查。
  - `POST /api/bootstrap`：校验真实 CSV 并刷新本地预聚合表。
  - `POST /api/analyze`：多 Agent 分析工作流。
  - `WebSocket /ws/analyze`：流式步骤输出。
- 完成 4 类 Agent 的本地可运行实现：
  - Orchestrator：问题分类、计划生成、串联 Agent。
  - DataAnalyst：基于问题生成视图优先 SQL，执行查询并摘要。
  - Visualizer：根据查询类型生成 HTML/SVG 图表和结果表。
  - DecisionMaker：基于数据摘要输出可操作建议。
- 完成数据工程闭环：
  - 必须使用真实 Olist CSV。
  - CSV 缺失时尝试下载真实文件；下载失败时直接报错，不生成模拟数据。
  - 当前阶段使用本地 SQLite 查询真实 CSV，MySQL SQL 保留为后续生产/报告口径。
- 新增 MySQL 基础表结构与 6 张 `mv_*` 预聚合表 SQL，后续可直接用于数据导入与性能对比。
- 新增 `requirements.txt`、`.env.example`、`.gitignore`、CLI、API Key 文档和运行验收手册。

## 本地运行方式

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

打开浏览器访问 <http://127.0.0.1:8000>，输入业务问题即可看到计划、SQL、路由、图表、预测与建议。

也可使用命令行：

```bash
python cli.py --bootstrap "2017年各月GMV趋势？"
```

## 下一步计划

1. 将 DeepSeek 或 Qwen 调用接入 SQL 生成与建议输出；模型不可用时直接报错，不返回本地假建议。
2. 在真实 MySQL 环境中导入 CSV，执行 `sql/schema.sql` 与 `sql/materialized_views.sql`，补充性能对比截图。
3. 若依赖安装顺利，用 Plotly/Folium 替换当前 SVG 图表，并补充巴西州 GeoJSON 地图。
4. 用 Prophet 替换当前线性预测基线；样本不足时明确报出预测数据不足，或在报告中说明改用 ARIMA 的依据。
5. 根据任务书 10 个验收问题补充端到端截图、系统报告与小组分工说明。
