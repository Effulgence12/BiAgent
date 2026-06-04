# 附录验证问题阶段结果

最近一次使用真实 Qwen SQL 规划和真实 SQLite 数据库进行验收：2026-05-12。

```bash
python cli.py --validate-assignment
python cli.py --validate-general
```

## 2026-05-14 多 Agent 决策链路升级

- Orchestrator 已升级为真实 Qwen 结构化 Planner：每次分析先生成 `analysis_type`、`metrics`、`dimensions`、`required_agents`、`required_views`、`chart_requirements`、`confidence` 和 `reasoning_summary`，前端 Agent 面板和 CLI 均会展示这些字段。
- DataAnalyst 会把 Planner 输出写入 SQL 规划 prompt，并优先按 `required_views` 与 `chart_requirements` 补齐必要证据；关键词规则仅保留为安全校验和必需证据 guardrail。
- Visualizer 会读取 Planner 的图表指标，例如 `delivery_late_rate`、`delivery_on_time_rate`、`seller_review_risk`，再结合结果字段渲染对应 Folium 地图。
- 真实单题验收：`python cli.py "请用地图找出物流风险热区，不要只看销售额。" --no-recommendations` 已通过。Planner 输出 `diagnostic`、`late_rate`、`mv_delivery_perf + mv_state_geo`，最终 SQL 命中 `mv_state_geo` 和 `mv_delivery_perf`，直答返回平台准时率 91.89%、延迟率 8.11%，并列出 AL、MA、PI、CE、SE 等物流风险较高州。
- 单元测试新增 Planner JSON 解析、Planner 失败报错、非关键词地图指标补充、Planner 指标驱动准时率地图等场景；当前 `python -m pytest -q tests -p no:cacheprovider` 为 27/27 通过。

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

这些问题不是业务逻辑里的写死分支。运行时由 Qwen 根据数据字典实时生成 SQL 任务，并由 Qwen 解读真实查询结果生成业务直答；代码只做只读 SQL 校验、执行、确定性证据视图取数（地图经纬度、预测周序列等）和通用字段识别。若模型不可用、SQL 非法或数据缺失，系统会明确报错。

## 2026-06-04 直答合成 Agent 化

- DataAnalyst 由"只生成 SQL"升级为"生成 SQL + 解读结果"的真正分析 Agent：执行完查询后，由 Qwen 依据真实结果摘要合成 1–2 句业务直答（`synthesize_direct_answer`），取代了过去约 285 行按字段别名猜测拼装答案的 `build_direct_answer_from_results` 写死分支。
- 大模型直答不可用时退回确定性兜底（`_fallback_direct_answer`），只陈述真实返回的数据规模与首行关键字段，不编造结论，保证 `has_direct_answer` 验收稳定。
- `SUPPLEMENTAL_TASKS` 证据视图模板（地图/预测/各维度 `mv_*` 取数）作为合理的少量确定性逻辑保留，仅负责机械取数与可视化证据补充，不参与答案文本生成。
- 离线单元验收：`python -m pytest -q tests/test_skeleton.py` 全部 32 项通过（新增 `synthesize_direct_answer` 接地上下文与确定性兜底两项测试，移除 3 项过时的写死直答断言）。

## 2026-06-04 负面评论 NMF 主题建模（加分项）

- 新增 `utils/review_topics.py`：对 `review_score<=2` 的葡语评论做 TF-IDF + NMF 无监督主题建模（scikit-learn 1.5.2），按品类聚合落地为 `mv_review_topics`，已注册进数据字典供 LLM 规划命中。
- 解决 `mv_review_category_perf` 关键词分类把超 70% 差评归入"其他"的问题：NMF 揭示真实根因为"付款后未收到货/漏发"（`comprei dois · recebi apenas`）与"下单后物流拖延"（`compra · pedido · dia`）等。
- 真实单题验收：`python cli.py "Top10差评品类及其主要差评原因是什么？"`，Planner 自动关联 `mv_review_topics`（treemap + `topic_share`），直答与 DecisionMaker 三条建议均围绕 NMF 主题给出履约漏发、物流提速的具体动作，完成"NLP 分析→决策建议"闭环。
- 性能：模型在 ETL/刷新阶段本地训练（秒级，无预训练模型下载），运行时只查预聚合结果，零额外负担。
- 离线单元验收：`python -m pytest -q tests/test_skeleton.py` 全部 34 项通过（新增 NMF 主题表填充与稀疏样本兜底两项测试）。

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

## 浏览器截图级视觉验收

2026-05-13 使用 Python Playwright + 系统 Edge 完成截图级验收：

```bash
python tests/visual_acceptance.py
```

验收结果：通过。截图与 JSON 报告已输出到 `docs/screenshots/visual_acceptance/`。

覆盖场景：

- 桌面视口 `1440x900`：GMV 趋势、州级地图、支付分期热力图、未来 6 周预测、多轮追问。
- 窄屏视口 `390x844`：可选检查项，当前答辩以 PC Web 为主，后续默认不消耗模型额度跑移动端。
- 每题检查图表区域、证据数据表、真实流式建议、Agent 事件和直接结论。

本次验收还修复了两个问题：

- 独立新问题不再默认注入历史上下文，避免上一轮问题污染当前 SQL 和直答；只有追问或失败重试才携带上下文。
- Folium 地图改为 `iframe srcdoc` 渲染，并显式设置地图高度，避免普通浏览器中出现 notebook 占位提示或空白地图。

2026-05-14 针对地图智能化补充验证：

- `地图中显示延迟配送最严重的州` 已生成 `各州配送延迟地图`，图表类型为 `folium_map_delivery_late`，来源为 `mv_state_geo + mv_delivery_perf`，截图为 `docs/screenshots/visual_acceptance/desktop_02_delivery_map_chart.png`。
- 地图指标不再固定为销售额：配送延迟问题使用延迟率颜色和延迟订单气泡，准时率问题使用准时率颜色，卖家评分问题使用评分风险颜色，销售问题仍保留销售气泡图。
- 2026-05-14 全量 PC 视觉验收前 4 个场景已生成截图；第 5 个多轮追问遇到真实模型服务 `SSL UNEXPECTED_EOF`，系统按要求明确报错，未用本地降级结果伪装通过。脚本已支持 `--scenario` 单场景重跑以减少后续模型额度消耗。

模型额度说明：原 `qwen3.6-plus` 返回免费额度耗尽后，已按人工测试策略将 `.env` 的 `QWEN_MODEL` 手动切换为 `qwen3.5-plus-2026-04-20`，未加入代码级自动 fallback。

## 可靠性修复

- DataAnalyst 增加真实 SQL 错误修复重试：当 Qwen 首次生成 SQL 执行失败时，会把错误与原 SQL 发回 Qwen 修复，最多修复 2 次；修不好则返回明确 SQL 错误。
- DataAnalyst 增加只读 SQL 方言规整：将 `ORDER BY ... LIMIT ... UNION ALL ...` 这类 SQLite/MySQL 常见兼容问题改写为子查询包裹形式，不伪造结果。
- Web 前端失败卡片新增“重试原问题”和“复制错误”，重试会携带原问题、失败 request id 和错误上下文，不再把“重试”当作业务问题。
- Agent 面板展示结构化计划、SQL 任务、命中视图、预测模型诊断和错误详情。
- LLM 非流式请求增加有限重试，避免远端瞬时断连导致整体验收失败。
- LLM 流式请求在未输出任何 delta 前允许重试；已经开始输出后若中断，会保留真实错误，避免重复内容或假流式。

## 2026-05-15 决策链路与泛化复验

- Orchestrator 已升级为真实 Qwen 结构化 Planner，输出 `analysis_type`、`intent`、`metrics`、`dimensions`、`required_agents`、`required_views`、`chart_requirements`、`confidence` 和 `reasoning_summary`。关键词逻辑仅作为安全校验与证据补充，不再作为主决策来源。
- DataAnalyst 会接收 Planner 计划生成 SQL；若模型把多条只读 SQL 放进同一个任务，会拆分为多条 QueryTask 后逐条校验，仍禁止危险 SQL。
- 新增 SQLite 方言护栏：`PERCENTILE_CONT ... WITHIN GROUP` 会被规整为 `ORDER BY + LIMIT/OFFSET` 近似分位数查询；提示词也明确禁止非 SQLite 语法。
- ForecastModel 会从所有 SQL 结果中优先选择有真实 `week_start,total_gmv` 数据的周度序列，避免空结果抢占预测输入。
- 直答与主 SQL 证据按问题焦点选择：支付、评价、卖家、重量、品类、预测、配送地图分别优先展示对应结果，减少补充地图或月度销售证据污染当前回答。
- 真实附录验收：`python cli.py --validate-assignment`，10/10 通过。
- 真实泛化验收：34 个非附录问题已分批通过，覆盖同义表达地图、预测解释、配送诊断、卖家风险、低分反馈归因和省略主语追问。中途两次遇到服务商 HTTPS EOF，系统明确报错；重跑对应分片后通过。
- PC 视觉验收补跑通过：
  - `python tests/visual_acceptance.py --scenario 02_delivery_map`
  - `python tests/visual_acceptance.py --scenario 03_payment_heatmap`
  两个场景均确认图表按钮、证据数据表、直接结论和真实建议输出存在。
