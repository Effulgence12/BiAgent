# AGENT.md

本项目是面向 Olist 电商数据集的 Agentic BI 期末项目。所有开发都应服务于一个目标：让非技术用户通过自然语言获得可验证的数据查询、图表、预测和运营建议。

## 核心任务

- 实现完整可运行的 Python Web 项目，而不只是原型脚本。
- 覆盖 4 类分析：描述性、诊断性、预测性、规范性。
- 至少提供 4 个必需预聚合视图，当前维护 10 个：`mv_monthly_sales`、`mv_state_sales`、`mv_category_sales`、`mv_delivery_perf`、`mv_seller_perf`、`mv_payment_dist`、`mv_weekly_sales`、`mv_state_geo`、`mv_review_category_perf`、`mv_weight_freight`。
- 至少展示 6 种可视化，并在 Web 页面中整合对话、图表和决策建议。
- 报告中必须体现预聚合视图的 SQL、Agent 命中策略、回退机制和性能对比截图。

## 技术路线判断

- `plan.md` 的 LangGraph + MySQL + FastAPI + 预测/可视化路线合理，符合任务书对多 Agent、预聚合查询、流式交互、预测和可视化的要求。
- 当前阶段因未租好 MySQL 服务器，运行时暂用 SQLite；但表名、预聚合层和 SQL 脚本必须保持 MySQL 可迁移。
- 预测以真实 `mv_weekly_sales` 周粒度序列为输入，输出未来 6 周预测值和置信区间；不能使用模拟序列替代真实数据。
- 规范性分析不能只写通用建议，应尽量融合配送、卖家、品类、支付和评论/NLP 洞察。

## 推荐工作流

1. 数据层：整理 9 张原始 CSV，统一字段、时间类型、缺失值处理，当前构建 SQLite 本地库，同时维护 MySQL 建表和预聚合 SQL。
2. 查询层：维护基础表与视图的数据字典；DataAnalyst 必须由真实大模型生成 SQL，代码只做视图优先提示、只读校验和执行。
3. Agent 层：用 LangGraph 编排 Orchestrator、DataAnalyst、ForecastModel、Visualizer、DecisionMaker，统一共享状态和错误返回格式。
4. 分析层：先跑通附录验证问题，再补充预测、诊断下钻、规范性建议和可选加分项。
5. 展示层：FastAPI 提供 HTTP/WebSocket 接口；前端保持双栏布局，左侧对话，右侧图表与建议。
6. 验证层：每个里程碑都要有可复现检查，包括视图可查询、Agent 命中/回退、图表渲染、预测输出、10 个验证问题、性能对比。
7. 报告层：边开发边沉淀截图、SQL、架构图、流程图、技术取舍和小组分工，避免最后集中补材料。

## 开发约束

- 保持改动小而明确，优先按 `plan.md` 的目录结构落地，不引入无关框架。
- 不把原始大数据、数据库文件、模型缓存或生成图片放到 C 盘；大文件应放在项目 `data/` 或明确说明来源。
- 不批量删除文件；任何大规模下载、清理或重建数据前先确认。
- 新增依赖前先判断是否确实必要，并记录到 `requirements.txt`。
- 每个功能完成后用最小可复现命令验证，失败原因要写清楚。
- 模型失败、SQL 非法或数据缺失必须真实报错，不允许返回本地写死建议、模拟 CSV 或特值 SQL 冒充完成。
