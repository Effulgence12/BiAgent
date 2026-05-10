# 项目骨架搭建说明

## 本次已完成

- 按 `plan.md` 的路线创建 Python Web 项目基础目录：`agents/`、`utils/`、`models/`、`config/`、`sql/`、`dashboard/`、`data/`。
- 新增 FastAPI 入口 `app.py`，提供：
  - `GET /`：双栏 Web 页面。
  - `GET /health`：健康检查。
  - `POST /api/analyze`：最小可运行 Agent 工作流。
  - `WebSocket /ws/analyze`：流式步骤占位。
- 新增 4 类 Agent 的最小确定性实现：
  - Orchestrator：问题分类与步骤规划。
  - DataAnalyst：基于关键词生成视图优先 SQL。
  - Visualizer：根据 SQL 目标选择图表类型。
  - DecisionMaker：输出建议模板。
- 新增 MySQL 基础表结构与 6 张 `mv_*` 预聚合表 SQL，后续可直接用于数据导入与性能对比。
- 新增 `requirements.txt`、`.env.example`、`.gitignore` 和数据目录说明，保证环境配置路径清晰。

## 本地运行方式

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

打开浏览器访问 <http://127.0.0.1:8000>，输入业务问题即可看到当前骨架返回的计划、SQL、路由与建议占位。

## 下一步计划

1. 数据层：下载 Olist 9 张 CSV 到 `data/raw/`，完善 `utils/db_init.py` 的 CSV 清洗与 MySQL 导入流程。
2. 查询层：接入 SQLAlchemy/PyMySQL，执行真实 SQL，并记录预聚合命中与基础表回退耗时。
3. Agent 层：用 LangGraph 替换当前确定性串联逻辑，接入 DeepSeek API 与 Prompt 模板。
4. 可视化层：用 Plotly/Folium 生成 7 类图表 HTML，并嵌入右侧结果区。
5. 预测层：基于 `mv_monthly_sales` 接入 Prophet；样本不足时增加周粒度或 ARIMA 备选。
6. 验证层：补充端到端测试、10 个任务书验证问题、性能对比截图和报告材料。
