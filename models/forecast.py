"""Forecasting utilities for the Agentic BI project."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from statistics import median
import warnings

from statsmodels.tsa.arima.model import ARIMA


def naive_forecast(values: Sequence[float], periods: int = 6) -> list[float]:
    """Return a simple last-value forecast for compatibility with earlier tests."""
    if periods < 1:
        raise ValueError("periods must be at least 1")
    if not values:
        return [0.0] * periods
    return [float(values[-1])] * periods


def linear_forecast(points: Sequence[dict[str, object]], value_key: str = "total_gmv", periods: int = 6) -> list[dict[str, float | int]]:
    """Forecast future values with a linear trend and residual confidence band."""
    values: list[float] = []
    for point in points:
        try:
            values.append(float(point[value_key]))
        except (KeyError, TypeError, ValueError):
            continue
    if not values:
        return [{"period": i + 1, "yhat": 0.0, "yhat_lower": 0.0, "yhat_upper": 0.0} for i in range(periods)]
    if len(values) == 1:
        slope = 0.0
    else:
        x_mean = (len(values) - 1) / 2
        y_mean = sum(values) / len(values)
        numerator = sum((idx - x_mean) * (value - y_mean) for idx, value in enumerate(values))
        denominator = sum((idx - x_mean) ** 2 for idx in range(len(values))) or 1.0
        slope = numerator / denominator
    last = values[-1]
    volatility = max(0.05 * abs(last), (max(values) - min(values)) * 0.08 if len(values) > 1 else 0.0)
    forecast = []
    for step in range(1, periods + 1):
        yhat = max(0.0, last + slope * step)
        forecast.append({"period": step, "yhat": round(yhat, 2), "yhat_lower": round(max(0.0, yhat - volatility), 2), "yhat_upper": round(yhat + volatility, 2)})
    return forecast


def forecast_sales_6_weeks(points: Sequence[dict[str, object]]) -> list[dict[str, float | str]]:
    """Forecast the next six weekly GMV points with ARIMA confidence intervals."""
    forecast, _diagnostics = forecast_sales_6_weeks_with_diagnostics(points)
    return forecast


def forecast_sales_6_weeks_with_diagnostics(points: Sequence[dict[str, object]]) -> tuple[list[dict[str, float | str]], dict[str, object]]:
    """Forecast weekly GMV with ARIMA and expose model diagnostics.

    使用任务书认可的时间序列方法 ARIMA。所有输入来自真实
    `mv_weekly_sales`，模型失败时抛出真实错误，不生成模拟序列。
    """
    horizon = 6
    order = (1, 1, 1)
    values: list[float] = []
    dates: list[date] = []
    for point in points:
        try:
            values.append(float(point["total_gmv"]))
            dates.append(date.fromisoformat(str(point["week_start"])[:10]))
        except (KeyError, TypeError, ValueError):
            continue
    if not values:
        return [], {"model": "ARIMA", "point_count": 0, "warnings": ["没有可用周GMV序列"]}
    if len(values) < 8:
        raise ValueError("真实周GMV序列不足8周，无法训练稳定的ARIMA预测模型")

    model_values = list(values)
    dropped_tail_points = 0
    if len(values) >= 12:
        recent_complete = values[-5:-1]
        recent_baseline = median(recent_complete)
        if recent_baseline > 0 and values[-1] < recent_baseline * 0.25 and len(values) - 1 >= 8:
            model_values = values[:-1]
            dropped_tail_points = 1

    captured_warnings: list[str] = []
    mae: float | None = None
    mape: float | None = None
    backtest_window = 0

    def relevant_warning_messages(caught: list[warnings.WarningMessage]) -> list[str]:
        messages = [str(item.message) for item in caught]
        return [message for message in messages if "deprecated" not in message.lower()]

    if len(model_values) > horizon + 8:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            backtest_model = ARIMA(model_values[:-horizon], order=order).fit()
            backtest_predictions = [float(value) for value in backtest_model.forecast(horizon)]
            captured_warnings.extend(relevant_warning_messages(caught))
        actual_values = model_values[-horizon:]
        abs_errors = [abs(actual - predicted) for actual, predicted in zip(actual_values, backtest_predictions)]
        pct_errors = [abs(actual - predicted) / actual for actual, predicted in zip(actual_values, backtest_predictions) if actual > 0]
        mae = sum(abs_errors) / len(abs_errors) if abs_errors else None
        mape = sum(pct_errors) / len(pct_errors) if pct_errors else None
        backtest_window = horizon

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fitted = ARIMA(model_values, order=order).fit()
        forecast_result = fitted.get_forecast(steps=horizon)
        captured_warnings.extend(relevant_warning_messages(caught))

    predictions = [float(value) for value in forecast_result.predicted_mean]
    confidence_intervals = forecast_result.conf_int(alpha=0.05)
    last_week = dates[-1]
    forecast = []
    for step in range(1, horizon + 1):
        yhat = max(0.0, predictions[step - 1])
        lower = max(0.0, float(confidence_intervals[step - 1][0]))
        upper = max(lower, float(confidence_intervals[step - 1][1]))
        forecast.append(
            {
                "week_start": (last_week + timedelta(days=7 * step)).isoformat(),
                "model": "ARIMA",
                "yhat": round(yhat, 2),
                "yhat_lower": round(lower, 2),
                "yhat_upper": round(upper, 2),
            }
        )
    diagnostics = {
        "model": "ARIMA",
        "order": list(order),
        "point_count": len(values),
        "training_point_count": len(model_values),
        "dropped_tail_points": dropped_tail_points,
        "backtest_window": backtest_window,
        "mae": round(mae, 2) if mae is not None else None,
        "mape": round(mape, 4) if mape is not None else None,
        "warnings": captured_warnings,
    }
    return forecast, diagnostics
