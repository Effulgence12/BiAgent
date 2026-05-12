"""Forecasting utilities for the Agentic BI project."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from math import sqrt
import warnings

from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tools.sm_exceptions import ConvergenceWarning


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
    """Forecast the next six weekly GMV points with ETS confidence intervals."""
    forecast, _diagnostics = forecast_sales_6_weeks_with_diagnostics(points)
    return forecast


def forecast_sales_6_weeks_with_diagnostics(points: Sequence[dict[str, object]]) -> tuple[list[dict[str, float | str]], dict[str, object]]:
    """Forecast weekly GMV with ETS and expose model diagnostics.

    使用任务书认可的时间序列方法 ETS/指数平滑。所有输入来自真实
    `mv_weekly_sales`，模型失败时抛出真实错误，不生成模拟序列。
    """
    values: list[float] = []
    dates: list[date] = []
    for point in points:
        try:
            values.append(float(point["total_gmv"]))
            dates.append(date.fromisoformat(str(point["week_start"])[:10]))
        except (KeyError, TypeError, ValueError):
            continue
    if not values:
        return [], {"model": "ETS", "point_count": 0, "warnings": ["没有可用周GMV序列"]}
    if len(values) < 8:
        raise ValueError("真实周GMV序列不足8周，无法训练稳定的ETS预测模型")
    model = ExponentialSmoothing(values, trend="add", seasonal=None, initialization_method="estimated")
    captured_warnings: list[str] = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        fitted = model.fit(optimized=True)
        captured_warnings = [str(item.message) for item in caught if issubclass(item.category, ConvergenceWarning)]
    fitted_values = list(fitted.fittedvalues)
    residuals = [actual - fitted_value for actual, fitted_value in zip(values, fitted_values)]
    residual_std = sqrt(sum(residual * residual for residual in residuals) / max(len(residuals) - 1, 1))
    recent = list(zip(values[-12:], fitted_values[-12:]))
    abs_errors = [abs(actual - fitted_value) for actual, fitted_value in recent]
    pct_errors = [abs(actual - fitted_value) / actual for actual, fitted_value in recent if actual > 0]
    mae = sum(abs_errors) / len(abs_errors) if abs_errors else 0.0
    mape = sum(pct_errors) / len(pct_errors) if pct_errors else 0.0
    predictions = [max(0.0, float(value)) for value in fitted.forecast(6)]
    last_week = dates[-1]
    forecast = []
    for step, yhat in enumerate(predictions, start=1):
        band = max(residual_std * 1.96, yhat * 0.05)
        forecast.append(
            {
                "week_start": (last_week + timedelta(days=7 * step)).isoformat(),
                "model": "ETS",
                "yhat": round(yhat, 2),
                "yhat_lower": round(max(0.0, yhat - band), 2),
                "yhat_upper": round(yhat + band, 2),
            }
        )
    diagnostics = {
        "model": "ETS",
        "point_count": len(values),
        "backtest_window": len(abs_errors),
        "mae": round(mae, 2),
        "mape": round(mape, 4),
        "warnings": captured_warnings,
    }
    return forecast, diagnostics
