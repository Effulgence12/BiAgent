# Agentic BI Olist 项目接手手册

> 面向两名组员的协作手册。

## 1. 项目一句话

"智能商务案例分析"期末项目：**Agentic BI 驱动的多表电商运营分析与决策智能系统**。基于真实 Olist 数据集，业务用户用自然语言提问，多 Agent 协作产出：可验证 SQL 结果、四层分析、可视化图表、未来 6 周预测、可执行运营建议。

## 2. 当前状态

### 已有

- 多 Agent 主链路：`orchestrator` / `data_analyst` / `forecast_model` / `visualizer` / `decision_maker`，真实 Qwen 驱动 SQL 规划与结果解读直答。
- 11 张预聚合表（`mv_*`）+ 命中/回退路由；≥6 种图表；FastAPI + WebSocket 双栏前端。
- 附录 10 题真实验收 **10/10**；离线单测 **34/34** 通过。
- 加分项：负面评论 **NMF 主题建模**（`mv_review_topics`）已融入决策建议；多轮会话记忆可用。

### 待完成（本次收尾重点 → 见第 3 节分工）

1. 预聚合**性能对比截图**（任务书硬性要求，报告里需要有一个章节用普通查询对比 agent，这个应该是要手动查然后截图？）。
2. **MySQL 接入**与运行口径说明。
3. **数据精细 ETL**（清洗 / 类型 / 空值）。
4. **预测模型优化** —— 见第 3 节组员 B 任务 B5。
5. **正式报告 + 演示截图** —— 三人共同（见第 3 节说明）。

## 3. 分工

> **报告撰写为三人共同任务**：各自撰写本人负责模块的章节，不归属任何单一组员。

### 组员 A — 数据与性能层

范围：`data/`、`sql/`、`utils/local_store.py`、`utils/db_init.py`、`config/views_desc.py` 及报告对应章节。**勿改 Agent 主流程**。

- **A1 性能对比截图（最高优先）**：对"基础表 JOIN vs 预聚合表"做耗时对比，至少 1 组、建议 3 组（月度 GMV / 州销售 / 配送延迟），SQL 见附录。截图须含 **SQL + 耗时 + 加速倍数**，放入报告"性能优化"章节。
- **A2 MySQL 接入**：有环境则用 `sql/schema.sql` + `sql/materialized_views.sql` 建库并校验各表行数；无环境则在报告写明"SQLite 为本地演示引擎、MySQL 脚本已提供且表名/字段/预聚合层保持可迁移"。
- **A3 数据精细 ETL**：复核空值、类型转换、时间字段解析，整理成报告"数据预处理"章节。
- **交付**：性能对比表 + 截图、视图说明表、MySQL/SQLite 口径说明、数据预处理章节文字。

### 组员 B — 演示与可视化

以及 B5 预测模型涉及的 `models/forecast.py`（并按 B5 同步 `agents/orchestrator.py`、`tests/test_skeleton.py` 中的 `"ETS"` 字样）。**建议勿改 `sql/` 与 `utils/local_store.py`**（避免与 A 冲突）。

- **B1**：跑 Web，确认问答 / SQL / 图表 / 建议 / 错误提示。
- **B2 撰写报告相关章节**：把直答 + 建议截图等整理进报告相关章节。
- **B3 预测模型优化(主要)**：见下方专节。
- **交付**：预测模型升级（含改前/改后回测对比）。

#### B3 详解：预测模型优化

**背景与问题**

- 当前预测用 statsmodels 的 **ETS（指数平滑）**，真实验收回测 **MAPE≈74.86%**，且伴随"Optimization failed to converge"收敛告警。
- 更关键：**任务书要求预测模型从 Prophet / ARIMA / LSTM / XGBoost 中选用**，ETS 不在其列。所以这一步首先是**合规问题**，其次才是精度。

1. 怎么实现的 / 在哪
   位置：models/forecast.py 的 forecast_sales_6_weeks_with_diagnostics(points)（第 56–110 行）。真正生效的就是这一个函数；同文件的 naive_forecast、linear_forecast 是给旧测试留的死代码，不参与主链路。
   调用点：agents/orchestrator.py:329 的 forecast_node——当 Planner 判定为 predictive 时，条件边路由到 forecast_model 节点，把 mv_weekly_sales 的 week_start/total_gmv 行喂进去。
   算法（第 74 行）：statsmodels 的 ExponentialSmoothing（ETS / Holt 线性趋势指数平滑），trend="add"、seasonal=None。

- 取真实周 GMV 序列，不足 8 周直接报错（第 72–73 行）；
- 拟合后预测未来 6 周（第 88 行 fitted.forecast(6)）；
- 置信区间是经验带：band = max(残差 std × 1.96, yhat × 0.05)（第 92 行），上下对称；
- 诊断里的 MAE/MAPE 用最近 12 个点的样本内拟合值算（第 83–87 行）。

1. 能勉强提交吗？
   能跑、能演示，但不建议直接当最终版交。它端到端是通的（附录验收 10/10、每条预测都带 yhat/yhat_lower/yhat_upper、有趋势解读），作为"保底"能撑住答辩流程。但在评分表上它踩了一个硬合规线（见缺陷 ①），一旦被严格对照任务书就会在预测这一块失分。所以定位是"勉强保底，风险明确"。 3.主要缺陷（按严重度排）

| #   | 缺陷                                                                                                                                                                 | 严重度 |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| ①   | 选型不合规：任务书要求 Prophet/ARIMA/LSTM/XGBoost，ETS 不在其列。这是最大风险，不是精度问题而是"用错了模型族"                                                        | 🔴 高  |
| ②   | 精度差：留出验收 MAPE≈74.86%，被追问准确率会很被动                                                                                                                   | 🔴 高  |
| ③   | 收敛告警：Optimization failed to converge，optimizer 没收敛，演示日志里会暴露                                                                                        | 🟠 中  |
| ④   | 置信区间是"伪区间"：用残差 std×1.96 的对称经验带 + max(yhat0.05)兜底，不是模型自身的预测区间；而且区间宽度不随预测步长变宽（多步预测不确定性本应递增），答辩易被问破 | 🟠 中  |
| ⑤   | 回测是样本内：MAE/MAPE 用 fittedvalues 自比，不是样本外留出法，高估了真实泛化（即便如此数值仍差）                                                                    | 🟠 中  |
| ⑥   | 无季节性建模（seasonal=None），周度波动未捕捉（不过 91 周难做 52 周季节性，这条可接受）                                                                              | 🟡 低  |
| ⑦   | 残留死代码 naive_forecast/linear_forecast                                                                                                                            | 🟡 低  |

一句话：核心病根是 ①（合规）+②（精度）+④（伪区间）。B5 的 ARIMA 方案正好对症——换成允许列表内的模型、用 get_forecast().conf_int() 出真区间（且随步长变宽）、用留出法回测给真实 MAPE，三个主要缺陷一次性解决。
**目标**

1. 合规：改用 **ARIMA**（statsmodels 自带，风险最低；ARIMA 在任务书允许列表内）。
2. 保留**真实置信区间**（用模型自带的 `conf_int()`，不再用残差经验带）。
3. 给出**留出法（train/test）回测的 MAPE**，并在报告里写"改进前 ETS vs 改进后 ARIMA"对比；消除收敛告警。

**改动范围**

- 仅改 `models/forecast.py` 里的 `forecast_sales_6_weeks_with_diagnostics(points)`。
- **返回值结构必须保持不变**（否则会连累 orchestrator / 前端 / 验收）：
  - `forecast`：每项含 `week_start`、`model`、`yhat`、`yhat_lower`、`yhat_upper`；
  - `diagnostics`：含 `model`、`point_count`、`backtest_window`、`mae`、`mape`、`warnings`。
- **保留** `naive_forecast`、`linear_forecast` 两个旧函数（仍被单测引用，勿删）。
- 把残留的 `"ETS"` 字样改为 `"ARIMA"`：`agents/orchestrator.py` 第 ~328 行兜底 diagnostics、第 ~189 行 agent 描述，以及 `tests/test_skeleton.py` 里 `forecast_diagnostics={"model": "ETS"}` 的测试夹具（共 3 处，纯字符串，改了更一致）。

**操作步骤**

1. 在函数顶部把解析 `total_gmv` / `week_start` 的部分保留（已写好，照用），保留 `len(values) < 8` 的报错保护。
2. 用下面骨架替换 ETS 拟合与预测部分，并按需微调 `order`：

```python
from statsmodels.tsa.arima.model import ARIMA
import numpy as np

HORIZON = 6
ORDER = (1, 1, 1)  # 可按 AIC 在 (0..2,1,0..2) 小范围内调优

# 留出法回测：用最后 6 周做样本外检验（数据足够时才做）
mae = mape = None
if len(values) > HORIZON + 8:
    bt = ARIMA(values[:-HORIZON], order=ORDER).fit()
    pred = list(bt.forecast(HORIZON))
    actual = values[-HORIZON:]
    abs_err = [abs(a - p) for a, p in zip(actual, pred)]
    pct = [abs(a - p) / a for a, p in zip(actual, pred) if a > 0]
    mae = sum(abs_err) / len(abs_err) if abs_err else None
    mape = sum(pct) / len(pct) if pct else None

# 全量拟合 + 预测未来 6 周（带置信区间）
fitted = ARIMA(values, order=ORDER).fit()
fc = fitted.get_forecast(steps=HORIZON)
mean = list(fc.predicted_mean)
ci = np.asarray(fc.conf_int(alpha=0.05))  # 形状 (6, 2)

forecast = []
for step in range(1, HORIZON + 1):
    yhat = max(0.0, float(mean[step - 1]))
    lower = max(0.0, float(ci[step - 1][0]))
    upper = float(ci[step - 1][1])
    forecast.append({
        "week_start": (dates[-1] + timedelta(days=7 * step)).isoformat(),
        "model": "ARIMA",
        "yhat": round(yhat, 2),
        "yhat_lower": round(lower, 2),
        "yhat_upper": round(upper, 2),
    })

diagnostics = {
    "model": "ARIMA",
    "order": list(ORDER),
    "point_count": len(values),
    "backtest_window": HORIZON if mae is not None else 0,
    "mae": round(mae, 2) if mae is not None else None,
    "mape": round(mape, 4) if mape is not None else None,
    "warnings": [],
}
return forecast, diagnostics
```

1. **可选提精度**（任选其一，能降 MAPE 再用）：

- 丢弃**尾部不完整周**（Olist 最后一周 GMV 常偏低，会带偏预测）：拟合前去掉最后 1 个明显偏低的点。
- 对 `values` 取 `log1p` 再拟合、预测后 `expm1` 还原（GMV 为乘性增长，常显著降 MAPE）。
- 在 `(p,1,q)`、p、q∈{0,1,2} 小网格里按最小 AIC 选 `order`。

**验证（缺一不可）**

```bash
python -m pytest -q tests -p no:cacheprovider        # 必须仍 34 passed
python -m pytest -q tests -k forecast_node           # 重点：8 点序列仍能出预测、point_count==8
python cli.py "根据历史订单趋势，预测未来6周的销售额，并给出趋势解读。"
python cli.py --validate-assignment                  # 预测题仍 10/10、含 yhat/yhat_lower/yhat_upper
```

**预期目标 / 验收标准**

- `diagnostics.model` 为 `"ARIMA"`，预测每项都带 `yhat_lower/yhat_upper` 置信区间；
- 8 点最小序列不报错（`test_forecast_node...` 通过），34 项单测全绿；
- 留出法回测 **MAPE 明显低于 ETS 的 74.86%**（目标 < 40%；若受数据波动限制仍偏高，需在报告如实写出回测方法与数值，不可造假）；
- 不再出现收敛告警；
- 报告"预测分析"章节给出"ETS→ARIMA 改进前后对比表"。

## 4. 常用命令

```bash
conda activate bussiness_final

# 启动 Web，浏览器访问 http://127.0.0.1:8000
uvicorn app:app --reload

# 命令行单题分析
python cli.py "2017年各月GMV趋势？"
python cli.py "哪些州配送延迟严重？"
python cli.py "预测未来6周GMV。"

# 任务书 附录 10 题验收（真实调用 Qwen，需 .env 中可用 API Key）
python cli.py --validate-assignment

# 离线单元测试
python -m pytest -q tests -p no:cacheprovider

# 查看基础表与预聚合表行数
python -c "from utils.local_store import ensure_local_store, table_counts; print(ensure_local_store()); print(table_counts())"
```

演示 6 问：

```text
2017年GMV是多少？按月和各州排名的趋势怎样？
平台整体准时交付率是多少？哪些州延迟最严重？
哪种支付方式最受欢迎？平均分期数是多少？
产品重量、尺寸与运费之间有什么关系？
根据历史订单趋势，预测未来6周的销售额，并给出趋势解读。
基于全部分析结果，给出平台3个月内的三大优先改进策略。
```

## 附录：性能对比 SQL（A1 用）

每组"基础表查询"与对应"预聚合表查询"结果一致，但前者需实时 JOIN 聚合、后者直接读 `mv_*`。各组预聚合等价写法为 `SELECT ... FROM mv_xxx ...`。

```sql
-- 对比 1｜月度 GMV：基础表
SELECT substr(o.order_purchase_timestamp,1,7) AS year_month,
       COUNT(DISTINCT o.order_id) AS total_orders,
       SUM(oi.price + oi.freight_value) AS total_gmv
FROM orders o JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_status = 'delivered'
GROUP BY year_month ORDER BY year_month;
-- 预聚合：SELECT year_month, total_orders, total_gmv FROM mv_monthly_sales ORDER BY year_month;

-- 对比 2｜州销售排行：基础表
SELECT c.customer_state,
       COUNT(DISTINCT o.order_id) AS total_orders,
       SUM(oi.price + oi.freight_value) AS total_gmv
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_status = 'delivered'
GROUP BY c.customer_state ORDER BY total_gmv DESC;
-- 预聚合：SELECT customer_state, SUM(total_orders), SUM(total_gmv) FROM mv_state_sales GROUP BY customer_state ORDER BY 3 DESC;

-- 对比 3｜配送延迟：基础表
SELECT c.customer_state,
       COUNT(DISTINCT o.order_id) AS total_orders,
       AVG(julianday(o.order_delivered_customer_date) - julianday(o.order_purchase_timestamp)) AS avg_delivery_days,
       SUM(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 ELSE 0 END) AS late_orders
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_status = 'delivered' AND o.order_delivered_customer_date <> ''
GROUP BY c.customer_state ORDER BY late_orders DESC;
-- 预聚合：SELECT customer_state, SUM(total_orders), AVG(avg_delivery_days), SUM(late_orders) FROM mv_delivery_perf GROUP BY customer_state ORDER BY 4 DESC;
```

输出建议格式：

| 查询问题   | 基础表耗时 | 预聚合表耗时 | 加速效果 |
| ---------- | ---------- | ------------ | -------- |
| 月度 GMV   | xx ms      | xx ms        | x.x×     |
| 州销售排行 | xx ms      | xx ms        | x.x×     |
| 配送延迟   | xx ms      | xx ms        | x.x×     |
