"""Forecasting placeholder for the first runnable project skeleton."""

from __future__ import annotations

from collections.abc import Sequence


def naive_forecast(values: Sequence[float], periods: int = 6) -> list[float]:
    """Return a simple last-value forecast until Prophet is integrated."""
    if periods < 1:
        raise ValueError("periods must be at least 1")
    if not values:
        return [0.0] * periods
    return [float(values[-1])] * periods
