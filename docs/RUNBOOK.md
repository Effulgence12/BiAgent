# 运行与验收手册

## 1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. 准备数据

项目启动时会校验 `data/raw/` 中的 9 张真实 Olist CSV。若任一文件缺失或为空，系统会尝试从公开 Olist CSV 镜像下载真实文件；下载失败或下载后仍缺失会直接报错，不会生成模拟数据。

也可以手动执行：

```bash
python cli.py --bootstrap "2017年各月GMV趋势？"
```

## 3. 启动 Web

```bash
uvicorn app:app --reload
```

访问 <http://127.0.0.1:8000>。

## 4. 建议验收问题

1. `2017年各月GMV趋势？`
2. `哪些州销售额最高？`
3. `哪些州配送延迟严重，原因是什么？`
4. `品类销售额Top10是什么？`
5. `支付方式和分期数分布如何？`
6. `卖家中哪些评分最低？`
7. `重量和运费是否相关？`
8. `预测未来6期GMV。`
9. `给出平台整体运营优化建议。`
10. `分析东北部降低延迟率的策略。`

也可以直接运行任务书附录 10 题验收：

```bash
python cli.py --validate-assignment
```

该命令会真实调用 Qwen 生成 SQL 任务，并报告每题的分析类型、命中视图、SQL 任务数、是否有直答、是否有图表、是否有预测。若模型不可用或 SQL 非法，会直接失败，不会用本地模板伪造结果。

泛化能力验收：

```bash
python cli.py --validate-general
```

该命令覆盖 34 个非附录问题，检查真实 SQL、命中视图、直答、摘要、图表和预测区间，通过率目标为 90%。

为了节省模型额度并定位失败题，也可以分批运行：

```bash
python cli.py --validate-general --general-offset 0 --general-limit 8 --validation-progress
python cli.py --validate-general --general-offset 8 --general-limit 8 --validation-progress
```

`--general-offset` 从 0 开始计数；如果远端模型偶发 HTTPS 断开，可从失败题附近继续跑。失败仍会真实返回非零退出码，不会使用本地模板伪造通过。

## 5. 浏览器截图级视觉验收

本项目提供 Playwright 视觉验收脚本，默认使用系统 Edge：

```bash
python tests/visual_acceptance.py
```

注意事项：

- 只需安装 Python `playwright` 包，不需要执行 `python -m playwright install` 下载浏览器。
- 脚本会启动本地 FastAPI 服务，用系统 Edge 打开页面，并真实调用 Qwen。
- 若当前模型额度耗尽，可按 `.env` 中 `QWEN_MODEL` 手动切换模型名；不要在代码中增加自动模型 fallback。
- 截图和报告输出到 `docs/screenshots/visual_acceptance/`。
- 默认覆盖 PC Web 桌面图表截图、GMV 趋势、州地图、支付热力图、预测和多轮追问。
- 如需额外检查窄屏布局，可运行 `python tests/visual_acceptance.py --include-mobile`。
- 如需减少模型额度消耗，可只重跑某个场景，例如 `python tests/visual_acceptance.py --scenario 02_delivery_map`。
- 当前 PC 答辩优先验收桌面视口。地图类问题会根据问题意图选择指标：销售分布走 `mv_state_geo` 销售气泡图；配送延迟/准时率问题会联动 `mv_delivery_perf` 生成红色延迟率地图或准时率地图；卖家评分风险会联动 `mv_seller_perf` 生成评分风险地图。若真实模型请求失败，页面会显示明确错误，不会退回固定销售地图伪装成功。

## 6. 启用 Qwen 流式建议

```bash
export ENABLE_LLM=1
export QWEN_API_KEY=你的key
export QWEN_MODEL=qwen3.5-plus-2026-04-20
uvicorn app:app --reload
```

WebSocket `/ws/analyze` 会先返回计划、SQL、摘要和图表，然后发送真实的 `llm_delta` 与 `llm_usage` 事件。若没有 key、key 无效或远程模型不可用，会发送 `llm_error` 并关闭连接，不返回本地建议。

## 7. 当前数据与数据库口径

- 当前阶段暂用 SQLite，本地库路径由 `.env` 的 `LOCAL_DB_PATH` 指定。
- SQLite 数据库必须由 `data/raw/` 下 9 张真实 Olist CSV 构建。
- 自动下载使用公开 Olist CSV 镜像；下载失败会报缺失 CSV 名称。
- MySQL 仍是最终迁移目标，`sql/schema.sql` 和 `sql/materialized_views.sql` 已维护对应表结构与预聚合脚本。

## 8. 已维护的预聚合表

`mv_monthly_sales`、`mv_state_sales`、`mv_category_sales`、`mv_delivery_perf`、`mv_seller_perf`、`mv_payment_dist`、`mv_weekly_sales`、`mv_state_geo`、`mv_review_category_perf`、`mv_weight_freight`。
