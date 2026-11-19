"""Baselines of forecast_study_v2 (prespecified in EXPERIMENT_PROTOCOL.md), built so that the forecast for target day t depends only on history up to a cutoff c(t) <= t-1.

Information sets
  matched : c(t) = t - H  (exactly what the learned direct models may use)
  fresh   : c(t) = last day before the retraining block (H = 28) or before the 7-day week containing t (H = 7); never later than t-1 and never earlier than t-H

Estimators (16; 'zero' exists once, the others in both information sets)
  naive, seasonal_naive, weekday_mean4/8, weekday_median4/8, trailing_mean28/91, trailing_median14/28/56/91, croston (classic), croston_sba, tsb, zero

All arrays are [series, day]; NaN marks 'not enough history'. State-based estimators are causal: state[:, e] uses y[:, :e+1] only, so the arrays can be computed on the truncated series.
"""
from __future__ import annotations

import math

import numpy as np

ALPHA = 0.1
ESTIMATORS = ("naive", "seasonal_naive", "weekday_mean4", "weekday_mean8", "weekday_median4", "weekday_median8", "trailing_mean28", "trailing_mean91",
              "trailing_median14", "trailing_median28", "trailing_median56", "trailing_median91", "croston", "croston_sba", "tsb", "zero")
STATE_BASED = ("trailing_mean28", "trailing_mean91", "trailing_median14", "trailing_median28", "trailing_median56", "trailing_median91", "croston", "croston_sba", "tsb")


def _croston_states(y: np.ndarray, sba: bool, alpha: float = ALPHA) -> np.ndarray:
    S, T = y.shape
    out = np.zeros((S, T))
    z, p, q = np.zeros(S), np.ones(S), np.ones(S)
    seen = np.zeros(S, dtype=bool)
    corr = (1.0 - alpha / 2.0) if sba else 1.0
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
        out[:, t] = np.where(seen, corr * z / np.maximum(p, 1e-12), 0.0)
    return out


def _tsb_states(y: np.ndarray, alpha: float = ALPHA, beta: float = ALPHA) -> np.ndarray:
    S, T = y.shape
    out = np.zeros((S, T))
    z, prob = np.zeros(S), np.zeros(S)
    seen = np.zeros(S, dtype=bool)
    for t in range(T):
        d = y[:, t] > 0
        first = d & ~seen
        z = np.where(first, y[:, t], z)
        prob = np.where(first, 1.0 / (1.0 + t), prob)
        z = np.where(d & seen, z + alpha * (y[:, t] - z), z)
        prob = np.where(seen, prob + beta * (d.astype(float) - prob), prob)
        seen |= d
        out[:, t] = np.where(seen, prob * z, 0.0)
    return out


def rolling_mean(y: np.ndarray, w: int) -> np.ndarray:
    S, T = y.shape
    cs = np.concatenate([np.zeros((S, 1)), np.cumsum(y.astype(np.float64), axis=1)], axis=1)
    out = np.full((S, T), np.nan)
    if T >= w:
        out[:, w - 1:] = (cs[:, w:] - cs[:, : T - w + 1]) / w
    return out


def rolling_median(y: np.ndarray, w: int, chunk: int = 50) -> np.ndarray:
    S, T = y.shape
    out = np.full((S, T), np.nan)
    if T >= w:
        yf = y.astype(np.float32)
        for a in range(0, S, chunk):
            view = np.lib.stride_tricks.sliding_window_view(yf[a: a + chunk], w, axis=1)
            out[a: a + chunk, w - 1:] = np.median(view, axis=2)
    return out


def states(y: np.ndarray) -> dict[str, np.ndarray]:
    """State arrays of the state-based estimators computed on the (already truncated) series."""
    y = np.asarray(y, dtype=np.float64)
    return {"trailing_mean28": rolling_mean(y, 28), "trailing_mean91": rolling_mean(y, 91), "trailing_median14": rolling_median(y, 14), "trailing_median28": rolling_median(y, 28),
            "trailing_median56": rolling_median(y, 56), "trailing_median91": rolling_median(y, 91), "croston": _croston_states(y, sba=False), "croston_sba": _croston_states(y, sba=True), "tsb": _tsb_states(y)}


def _lag(a: np.ndarray, k: int) -> np.ndarray:
    out = np.full(a.shape, np.nan)
    if k < a.shape[1]:
        out[:, k:] = a[:, : a.shape[1] - k]
    return out


def matched(y: np.ndarray, H: int, st: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Forecast for day t from y[..t-H] only."""
    y = np.asarray(y, dtype=np.float64)
    k0 = math.ceil(H / 7)
    lags = [_lag(y, 7 * (k0 + i)) for i in range(8)]
    out = {"naive": _lag(y, H), "seasonal_naive": lags[0], "weekday_mean4": np.mean(np.stack(lags[:4]), axis=0), "weekday_mean8": np.mean(np.stack(lags[:8]), axis=0),
           "weekday_median4": np.median(np.stack(lags[:4]), axis=0), "weekday_median8": np.median(np.stack(lags[:8]), axis=0), "zero": np.zeros(y.shape)}
    for name in STATE_BASED:
        out[name] = _lag(st[name], H)
    return out


def cutoff_index(T: int, H: int, block_starts: list[int], block_len: int = 28) -> np.ndarray:
    c = np.full(T, -1, dtype=np.int64)
    for o in block_starts:
        for t in range(o, min(o + block_len, T)):
            c[t] = (o - 1) if H >= 28 else (o + 7 * ((t - o) // 7) - 1)
    return c


def fresh(y: np.ndarray, H: int, block_starts: list[int], st: dict[str, np.ndarray], block_len: int = 28) -> dict[str, np.ndarray]:
    y = np.asarray(y, dtype=np.float64)
    S, T = y.shape
    c = cutoff_index(T, H, block_starts, block_len)
    out = {k: np.full((S, T), np.nan) for k in ESTIMATORS}
    for t in np.flatnonzero(c >= 0):
        cc = int(c[t])
        k = math.ceil((t - cc) / 7)
        src = [t - 7 * (k + i) for i in range(8)]
        out["naive"][:, t] = y[:, cc]
        out["seasonal_naive"][:, t] = y[:, src[0]] if src[0] >= 0 else np.nan
        if src[3] >= 0:
            out["weekday_mean4"][:, t] = y[:, src[:4]].mean(axis=1)
            out["weekday_median4"][:, t] = np.median(y[:, src[:4]], axis=1)
        if src[7] >= 0:
            out["weekday_mean8"][:, t] = y[:, src[:8]].mean(axis=1)
            out["weekday_median8"][:, t] = np.median(y[:, src[:8]], axis=1)
        out["zero"][:, t] = 0.0
        for name in STATE_BASED:
            out[name][:, t] = st[name][:, cc]
    return out


def table(y: np.ndarray, H: int, block_starts: list[int], st: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """All prespecified baselines as {'matched__name' | 'fresh__name': [series, day]}; 'zero' appears once (as matched__zero)."""
    m = matched(y, H, st)
    f = fresh(y, H, block_starts, st)
    out = {f"matched__{k}": v for k, v in m.items()}
    out.update({f"fresh__{k}": v for k, v in f.items() if k != "zero"})
    return out
