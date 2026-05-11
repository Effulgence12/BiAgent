"""Lightweight forecasting utilities for the Agentic BI project."""

from __future__ import annotations

from collections.abc import Sequence


def naive_forecast(values: Sequence[float], periods: int = 6) -> list[float]:
    """Return a simple last-value forecast for compatibility with earlier tests."""
    if periods < 1:
        raise ValueError("periods must be at least 1")
    if not values:
        return [0.0] * periods
    return [float(values[-1])] * periods


def linear_forecast(points: Sequence[dict[str, object]], value_key: str = "total_gmv", periods: int = 6) -> list[dict[str, float | int]]:
    """Forecast future values with a dependency-free linear trend baseline.

    Prophet can replace this function later, but this deterministic model keeps the
    project runnable in restricted environments.
    """
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
