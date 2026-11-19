"""Metric definitions for the study. Every function states its undefined-case policy; undefined results are ``None`` (never 0, never an epsilon-floored value).

Pooled metrics sum over every evaluated (series, day) cell; per-series metrics are computed per series and then summarised. Pooled and per-series values
answer different questions and are never mixed in one comparison.

  wape(y, p)            sum|p - y| / sum(y). None when sum(y) = 0.
  mae, rmse             mean absolute / root mean squared error, in the units of y.
  rel_bias(y, p)        sum(p - y) / sum(y); positive = over-forecast. None when sum(y) = 0.
  rmsse(y, p, scale)    sqrt(mean e^2 / scale), scale = mean((y_t - y_{t-1})^2) over the TRAINING history of the series (supplied by the caller).
                        None when scale = 0 (constant history); such series are excluded and counted by ``rmsse_mean``.
  rmsse_mean            unweighted mean of per-series RMSSE over series with scale > 0 (+ the number excluded).
  aggregate_wape        WAPE after summing all series per day (store-day aggregate level).
  mape                  NOT provided: actuals are zero on a large share of days, so no defensible denominator policy exists for these data.
"""
from __future__ import annotations

import numpy as np


def wape(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    d = float(np.sum(np.abs(y)))
    return float(np.sum(np.abs(p - y)) / d) if d > 0 else None


def mae(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.mean(np.abs(p - y))) if y.size else None


def rmse(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.sqrt(np.mean((p - y) ** 2))) if y.size else None


def rel_bias(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    d = float(np.sum(np.abs(y)))
    return float(np.sum(p - y) / d) if d > 0 else None


def series_scale(history: np.ndarray) -> np.ndarray:
    """Per-series RMSSE denominator from training history ``[series, days]``: mean squared one-step difference. 0 for constant history."""
    d = np.diff(np.asarray(history, float), axis=1)
    return np.mean(d * d, axis=1)


def rmsse_mean(y, p, series, scale):
    """Unweighted mean of per-series RMSSE; returns (value or None, n_series_used, n_series_excluded)."""
    y, p, series = np.asarray(y, float), np.asarray(p, float), np.asarray(series)
    vals, excluded = [], 0
    for s in np.unique(series):
        m = series == s
        sc = float(scale[int(s)])
        if sc > 0:
            vals.append(float(np.sqrt(np.mean((p[m] - y[m]) ** 2) / sc)))
        else:
            excluded += 1
    return (float(np.mean(vals)) if vals else None), len(vals), excluded


def aggregate_wape(y, p, day):
    y, p, day = np.asarray(y, float), np.asarray(p, float), np.asarray(day)
    days = np.unique(day)
    ya = np.array([y[day == d].sum() for d in days])
    pa = np.array([p[day == d].sum() for d in days])
    return wape(ya, pa)


def summary(y, p, series, day, scale=None) -> dict:
    out = {"n_points": int(len(y)), "n_series": int(np.unique(series).size), "zero_share": float(np.mean(np.asarray(y) == 0)), "mae": mae(y, p), "rmse": rmse(y, p),
           "wape": wape(y, p), "rel_bias": rel_bias(y, p), "aggregate_wape": aggregate_wape(y, p, day)}
    if scale is not None:
        v, used, excl = rmsse_mean(y, p, series, scale)
        out.update({"rmsse_mean": v, "rmsse_series_used": used, "rmsse_series_excluded": excl})
    return out
