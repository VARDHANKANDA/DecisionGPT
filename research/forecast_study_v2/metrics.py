"""Metric definitions of forecast_study_v2. Undefined results are None, never 0, never epsilon-floored. WAPE is NOT called accuracy.

Primary: pooled item-day WAPE = sum|yhat - y| / sum y over all eligible (series, day) rows. Positive relative bias = over-forecast.
Aggregation ladder (the same forecasts, sums taken BEFORE scoring):
  item-week   : sum each series over its 7-day target block, then WAPE over (series, week) cells
  subset-week : sum all series of the selected subset over each 7-day target block, then WAPE over weeks
  subset-day  : sum all series of the selected subset over each day, then WAPE over days
Subset-day WAPE >= |relative bias| (sum over days of |daily total error| >= |total error|).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def wape(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    d = float(np.abs(y).sum())
    return float(np.abs(p - y).sum() / d) if d > 0 else None


def rel_bias(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    d = float(np.abs(y).sum())
    return float((p - y).sum() / d) if d > 0 else None


def mae(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.abs(p - y).mean()) if y.size else None


def rmse(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.sqrt(((p - y) ** 2).mean())) if y.size else None


def subset_day_wape(y, p, day):
    y, p = np.asarray(y, float), np.asarray(p, float)
    e = pd.Series(p - y).groupby(day).sum()
    t = pd.Series(y).groupby(day).sum()
    d = float(np.abs(t).sum())
    return float(np.abs(e).sum() / d) if d > 0 else None


def _grouped(y, p, keys):
    df = pd.DataFrame({"y": y, "p": p, **keys})
    return df.groupby(list(keys)).sum()


def item_week_wape(y, p, series, day, day0):
    g = _grouped(np.asarray(y, float), np.asarray(p, float), {"s": series, "w": (np.asarray(day) - day0) // 7})
    d = float(np.abs(g["y"]).sum())
    return float(np.abs(g["p"] - g["y"]).sum() / d) if d > 0 else None


def subset_week_wape(y, p, day, day0):
    g = _grouped(np.asarray(y, float), np.asarray(p, float), {"w": (np.asarray(day) - day0) // 7})
    d = float(np.abs(g["y"]).sum())
    return float(np.abs(g["p"] - g["y"]).sum() / d) if d > 0 else None


def ladder(y, p, series, day, day0) -> dict:
    return {"item_day_wape": wape(y, p), "item_week_wape": item_week_wape(y, p, series, day, day0), "subset_week_wape": subset_week_wape(y, p, day, day0),
            "subset_day_wape": subset_day_wape(y, p, day), "rel_bias": rel_bias(y, p), "mae": mae(y, p), "rmse": rmse(y, p), "zero_forecast_share": float((np.asarray(p) == 0).mean())}
