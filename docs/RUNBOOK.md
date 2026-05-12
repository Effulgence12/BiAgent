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

## 5. 启用 Qwen 流式建议

```bash
export ENABLE_LLM=1
export QWEN_API_KEY=你的key
export QWEN_MODEL=qwen3.6-plus
uvicorn app:app --reload
```

WebSocket `/ws/analyze` 会先返回计划、SQL、摘要和图表，然后发送真实的 `llm_delta` 与 `llm_usage` 事件。若没有 key、key 无效或远程模型不可用，会发送 `llm_error` 并关闭连接，不返回本地建议。

## 6. 当前数据与数据库口径

- 当前阶段暂用 SQLite，本地库路径由 `.env` 的 `LOCAL_DB_PATH` 指定。
- SQLite 数据库必须由 `data/raw/` 下 9 张真实 Olist CSV 构建。
- 自动下载使用公开 Olist CSV 镜像；下载失败会报缺失 CSV 名称。
- MySQL 仍是最终迁移目标，`sql/schema.sql` 和 `sql/materialized_views.sql` 已维护对应表结构与预聚合脚本。

## 7. 已维护的预聚合表

`mv_monthly_sales`、`mv_state_sales`、`mv_category_sales`、`mv_delivery_perf`、`mv_seller_perf`、`mv_payment_dist`、`mv_weekly_sales`、`mv_state_geo`、`mv_review_category_perf`、`mv_weight_freight`。
