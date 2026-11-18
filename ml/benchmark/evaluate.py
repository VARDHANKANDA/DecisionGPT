"""Scale-aware metrics and paired uncertainty for forecast comparisons.

Definitions (documented in docs/ML_BENCHMARK_REPORT.md):
  * WAPE = sum |e| / sum y. Undefined (``None``) when sum y == 0 - never reported as 0.
  * RMSSE per series = sqrt(mean e^2 / mean (y_t - y_{t-1})^2 over the training history); series whose history is constant
    (denominator 0) are excluded and counted. Aggregate RMSSE is the unweighted mean over valid series.
  * bias = sum e / sum y (signed; positive means over-forecast).
Paired comparisons use the SAME (series, day) pairs; uncertainty is a series-cluster bootstrap (series are the independent units;
days within a series are dependent), so overlapping intervals are never read as a test.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def wape(y: np.ndarray, p: np.ndarray) -> float | None:
    d = float(np.sum(np.abs(y)))
    return float(np.sum(np.abs(p - y)) / d) if d > 0 else None


def metrics(y: np.ndarray, p: np.ndarray, series_idx: np.ndarray, scale: dict[int, float] | None = None) -> dict[str, Any]:
    """Aggregate and per-series summary. ``y``/``p`` are flat; ``series_idx`` gives the series of every element."""
    e = p - y
    out: dict[str, Any] = {
        "n_points": int(len(y)), "n_series": int(len(np.unique(series_idx))),
        "mae": float(np.mean(np.abs(e))), "rmse": float(np.sqrt(np.mean(e ** 2))),
        "wape": wape(y, p), "bias": float(np.sum(e) / np.sum(y)) if np.sum(y) > 0 else None,
        "zero_share": float(np.mean(y == 0)),
    }
    per = []
    rms = []
    excluded = 0
    for s in np.unique(series_idx):
        m = series_idx == s
        ys, ps = y[m], p[m]
        w = wape(ys, ps)
        if w is not None:
            per.append(w)
        if scale is not None:
            sc = scale.get(int(s))
            if sc and sc > 0:
                rms.append(float(np.sqrt(np.mean((ps - ys) ** 2) / sc)))
            else:
                excluded += 1
    out["median_series_wape"] = float(np.median(per)) if per else None
    out["series_with_defined_wape"] = len(per)
    if scale is not None:
        out["rmsse_mean"] = float(np.mean(rms)) if rms else None
        out["rmsse_series_excluded_constant_history"] = excluded
    return out


def series_scale(y_hist: np.ndarray) -> dict[int, float]:
    """In-sample one-step naive MSE per series (RMSSE denominator), from training history only."""
    d = np.diff(y_hist, axis=1)
    sc = np.mean(d ** 2, axis=1)
    return {i: float(v) for i, v in enumerate(sc)}


def paired_cluster_bootstrap(y: np.ndarray, p_a: np.ndarray, p_b: np.ndarray, series_idx: np.ndarray, draws: int = 2000,
                             seed: int = 42, stat: str = "wape") -> dict[str, Any]:
    """Difference (A - B) in WAPE (or MAE) on identical points, resampling whole series. Negative = A better."""
    rng = np.random.default_rng(seed)
    ids = np.unique(series_idx)
    abs_a = np.zeros(len(ids))
    abs_b = np.zeros(len(ids))
    ysum = np.zeros(len(ids))
    cnt = np.zeros(len(ids))
    for k, s in enumerate(ids):
        m = series_idx == s
        abs_a[k] = np.sum(np.abs(p_a[m] - y[m]))
        abs_b[k] = np.sum(np.abs(p_b[m] - y[m]))
        ysum[k] = np.sum(y[m])
        cnt[k] = m.sum()

    def stat_fn(sel):
        if stat == "wape":
            d = ysum[sel].sum()
            return (abs_a[sel].sum() - abs_b[sel].sum()) / d if d > 0 else np.nan
        return (abs_a[sel].sum() - abs_b[sel].sum()) / cnt[sel].sum()

    point = stat_fn(np.arange(len(ids)))
    if len(ids) < 8:  # a single (or a handful of) series: resampling series is meaningless and 4 weekly blocks would be fabricated precision
        return {"statistic": stat, "difference_a_minus_b": float(point), "ci95": None, "share_of_draws_a_better": None,
                "n_series": int(len(ids)), "draws": 0,
                "method": "point difference only: fewer than 8 independent series, so no interval is reported"}
    boots = np.array([stat_fn(rng.integers(0, len(ids), len(ids))) for _ in range(draws)])
    boots = boots[~np.isnan(boots)]
    return {"statistic": stat, "difference_a_minus_b": float(point),
            "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "share_of_draws_a_better": float(np.mean(boots < 0)), "n_series": int(len(ids)), "draws": int(len(boots)),
            "method": "series-cluster bootstrap on identical (series, day) pairs"}
