"""Simple forecasting baselines for the study, constructed so that a forecast for target day ``t`` depends ONLY on history up to a cutoff ``c(t) <= t - 1``.

Two information sets (both leak-free by construction; ``tests/research/test_forecast_study_baselines.py`` perturbs the future and checks):

* **matched**: cutoff ``c(t) = t - H``. Exactly the information the learned direct models may use (their features have minimum lag ``H``).
* **fresh**: cutoff = the last observed day before the retraining block (``H = 28``) or before the 7-day week containing ``t`` (``H = 7``).
  It is at least as recent as the matched cutoff (never later than ``t - 1``), so it is a stronger, operationally realistic reference.

All arrays are ``[series, day]`` and hold the forecast for target day ``day``; NaN marks "not enough history". Series are rows, days are columns.

Estimators
  naive              y[c]
  seasonal_naive     value one or more whole weeks before ``t``, the most recent such day that is <= c
  weekday_mean4/8    mean of the last 4 / 8 same-weekday values <= c
  trailing_mean28    mean of y[c-27..c]
  trailing_median28  median of y[c-27..c]
  croston_sba        Croston's method with the Syntetos-Boylan bias correction, smoothing 0.1
  tsb                Teunter-Syntetos-Babai method, demand-probability and size smoothing 0.1
"""
from __future__ import annotations

import math

import numpy as np

ALPHA = 0.1          # smoothing constant for Croston/SBA/TSB (a common convention; fixed before any evaluation, not tuned)
NAMES = ("naive", "seasonal_naive", "weekday_mean4", "weekday_mean8", "trailing_mean28", "trailing_median28", "croston_sba", "tsb")


# ---- recursive intermittent-demand states: state[:, e] is the forecast made after observing y[:, 0..e] -------------------------------------
def croston_sba_states(y: np.ndarray, alpha: float = ALPHA) -> np.ndarray:
    """Per-series SBA forecast after each day. Zero until the first demand occurs."""
    S, T = y.shape
    out = np.zeros((S, T), dtype=np.float64)
    z = np.zeros(S)          # smoothed demand size
    p = np.ones(S)           # smoothed inter-demand interval
    q = np.ones(S)           # periods since last demand (counting the current one)
    seen = np.zeros(S, dtype=bool)
    for t in range(T):
        d = y[:, t] > 0
        first = d & ~seen
        z = np.where(first, y[:, t], z)
        p = np.where(first, q, p)
        upd = d & seen
        z = np.where(upd, z + alpha * (y[:, t] - z), z)
        p = np.where(upd, p + alpha * (q - p), p)
        seen |= d
        q = np.where(d, 1.0, q + 1.0)
        out[:, t] = np.where(seen, (1.0 - alpha / 2.0) * z / np.maximum(p, 1e-12), 0.0)
    return out


def tsb_states(y: np.ndarray, alpha: float = ALPHA, beta: float = ALPHA) -> np.ndarray:
    """Per-series TSB forecast after each day: P(demand) x smoothed size. Zero until the first demand."""
    S, T = y.shape
    out = np.zeros((S, T), dtype=np.float64)
    z = np.zeros(S)
    prob = np.zeros(S)
    seen = np.zeros(S, dtype=bool)
    for t in range(T):
        d = y[:, t] > 0
        first = d & ~seen
        z = np.where(first, y[:, t], z)
        prob = np.where(first, 1.0 / (1.0 + t), prob)    # first-demand initialisation: observed frequency so far
        z = np.where(d & seen, z + alpha * (y[:, t] - z), z)
        prob = np.where(seen, prob + beta * (d.astype(float) - prob), prob)
        seen |= d
        out[:, t] = np.where(seen, prob * z, 0.0)
    return out


def _rolling_mean(y: np.ndarray, w: int) -> np.ndarray:
    """out[:, e] = mean of y[:, e-w+1..e]; NaN before w days exist."""
    S, T = y.shape
    cs = np.concatenate([np.zeros((S, 1)), np.cumsum(y.astype(np.float64), axis=1)], axis=1)
    out = np.full((S, T), np.nan)
    if T >= w:
        out[:, w - 1:] = (cs[:, w:] - cs[:, : T - w + 1]) / w
    return out


def _rolling_median(y: np.ndarray, w: int) -> np.ndarray:
    S, T = y.shape
    out = np.full((S, T), np.nan)
    if T >= w:
        view = np.lib.stride_tricks.sliding_window_view(y.astype(np.float32), w, axis=1)      # [S, T-w+1, w]
        out[:, w - 1:] = np.median(view, axis=2)
    return out


def _lag(y: np.ndarray, k: int) -> np.ndarray:
    """out[:, t] = y[:, t-k] (NaN for t < k)."""
    out = np.full(y.shape, np.nan)
    if k < y.shape[1]:
        out[:, k:] = y[:, : y.shape[1] - k]
    return out


# ---- matched-information baselines -------------------------------------------------------------------------------------------------------
def matched(y: np.ndarray, H: int) -> dict[str, np.ndarray]:
    """Forecast for day t using only y[..t-H]."""
    y = np.asarray(y, dtype=np.float64)
    k0 = math.ceil(H / 7)
    lags = [_lag(y, 7 * (k0 + i)) for i in range(8)]
    out = {
        "naive": _lag(y, H),
        "seasonal_naive": lags[0],
        "weekday_mean4": np.mean(np.stack(lags[:4]), axis=0),
        "weekday_mean8": np.mean(np.stack(lags[:8]), axis=0),
        "trailing_mean28": _lag(_rolling_mean(y, 28), H),
        "trailing_median28": _lag(_rolling_median(y, 28), H),
        "croston_sba": _lag(croston_sba_states(y), H),
        "tsb": _lag(tsb_states(y), H),
    }
    return out


# ---- fresh-information baselines ---------------------------------------------------------------------------------------------------------
def cutoff_index(T: int, H: int, block_starts: list[int], block_len: int = 28) -> np.ndarray:
    """c(t) for every target day covered by a block; -1 elsewhere. H=28: last day before the block. H=7: last day before the week containing t."""
    c = np.full(T, -1, dtype=np.int64)
    for o in block_starts:
        for t in range(o, min(o + block_len, T)):
            c[t] = (o - 1) if H >= 28 else (o + 7 * ((t - o) // 7) - 1)
    return c


def fresh(y: np.ndarray, H: int, block_starts: list[int], block_len: int = 28) -> dict[str, np.ndarray]:
    """Forecast for day t using only y[..c(t)] with c(t) from :func:`cutoff_index`. NaN for days outside the blocks."""
    y = np.asarray(y, dtype=np.float64)
    S, T = y.shape
    c = cutoff_index(T, H, block_starts, block_len)
    st = {"croston_sba": croston_sba_states(y), "tsb": tsb_states(y), "trailing_mean28": _rolling_mean(y, 28), "trailing_median28": _rolling_median(y, 28)}
    out = {k: np.full((S, T), np.nan) for k in NAMES}
    for t in np.flatnonzero(c >= 0):
        cc = int(c[t])
        gap = t - cc                                           # 1..H
        k = math.ceil(gap / 7)                                 # whole weeks back so that the source day is <= cc
        src = [t - 7 * (k + i) for i in range(8)]
        out["naive"][:, t] = y[:, cc]
        out["seasonal_naive"][:, t] = y[:, src[0]] if src[0] >= 0 else np.nan
        out["weekday_mean4"][:, t] = y[:, src[:4]].mean(axis=1) if src[3] >= 0 else np.nan
        out["weekday_mean8"][:, t] = y[:, src[:8]].mean(axis=1) if src[7] >= 0 else np.nan
        for name in ("trailing_mean28", "trailing_median28", "croston_sba", "tsb"):
            out[name][:, t] = st[name][:, cc]
    return out
