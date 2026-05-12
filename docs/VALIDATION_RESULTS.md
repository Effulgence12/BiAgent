# 附录验证问题阶段结果

最近一次使用真实 Qwen SQL 规划和真实 SQLite 数据库进行验收：2026-05-12。

```bash
python cli.py --validate-assignment
python cli.py --validate-general
```

## 覆盖情况

| 序号 | 验证问题 | 当前状态 |
| --- | --- | --- |
| 1 | 2017 年 GMV、月趋势、州排名 | 通过，命中 `mv_monthly_sales`、`mv_state_sales` |
| 2 | 平台准时交付率、延迟最严重州 | 通过，命中 `mv_delivery_perf` |
| 3 | 支付方式、平均分期数 | 通过，命中 `mv_payment_dist` |
| 4 | 重量/尺寸与运费关系 | 通过，命中 `mv_weight_freight` |
| 5 | Top10 差评品类与原因 | 通过，命中 `mv_review_category_perf` |
| 6 | 未来 6 周销售额预测 | 通过，命中 `mv_weekly_sales` 并返回预测区间 |
| 7 | 三个月三大优先改进策略 | 通过，综合销售、配送、支付、评价、卖家、商品等视图 |
| 8 | 2017 最高销售州、准时率、支付方式 | 通过，组合命中销售、配送、支付视图 |
| 9 | 高配送时长州与高差评卖家 | 通过，命中 `mv_delivery_perf`、`mv_seller_perf` |
| 10 | 东北部高退货/体验问题运营方案 | 通过，综合区域、配送、评价、卖家和商品视图 |

## 已确认样例

- 平台整体准时交付率：91.89%。
- 平台整体延迟率：8.11%。
- 延迟最严重州：AL、MA、PI、CE、SE。
- 2017 年销售额最高州：SP。
- 2017 年 SP 州 GMV：约 2,428,002.62。
- 2017 年 SP 州准时交付率：94.11%。
- 最受欢迎支付方式：credit_card。
- credit_card 平均分期数：约 3.0。
- 预测题基于 91 周真实 GMV 序列返回未来 6 周 `yhat/yhat_lower/yhat_upper`。

## 重要说明

这些问题不是业务逻辑里的写死分支。运行时由 Qwen 根据数据字典实时生成 SQL 任务，代码只做只读 SQL 校验、执行和通用字段识别。若模型不可用、SQL 非法或数据缺失，系统会明确报错。

## 泛化验收

2026-05-12 新增非附录泛化验收入口：

```bash
python cli.py --validate-general
```

本次真实模型验收结果：26/26 通过，覆盖时间范围变化、州/品类/支付组合、地图、配送诊断、卖家下钻、预测解释、规范建议和省略主语追问等问题。预测题均返回 `yhat/yhat_lower/yhat_upper`，并带 ETS 模型诊断信息。

新增验收会检查：

- 是否真实生成 SQL 任务。
- 是否命中合理 `mv_*` 视图或真实基础表。
- 是否有直答、摘要、图表。
- 预测题是否有预测区间。
- 通过率目标为 90%，失败会以非零退出码暴露。

## WebSocket 多轮流式验收

2026-05-12 使用同一个 `session_id=codex_ws_acceptance` 连续验证 5 类问题：

| 轮次 | 问题类型 | 结果 |
| --- | --- | --- |
| 1 | 描述性：2017 GMV 月趋势 | 通过，收到完整 Agent 事件、3 个图表、真实 `llm_delta` |
| 2 | 诊断性：配送延迟州 | 通过，收到完整 Agent 事件、8 个图表、真实 `llm_delta` |
| 3 | 预测性：未来 6 周销售额 | 通过，收到完整 Agent 事件、10 个图表、真实 `llm_delta` 和预测区间 |
| 4 | 规范性：三个月优先策略 | 通过，收到完整 Agent 事件、16 个图表、真实 `llm_delta` |
| 5 | 多轮追问：继续分析刚才高延迟州 | 通过，记忆轮数递增到 5，收到完整 Agent 事件、17 个图表、真实 `llm_delta` |

本次验收确认事件集包含：`session`、`memory`、`plan`、`sql_planned`、`query_done`、`chart_done`、`llm_delta`、`memory_updated`、`final`。

## 可靠性修复

- DataAnalyst 增加真实 SQL 错误修复重试：当 Qwen 首次生成 SQL 执行失败时，会把错误与原 SQL 发回 Qwen 修复，最多修复 2 次；修不好则返回明确 SQL 错误。
- DataAnalyst 增加只读 SQL 方言规整：将 `ORDER BY ... LIMIT ... UNION ALL ...` 这类 SQLite/MySQL 常见兼容问题改写为子查询包裹形式，不伪造结果。
- Web 前端失败卡片新增“重试原问题”和“复制错误”，重试会携带原问题、失败 request id 和错误上下文，不再把“重试”当作业务问题。
- Agent 面板展示结构化计划、SQL 任务、命中视图、预测模型诊断和错误详情。
- LLM 非流式请求增加有限重试，避免远端瞬时断连导致整体验收失败。
- LLM 流式请求在未输出任何 delta 前允许重试；已经开始输出后若中断，会保留真实错误，避免重复内容或假流式。
