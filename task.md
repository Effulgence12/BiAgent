# 智能商务案例分析 期末项目任务书

# 项目题目:Agentic BI驱动的多表电商运营分析与决策智能系统
## Project Title: Agentic BI-Driven Multi-Table E-Commerce Operations Analysis and Decision Intelligence System

## 一、项目背景与目标
随着大语言模型与多智能体技术的成熟,商业智能正从"被动看板"进化为"主动分析与决策引擎"--这便是Agentic BI的核心思想。本项目要求同学们基于真实多表电商数据集,设计并实现一个多智能体协作的BI分析系统,能够:理解自然语言业务问题、自动完成跨表数据查询与多维度统计分析、生成预测与可视化图表、给出具有决策价值的规范性建议。

通过本实战项目,你将深入理解Agentic BI、决策智能、AI 原生BI架构等前沿概念,并掌握多智能体框架的开发方法。

### 1. Project Background and Objectives
With the maturation of large language models (LLMs) and muli-agent technologies, business intelligence is evolving from "passive dashboards" into a "proactive analysis and decision engine"this is the core idea of Agentic Bl. This project requires students to design and implement a multiagent collaborative Bl analysis system based on a real multi-table e-commerce dataset. The system should be able to: understand natural language business questions, automatically execute cross-table data queries and muli-dimensional statistical analysis, generate forecasts and visualization charts, and provide prescriptive recommendations with decision-making value.

Through this hands-on project, you will gain an in-depth understanding of cutting-edge concepts such as Agentic BIl, Decision Intelligence (DI), and Al-native Bl architecture, and master the development methods of multi-agent frameworks.

## 二、数据集说明
指定数据集: Brazilian E-Commerce Public Dataset by Olist (巴西Olist电商公开数据集)
来源:Kaggle .(https://www.kaggle.com/atasetsenzoschitinibrazilian-e-commerce-public-dataset-byolist)

### 核心字段:
1. order_id: Unique identifier of the order.
2. order_item_id: Identifier of the item in the order.
3. customer_id: Customer identifier.
4. customer_unique_id: Unique customer identiier.
5. customer_zip_code_prefix: Customer's ZIP code prefix.
6. customer_city: Customer's city.
7. customer_state: Customer's state.
8. product_id: Product identifier.
9. product_category_name: Name of the product category.
10. product_name_length: Length of the product name.
11. product_description_length: Length of the product description.
12. product_photos_qty: Quantity of product photos.
13. product_weight_g: Product weight in grams.
14. product_length_cm: Product length in centimeters.
15. product_height_cm: Product height in centimeters.
16. product_width_cm: Product width in centimeters.
17. seller_id: Seller identifier.
18. seller_city: Seller's city.
19. seller_state: Seller's state.
20. seller_zip_code_prefix: Seller's ZIP code prefix.
21. payment_type: Payment type.
22. payment_sequential: Payment sequential.
23. payment_installments: Number of payment installments.
24. installments_price: Price of installments.
25. price: Product price.
26. freight_value: Freight value.
27. payment_value: Total payment value.
28. shipping_limit_date: Shipping deadline date.
29. order_purchase_timestamp: Purchase timestamp.
30. order_approved_at: Order approval timestamp.
31. order_delivered_carrier_date: Delivery date to the carrier.
32. order_delivered_customer_date: Delivery date to the customer.
33. order_estimated_delivery_date: Estimated delivery date.
34. shipping_duration: Shipping duration.
35. day_of_purchase: Day of purchase.
36. month_of_purchase: Month of purchase.
37. year_of_purchase: Year of purchase.
38. month/year_of_purchase: Month and year of purchase.
39. order_status: Order status.
40. order_unique_id: Unique order identifier.

### 数据集说明:
多表结构需要跨表JOIN分析,考察数据建模能力
包含支付方式/分期数、配送时效、商品物理属性(重量/尺寸)等多维字段
可以分析从下单到送达的全订单链路(物流时效、准时率)
核心性能提示:该数据集涉及多个维度的查询,部分JOIN操作可能产生较大中间结果集,必须实现高频聚合查询Pre-Aggregation视图(见下节)。

### II. Dataset Description
Designated Dataset: Brazilian E-Commerce Public Dataset by Olist
Source: Kaggle (https:/www.kaggle.com/atasetsenzoschitinibrazilian-e-commerce-public-dataset-byolist)

### Core Data Fields:
1. order_id: Unique identifier of the order.
2. order_item_id: Identifier of the item in the order.
3. customer_id: Customer identifier.
4. customer_unique_id: Unique customer identifier.
5. customer_zip_code_prefix: Customer's ZIP code prefix.
6. customer_city: Customer's city.
7. customer_state: Customer's state.
8. product_id: Product identifier.
9. product_category_name: Name of the product category.
10. product_name_length: Length of the product name.
11. product_description_length: Length of the product description.
12. product_photos_qty: Quantity of product photos.
13. product_weight_g: Product weight in grams.
14. product_length_cm: Product length in centimeters.
15. product_height_cm: Product height in centimeters.
16. product_width_cm: Product width in centimeters.
17. seller_id: Seller identifier.
18. seller_city: Seller's city.
19. seller_state: Seller's state.
20. seller_zip_code_prefix: Seller's ZIP code prefix.
21. payment_type: Payment type.
22. payment_sequential: Payment sequential.
23. payment_installments: Number of payment installments.
24. installments_price: Price of installments.
25. price: Product price.
26. freight_value: Freight value.
27. payment_value: Total payment value.
28. shipping_limit_date: Shipping deadline date.
29. order_purchase_timestamp: Purchase timestamp.
30. order_approved_at: Order approval timestamp.
31. order_delivered_carrier_date: Delivery date to the carier.
32. order_delivered_customer_date: Delivery date to the customer.
33. order_estimated_delivery_date: Estimated delivery date.
34. shipping_duration: Shipping duration.
35. day_of_purchase: Day of purchase.
36. month_of_purchase: Month of purchase.
37. year_of_purchase: Year of purchase.
38. month/year_of_purchase: Month and year of purchase.
39. order_status: Order status.
40. order_unique_id: Unique order identifier.

### Dataset Characteristics:
Multi-table structure requires cross-table JOIN analysis, testing data modeling capabilities.
Contains multi-dimensional fields such as payment methodslinstallments, delivery timeliness, product physical attributes (weight/dimensions).
Enables analysis of the entire order lifecycle from placement to delivery (logistics timeliness, ontime rate).
Core Performance Note: This dataset involves multi dimensional data. Some JOIN operations may generate large intermediate result sets. You must implement high-frequency aggregated query Pre-Aggregation views (see next section).

## 三、Pre-Aggregation试图
为了在Agent频繁调用数据时保证响应速度,必须预先创建若干张预聚合视图作为性能加速层。数据分析Agent应优先查询这些预计算表,只有在视图无法覆盖查询时才回退到基础表的全量扫描。

你必须创建并维护以下预聚合视图(至少4个):

| 视图名称 | 核心字段(示例,按照实际数据处理) | 用途示例 |
| --- | --- | --- |
| mv_monthly_sales 年-月 | year_month, total_gmv, total_orders, avg_basket, total_freight | "月度销售趋势"、 "GMV环比增长" |
| mv_state_sales | year_month, customer_state, total_gmv, total_orders, unique_customers | "各州销售额排名"、 "区域市场对比" |
| mv_category_sales | 年-月-品 year_month, product_category_english, total_gmv, total_orders, avg_price | "品类表现分析"、"哪些品类在下降" |
| mv_delivery_perf 年-月-州 | year_month, customer_state, avg_delivery_days, on_time_rate, delayed_orders | "配送延迟诊断"、"准时率分析" |
| mv_seller_perf (推荐) 年-月-卖 | year_month, seller_id, seller_state, total_gmv, total_orders, avg_review_score | "卖家绩效监控"、"高差评卖家定位" |
| mv_payment_dist (推荐) 年-月-支付类型 | year_month,payment_type, total_transactions, avg_installments, total_value | "支付偏好分析"、"分期率对比" |

| 视图名称 | 粒度 | 核心字段(示例,按照实际数据处理) | 用途示例 |
| --- | --- | --- | --- |
| mv_monthly_sales | Year-Month | total_orders, avg_basket, total_freight | "月度销售趋势"、"GMV month-over-month growth" |
| mv_state_sales | Year-Month-State | year_month, customer_state, total_gmv, total_orders, unique_customers | "State sales ranking"、"Regional market comparison" |
| mv_category_sales | Year-Month-Category | year_month, product_category_english, total_gmv, total_orders, avg_price | "Category performance analysis"、"Which categories are declining" |
| mv_delivery_perf | Year-Month-State | year_month, customer_state, avg_delivery_days, on_time_rate, delayed_orders | "Delivery delay diagnosis"、"On-time rate analysis" |
| mv_seller_perf(Recommended) | Year-Month-Seller | year_month, seller_id, seller_state, total_gmv, total_orders, avg_review_score | "Seller performance monitoring"、"Identifying high-negative-review sellers" |
| mv_payment_dist(Recommended) | Year-Month-Payment Type | year_month, payment_type, total_transactions, avg_installments, total_value | "Payment preference analysis"、"Installment rate comparison" |

### 实现与使用要求:
1.生成脚本:在utils/或data/目录下提供具体的预聚合视图创建脚本(SQL),所有视图必须基于原始表一次性计算,并在系统启动时自动构建或通过脚本一键刷新。
2.Agent查询策略:数据分析Agent的Prompt或配置中必须包含对各预聚合视图的说明(名称、粒度、字段),当用户问题匹配到上述预计算维度时,优先使用预聚合视图查询。例如:用户问"去年每个月的销售额是多少?",Agent应直接 SELECT *FROM mv_monthly_sales而不是JOIN orders、order_items等原始表做实时聚合。
3.回退机制:当问题维度不在任何预聚合视图中(如查询某个具体订单的详情)时,Agent必须能够回退到基础表进行查询。
4.性能对比截图:在项目报告中至少提供一组对比截图,展示同一分析问题在使用预聚合视图前后的查询耗时差异,证明优化效果。

### Ill. Pre-Aggregated Views
To ensure response speed when agents frequently query data, you must pre-create several preaggregated views as a performance acceleration layer. The Data Analysis Agent should priortize querying these pre-computed tables, falling back to full scans of base tables only when the view cannot cover the query.

You must create and maintain the following pre-aggregated views (at least 4):

| View Name | Granularity | Core Fields(Samples) | Use Case Examples |
| --- | --- | --- | --- |
| mv_monthly_sales | Year-Month | total_orders, avg_basket, total_freight | "Monthly sales trend", "GMV month-over-month growth" |
| mv_state_sales | Year-Month-State | year_month, customer_state, total_gmv, total_orders, unique_customers | "State sales ranking", "Regional market comparison" |
| mv_category_sales | Year-Month-Category | year_month, product_category_english, total_gmv, total_orders, avg_price | "Category performance analysis", "Which categories are declining" |
| mv_delivery_perf | Year-Month-State | year_month, customer_state, avg_delivery_days, on_time_rate, delayed_orders | "Delivery delay diagnosis", "On-time rate analysis" |
| mv_seller_perf(Recommended) | Year-Month-Seller | year_month, seller_id, seller_state, total_gmv, total_orders, avg_review_score | "Seller performance monitoring", "Identifying high-negative-review sellers" |
| mv_payment_dist(Recommended) | Year-Month-Payment Type | year_month, payment_type, total_transactions, avg_installments, total_value | "Payment preference analysis", "Installment rate comparison" |

### Implementation and Usage Requirements:
1. Creation Scripts: Provide specific SQL creation scripts for the pre-aggregated views in the utils/ or data/directory. All views must be calculated once from the base tables and built automatically on system startup or refreshable via a single script.
2. Agent Query Strategy: The Data Analysis Agent's Prompt or configuration must include descriptions (name, granularity, fields) of each pre-aggregated view. When a user question matches the pre-computed dimensions, prioritize querying the pre-aggregated view. For example, if a user asks "What were the monthly sales last year?", Agent should directly SELECT * FROM mv_monthly_sales instead of JOINing orders, order_items, etc., for real-time aggregation.
3. Fallback Mechanism: When the question's dimensions are not covered by any pre-aggregated view (e.g., querying details of a specific order), Agent must be able to fall back to querying the base tables.
4. Performance Comparison Screenshots: Incude at least one set of comparison screenshots in the project report, showing the query time difference for the same analytical question with and without pre-aggregated views, demonstrating the optimization effect.

## 四、业务场景与数据分析要求
假设角色:你是一家巴西跨境电商平台Olist的数据科学与决策支持顾问。
核心任务:构建Agentic BI系统,让非技术业务人员能用自然语言提问,并即时获得分析结论、可视化图形与可执行的商业建议。

至少需要覆盖以下四类分析要求:

| 分析类型 | 示例问题 | 技术要求 |
| --- | --- | --- |
| 描述性分析 | "2017年哪个州的销售额最高?交付准时率是多少?哪种支付方式最受欢迎?" | 跨表聚合统计、KPI计算(GMV、客单价、平均配送时长等),必须利用预聚合视图加速 |
| 诊断性分析 | "为什么某些州的平均配送时长显著高于全国均值?哪些卖家的差评率最高?" | 关联sellers、orders、reviews表做下钻分析;定位差评率高的卖家与品类;分析配送延迟与客户地理位置/卖家地理位置的关系 |
| 预测性分析 | "根据历史订单趋势,预测未来6周的销售额" | 使用适当的时间序列预测模型(Prophet、ARIMA、LSTM或XGBoost),基于预聚合视图mv_monthly_sales提供的历史序列进行建模,生成预测值及置信区间 |
| 规范性分析(决策智能) | "如何降低巴西东北部地区的高退货率?请给出具体的运营改进方案。" | 结合前三层分析结果,Agent调用LLMM推理;融合review文本情感分析结果;给出可行动的分段策略建议(如调整物流、筛选卖家、优化定价) |

### 加分场景:
- 实现What-if模拟分析:"如果将Top 20高差评卖家的商品统一下架,平台整体评分预估提升多少?"
- 实现异常检测Agent,自动扫描近期数据并预警异常(如某州订单量骤降、差评率突升)

### IV. Business Scenario and Data Analysis Requirements
Assumed Role: You are a Data Science and Decision Support Consultant for the Brazilian crossborder e-commerce platform Olist.
Core Task: Build an Agentic Bl system that enables non-technical business users to ask questions in natural language and instantly receive analytical conclusions, visualization charts, and executable business recommendations.

You must cover at least the following four types of analysis:

| Analysis Type | Example Question | Technical Requirements |
| --- | --- | --- |
| Descriptive Analysis | "Which state had the highest sales in 2017? What is the on-time delivery rate? Which payment method is most popular?" | Cross-table aggregation, KPI calculation (GMV, Average Order Value, average delivery totime, etc.). Must leverage pre-aggregated views for acceleration. |
| Diagnostic Analysis | "Why is the average delivery time significantly higher in some states? Which sellers have the highest negative review rates?" | Drill-down analysis by joining sellers, orders, reviews; identify sellers/categories with high negative review rates; analyze the relationship between delivery delays and customer/seller geographic location. |
| Predictive Analysis | "Based on historical order trends, predict sales for the next 6 weeks." | Use an appropriate time series forecasting model (Prophet, ARIMA, LSTM, or XGBoost). Build the model based on the historical series provided by the pre-aggregated view mv_monthly_sales, generating forecast values and confidence intervals. |
| Prescriptive Analysis (Decision Intelligence) | "How can we reduce the high return rate in Northeast Brazil? Provide specific operational improvement plans." | Combine results from the first three layers of analysis. The Agent invokes LLM reasoning; incorporates NLP sentiment analysis results from reviews; provides actionable, segmented strategy recommendations (e.g. adjust logistics, screen sellers, optimize pricing). |

### Bonus Scenarios:
- Implement a What-if simulation analysis: "If we uniformly delist the products of the Top 20 highnegative-review sellers, what would be the estimated improvement in the platform's overall rating?"
- Implement an Anomaly Detection Agent that automatically scans recent data and alerts on anomalies (e.g., a sudden drop in orders in a state, a surge in negative review rates).

## 五、Agentic BI 框架与技术要求
你需要设计并实现一个多智能体系统来完成上述任务,必须满足以下技术要求:

### 1.基础平台
- 必须接入大语言模型(GPT-4o、DeepSeek、Qwen等),可调用API或使用本地开源模型
- 多表查询与预聚合视图引擎:使用MySQL作为查询引擎,原始表与预聚合视图共同驻留在数据库中。让Agent生成SQL完成跨表JOIN与聚合,并利用预聚合视图加速
- Agent编排推荐:鉴于本项目涉及多表查询、文本分析、时间序列预测等异质任务,推荐采用LangGraph 等工具构建有状态的任务编排图。用StateGraph的节点定义各Agent的执行函数,用条件边控制任务分支,Agent间通过共享状态字典传递中间结果,并利用MemorySaver实现对话上下文记忆

### 2.智能体角色设计(至少4个Agent)
| Agent角色 | 核心职责 |
| --- | --- |
| 数据分析Agent | 将自然语言问题转换为SQL。首要动作:根据问题维度,判断能否命中预聚合视图;若能,则对视图查询;若不能,则对基础表进行SQL查询。输出统计表与数据摘要。需维护数据字典(基础表+预聚合视图) |
| 可视化Agent | 根据分析结果,自动选择合适图表类型(折线图、柱状图、热力图、地理图、词云等),生成并保存图片文件 |
| 决策智能Agent | 以分析摘要+预测结果+NLP洞察为输入,结合电商业务知识推理,输出商业建议与What-if答案 |
| 协调器Agent | 解析用户问题,规划多步分析流程,将子任务分派给相应Agent,汇总最终回答 |

### 3.协作流程示例
用户输入:"分析平台整体运营状况,找出需要优化的方面并给出策略建议。"
- 协调器→将问题分解为五大子任务。
- 数据分析 Agent→依次查询 mv_monthly_sales、mv_state_sales、mv_delivery_perf、mv_category_sales、mv_payment_dist等预聚合视图,快速获得各维度统计。
- 可视化Agent→基于视图结果生成趋势图、地理热力图、配送对比图、支付饼图。
- 决策智能Agent→综合所有结果,识别问题区域,输出分级改进策略。
- 协调器→整合所有结果返回用户。

### 4.自然语言交互接口
- 搭建Web界面,支持连续问答与结果展示
- 系统需跨Agent维护会话上下文,使连续问题可引用之前的分析结果
- 建议设计左侧对话区+右侧可视化展示区的双栏布局

### V. Agentic BI Framework and Technical Requirements
You need to design and implement a multi-agent system to complete the above tasks, meeting the following technical requirements:

### 1. Base Platform
- Must integrate with a Large Language Model (GPT-4o, Deep Seek, Qwen, etc.), either via APl calls or a locally deployed open-source model.
- Multi-table Query and Pre-aggregated View Engine: Use MySQL as query engine, where raw tables and pre-aggregated views reside together. Let Agent generate SQL to complete cross-table JOINs and aggregations, leveraging pre-aggregated views for acceleration.
- Agent Orchestration Recommendation: Given the heterogeneous tasks involved (multi-table queries, text analysis, time series forecasting), it is recommended to use tools like LangGraph to build a stateful task orchestration graph. Define each Agent's execution function as a node in a StateGraph, use conditional edges to control task branching, pass intermediate results between Agents via a shared state dictionary, and utlize MemorySaver for conversational context memory.

### 2. Agent Role Design (At least 4 Agents)
| Agent Role | Core Responsibilities |
| --- | --- |
| Data Analysis Agent | Convert natural language questions into SQL. Primary action: determine ifthe question's dimensions can hit a pre-aggregated view; if yes, query the view; if no, perform an SQL query on the base tables. Output statistical tables and data summaries. Must maintain a data dictionary (base tables + pre-aggregated views). |
| Visualization Agent | Automatically select the appropriate chart type (line chart, bar chart, heatmap, geographic map, word cloud, etc.) based on the analysis results, generate and save image files. |
| Decision Intelligence Agent | Take analysis summaries + forecast results + NLP insights as input, reason with e-commerce business knowledge, and output business recommendations and What-if answers. |
| Orchestrator Agent | Parse user questions, plan multi-step analysis workflows, dispatch sub-tasks to corresponding Agents, and aggregate the final response. |

### 3. Workflow Example
User Input: "Analyze the platform's overall operational status, identify areas for optimization, and provide strategic recommendations."
- Orchestrator → Decomposes the problem into five sub-tasks.
- Data Analysis Agent → Sequentially queries mv_monthly_sales, mv_state_sales, mv_delivery_perf, mv_category_sales, mv_payment_dist and other pre-aggregated views to quickly obtain statistics for each dimension.
- Visualization Agent → Generates trend charts, geographic heatmaps, delivery comparison charts, and payment pie charts based on the view results.
- Decision Inteligence Agent → Synthesizes all results, identifies problem areas, and outputs tiered improvement strategies.
- Orchestrator → Aggregates all results and returns to the user.

### 4. Natural Language Interaction Interface
- Build a Web interface supporting continuous Q&A and result display.
- The system must maintain session context across Agents, allowing follow-up questions to reference previous analysis results.
- A two-column layout with a dialogue area on the left and a visualization display area on the right is recommended.

## 六、可视化要求
系统需自动生成并展示不少于6种不同类型的可视化图表(多表数据提供更丰富的可视化可能性):

| 序号 | 图表类型 | 展示要求 |
| --- | --- | --- |
| 1 | 时间序列折线图 | 基于mv_monthly_sales构建月度销售额趋势,叠加未来6周预测曲线及置信区间 |
| 2 | 地理热力图/气泡图 | 基于mv_state_sales和 geolocation表绘制巴西各州销售额、订单量分布 |
| 3 | 柱状图/条形图 | 各州客单价对比、Top品类销售额、支付方式频率,均优先从预聚合视图取数 |
| 4 | 热力图/矩阵图 | 支付方式×分期数交叉矩阵,或品类×平均评分矩阵 |
| 5 | 散点图/气泡图 | 商品重量 vs 运费散点图,气泡大小表示订单量,颜色区分配送状态 |

### 仪表板集成:
最终系统应在一个Web页面中整合对话输入框、分析结论、可视化图表及决策建议,形成完整的Agentic BI体验。

### VI. Visualization Requirements
The system must automatically generate and display no fewer than 6 different types of visualization charts (the multi-table data offers richer visualization possibilities):

| No. | Chart Type | Display Requirement |
| --- | --- | --- |
| 1 | Time Series Line Chart | Build a monthly sales trend based on mv_monthly_sales, overlay with the 6-week forecast curve and confidence intervals. |
| 2 | Geographic Heatmap / Bubble Map | Plot the distribution of sales and order volume across Brazilian states using mv_state_sales and the geolocation table. |
| 3 | Bar Chart / Column Chart | Compare Average Order Value by state, Top category sales, and payment method frequency. All should prioritize reading from pre- aggregated views. |
| 4 | Heatmap / Matrix Chart | Cross-tabulation matrix of payment method vs. installment count, or category vs. average rating matrix. |
| 5 | Scatter Plot / Bubble Chart | Product weight vs. freight cost scatter plot, where bubble size represent order volume and color distinguishes delivery status. |

### Dashboard Integration:
Final system should integrate the dialogue input box, analytical conclusions, visualization charts, and decision recommendations into a single Web page, forming a complete Agentic Bl experience.

## 七、提交要求
### 1.项目代码
- 完整可运行的Python项目,包含多Agent实现、预聚合视图创建脚本、Web界面
- 项目目录结构建议:
```
AgenticBl_Final_Olist/
-data/ #原始数据集
-agents/ #各Agent定义
-utils/ #数据加载、清洗、预聚合视图SQL、数据库初始化
-dashboard/ #Web界面
-models/ #预测模型与NLP模型
-config/ #Prompt模板与数据字典
-app.py #入口
-requirements.txt
-README.md
```

### 2.项目报告
- 项目背景与动机
- 系统架构设计图(含Agent流程与预聚合视图层)
- 关键技术选型说明(LLM、Agent框架、查询引擎、预测模型)
- 预聚合视图设计专节:列出创建的视图及其SQL定义,说明如何被Agent利用;附上至少一组性能对比截图(同一查询有无预聚合视图的执行时间对比)
- 数据集描述与预处理步骤
- 智能体实现和多智能体调度方法
- 运行结果截图、分析解释及决策建议解读
- 技术挑战与解决方案
- 小组分工和比例

### VIl. Submission Requirements
### 1. Project Code
- A complete, runnable Python project, including the muli-agent implementation, pre-aggregated view creation scripts, and Web interface.
- Suggested project directory structure:
```
AgenticBl_Final_Olist/
-data/ # Raw dataset
-agents/ # Agent definitions
-utils/ # Data loading, cleaning, pre-aggregated view SQL, database initialization
-dashboard/ # Web interface
-models/ # Forecasting models and NLP models
-config/ # Prompt templates and data dictionary
-app.py # Entry point
-requirements.txt
-README.md
```

### 2. Project Report
- Project background and motivation.
- System architecture design diagram (including Agent workflow and pre-aggregated view layer).
- Key technology selection rationale (LLM, Agent framework, query engine, forecasting model).
- Dedicated section on Pre-Aggregated View Design: List the created views and their SQL definitions, explain how they are utlized by the Agent; attach at least one set of performance comparison screenshots (query execution time with and without pre-aggregated views).
- Dataset description and preprocessing steps.
- Agent implementation and muli-agent scheduling methods.
- Screenshots of operational results, analysis interpretations, and decision recommendation explanations.
- Technical challenges encountered and solutions.
- Team member contributions and percentage.

## 八、评分标准(总分100分)
| 评分项 | 分值 | 要求说明 |
| --- | --- | --- |
| 数据预处理与多表查询准确性 | 20 | 正确完成9张表的清洗与关联;预聚合视图创建正确、可刷新;Agent能根据问题准确命中/回退查询 |
| 预聚合视图设计与性能优化 | 10 | 至少实现4个预聚合视图,Agent查询策略体现出优先使用视图的逻辑;报告中有性能对比截图,响应时间有显著改善 |
| Agentic BI系统设计与多智能体协作 | 20 | 4+ Agent 角色设计合理、协作流程正确;多表查询与视图调度策略清晰有效 |
| 分析任务的完整度与深度 | 20 | 完整实现描述、诊断、预测、规范性四层分析;决策建议具体、具备业务可操作性 |
| 可视化质量与仪表板交互 | 15 | 图表种类 ≥6 种、美观清晰; Web 界面可交互, 布局合理, 支持多轮问答 |
| 报告与演示质量 | 15 | 报告结构完整、阐述清晰;演示突出预聚合视图加速等亮点,时间控制得当 |

### 额外加分(≤10分):
- 对评论文本进行情感分析或主题建模,并将结果融入决策建议(+3分)
- 实现What-if分析或异常检测Agent并动态展示(+3分)
- 使用本地开源LLM完成全部Agent推理(+2分)
- 为Agent加入记忆模块,支持多轮关联分析(+2分)

### VIll. Grading Criteria (Total: 100 points)
| Grading Item | Points | Requirement Description |
| --- | --- | --- |
| Data Preprocessing & Multi-table Query Accuracy | 20 | Correctly complete cleaning and joining of the 9 tables; pre-aggregated views are correctly created and refreshable; Agent can accurately hit/fallback queries based on the question. |
| Pre-Aggregated View Design & Performance Opt. | 10 | Implement at least 4 pre-aggregated views; Agent query strategy demonstrates logic for prioritizing views; report includes performance comparison screenshots showing significant response time improvement. |
| Agentic BI System Design & Multi-Agent Collab. | 20 | 4+ Agent roles are well-designed, collaboration flow is correct; multi-table query and view scheduling strategy is clear and effective. |
| Completeness and Depth of Analysis Tasks | 20 | Fully implement descriptive, diagnostic, predictive, and prescriptive analysis layers; decision recommendations are specific and operationally feasible. |
| Visualization Quality & Dashboard Interactivity | 15 | Chart types ≥6, aestheticaly clear; Web interface is interactive, welllaid-out, and supports multi-turn Q&A. |
| Report & Demo Quality | 15 | Report is well-structured and clearly articulated; demo highlights key features like pre-aggregated view acceleration, with good time management. |

### Extra Credit (≤ 10 points):
- Perform sentiment analysis or topic modeling on review text and integrate results into decision recommendations (+3 points).
- Implement a What-if analysis or Anomaly Detection Agent with dynamic display (+3 points).
- Use a locally deployed open-source LLM for all Agent reasoning (+2 points).
- Add a memory module for Agents to support multi-tur correlated analysis (+2 points).

## 九、附录:数据集分析能力验证问题
你的Agentic BI系统应至少能回答以下问题:
- "2017年GMV是多少?按月和各州排名的趋势怎样?"(命中mv_monthly_sales和 mv_state_sales)
- "平台整体准时交付率是多少?哪些州延迟最严重?"(命中mv_delivery_perf)
- "哪种支付方式最受欢迎? 平均分期数是多少?"(命中mv_payment_dist)
- "产品的重量、尺寸与运费之间有什么关系?"
- "Top10差评品类及其主要差评原因是什么?"
- "根据历史订单趋势,预测未来6周的销售额,并给出趋势解读。"
- "基于全部分析结果,给出平台3个月内的三大优先改进策略。"
- "2017年哪个州的销售额最高?交付准时率是多少?哪种支付方式最受欢迎?"
- "为什么某些州的平均配送时长显著高于全国均值?哪些卖家的差评率最高?"
- "如何降低巴西东北部地区的高退货率?请给出具体的运营改进方案。"

### IX. Appendix: Dataset Analysis Capability Verification Questions
Your Agentic Bl system should be able to answer at least the following questions:
- "What is the GMV for 2017? What are the trends by month and state ranking?" (Hits mv_monthly_sales and mv_state_sales)
- "What is the platform's overall on-time delivery rate? Which states have the most severe delays?" (Hits mv_delivery_perf)
- "Which payment method is most popular? What is the average number of installments?" (Hits mv_payment_dist)
- "What is the relationship between product weightsize and shipping cost?"
- "What are the Top 10 high-negative-review categories and their main reasons for bad reviews?"
- "Based on historical order trends, predict the sales for the next 6 weeks and provide a trend interpretation."
- "Based on all analysis results, provide the top 3 priority improvement strategies for the platform within 3 months."
- "Which state had the highest sales in 2017? What is the on-time delivery rate? Which payment method is most popular?"
- "Why is the average delivery time significantly higher in some states? Which sellers have the highest negative review rates?"
- "How can we reduce the high return rate in Northeast Brazil? Provide specific operational improvement plans."