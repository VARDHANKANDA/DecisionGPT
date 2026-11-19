"""Dependence-aware uncertainty for paired forecast comparisons, multiplicity control and split-conformal intervals.

**Why not a series-only bootstrap.** Series in one store share calendar days (events, SNAP days, closures), store-level shocks, and each series has strong
weekly seasonality, so both the cross-section and time are dependent. Cells ``(series s, 7-day target block w)`` are therefore resampled in a *crossed* way: a
bootstrap draw selects series with replacement AND, independently, week blocks with replacement, and recomputes the pooled statistic on the selected
sub-matrix (Kunsch 1989 block resampling in time; cluster resampling over series). This is an approximation (independent two-way resampling), documented as such; the
stationary bootstrap over weeks (Politis & Romano 1994, mean block length ``mean_block`` weeks) is provided as a sensitivity analysis.

Statistics are pooled ratios of sums, so each draw is a ratio of resampled sums (a ratio estimator), not a mean of ratios.
"""
from __future__ import annotations

import math

import numpy as np


# ---- cell matrices -------------------------------------------------------------------------------------------------------------------------
def cell_matrices(series: np.ndarray, day: np.ndarray, y: np.ndarray, preds: dict[str, np.ndarray], n_series: int, day0: int, block: int = 7):
    """Sum of |error| (per method) and of actuals on the ``[series, week-block]`` grid. ``day0`` is the first target day; blocks are ``block`` days long."""
    w = (day - day0) // block
    W = int(w.max()) + 1
    flat = series * W + w
    size = n_series * W
    D = np.bincount(flat, weights=np.abs(y), minlength=size).reshape(n_series, W)
    N = {k: np.bincount(flat, weights=np.abs(p - y), minlength=size).reshape(n_series, W) for k, p in preds.items()}
    # signed error and squared error are needed for bias / RMSE style statistics
    SE = {k: np.bincount(flat, weights=(p - y), minlength=size).reshape(n_series, W) for k, p in preds.items()}
    cnt = np.bincount(flat, minlength=size).reshape(n_series, W)
    return {"D": D, "N": N, "SE": SE, "cnt": cnt, "W": W}


def _rel_improvement(Na, Nb, D, si, wi):
    """(WAPE_a - WAPE_b) / WAPE_a on the selected sub-grid: positive = b (the model) has the lower error."""
    d = D[np.ix_(si, wi)].sum()
    if d <= 0:
        return np.nan
    wa = Na[np.ix_(si, wi)].sum() / d
    wb = Nb[np.ix_(si, wi)].sum() / d
    return (wa - wb) / wa if wa > 0 else np.nan


def crossed_bootstrap(Na: np.ndarray, Nb: np.ndarray, D: np.ndarray, B: int = 2000, seed: int = 20261022, series_subset: np.ndarray | None = None) -> dict:
    """Paired, crossed series x week-block bootstrap of the relative WAPE improvement of b over a (positive = b better) and of the WAPE difference.

    ``series_subset`` restricts the series dimension (segment analysis): resampling happens within the subset.
    """
    rng = np.random.default_rng(seed)
    S, W = D.shape
    idx = np.arange(S) if series_subset is None else np.asarray(series_subset)
    n = len(idx)
    pt = _rel_improvement(Na, Nb, D, idx, np.arange(W))
    dpt = (Na[idx].sum() - Nb[idx].sum()) / max(D[idx].sum(), 1e-12)
    draws = np.empty(B)
    ddraws = np.empty(B)
    for b in range(B):
        si = idx[rng.integers(0, n, n)]
        wi = rng.integers(0, W, W)
        draws[b] = _rel_improvement(Na, Nb, D, si, wi)
        den = D[np.ix_(si, wi)].sum()
        ddraws[b] = (Na[np.ix_(si, wi)].sum() - Nb[np.ix_(si, wi)].sum()) / den if den > 0 else np.nan
    return _summarise(pt, draws) | {"wape_diff_point": float(dpt), "wape_diff_ci95": _ci(ddraws), "n_series": int(n), "n_blocks": int(W), "B": B, "method": "crossed series x 7-day-block bootstrap"}


def stationary_bootstrap_weeks(Na, Nb, D, B: int = 2000, mean_block: float = 3.0, seed: int = 20261023) -> dict:
    """Sensitivity: series resampled with replacement; week blocks resampled by the stationary bootstrap (geometric block lengths, mean ``mean_block`` weeks)."""
    rng = np.random.default_rng(seed)
    S, W = D.shape
    pt = _rel_improvement(Na, Nb, D, np.arange(S), np.arange(W))
    p = 1.0 / mean_block
    draws = np.empty(B)
    for b in range(B):
        si = rng.integers(0, S, S)
        wi = np.empty(W, dtype=int)
        wi[0] = rng.integers(0, W)
        for j in range(1, W):
            wi[j] = rng.integers(0, W) if rng.random() < p else (wi[j - 1] + 1) % W
        draws[b] = _rel_improvement(Na, Nb, D, si, wi)
    return _summarise(pt, draws) | {"method": f"series bootstrap x stationary week bootstrap (mean block {mean_block} weeks)", "B": B}


def series_only_bootstrap(Na, Nb, D, B: int = 2000, seed: int = 20261024) -> dict:
    """The historical design (series-cluster only), reported next to the crossed version to show how much the dependence matters."""
    rng = np.random.default_rng(seed)
    S, W = D.shape
    allw = np.arange(W)
    pt = _rel_improvement(Na, Nb, D, np.arange(S), allw)
    draws = np.array([_rel_improvement(Na, Nb, D, rng.integers(0, S, S), allw) for _ in range(B)])
    return _summarise(pt, draws) | {"method": "series-cluster bootstrap only (historical design)", "B": B}


def _ci(draws, lo=2.5, hi=97.5):
    d = draws[~np.isnan(draws)]
    return [float(np.percentile(d, lo)), float(np.percentile(d, hi))] if d.size else [None, None]


def _summarise(point, draws):
    d = draws[~np.isnan(draws)]
    if not d.size:
        return {"estimate": None, "ci95": [None, None], "p_two_sided": None}
    p_le = float(np.mean(d <= 0))
    p_ge = float(np.mean(d >= 0))
    return {"estimate": float(point), "ci95": _ci(draws), "p_two_sided": float(min(1.0, 2 * min(p_le, p_ge))), "boot_mean": float(d.mean()), "boot_se": float(d.std(ddof=1)),
            "n_valid_draws": int(d.size)}


# ---- multiplicity ---------------------------------------------------------------------------------------------------------------------------
def holm(pvals: dict[str, float | None]) -> dict[str, float | None]:
    """Holm (1979) step-down adjusted p-values. Undefined p-values stay undefined and are not counted."""
    items = [(k, v) for k, v in pvals.items() if v is not None]
    items.sort(key=lambda kv: kv[1])
    m = len(items)
    adj, running = {}, 0.0
    for i, (k, v) in enumerate(items):
        running = max(running, min(1.0, (m - i) * v))
        adj[k] = running
    return {k: adj.get(k) for k in pvals}


# ---- Diebold-Mariano on a loss-differential series (store-day aggregate) -------------------------------------------------------------------
def diebold_mariano(loss_a: np.ndarray, loss_b: np.ndarray, h: int = 1) -> dict:
    """DM test of equal expected loss on one series of per-day losses, HAC variance (Bartlett, lag h-1). Positive stat = b has the smaller loss.
    Exploratory complement only: with short test series the normal approximation is optimistic."""
    d = np.asarray(loss_a, float) - np.asarray(loss_b, float)
    n = d.size
    if n < 8:
        return {"statistic": None, "p_two_sided": None, "n": int(n)}
    dm = d - d.mean()
    gamma0 = float(np.sum(dm * dm) / n)
    var = gamma0
    for k in range(1, max(h, 1)):
        w = 1.0 - k / h
        var += 2.0 * w * float(np.sum(dm[k:] * dm[:-k]) / n)
    var = max(var, 1e-18)
    stat = float(d.mean() / math.sqrt(var / n))
    p = float(math.erfc(abs(stat) / math.sqrt(2.0)))
    return {"statistic": stat, "p_two_sided": p, "n": int(n), "mean_loss_diff": float(d.mean())}


# ---- split conformal -----------------------------------------------------------------------------------------------------------------------
def conformal_quantile(abs_residuals: np.ndarray, level: float) -> float | None:
    """Finite-sample split-conformal quantile: the ceil((n+1)*level)-th smallest absolute residual. None if there are too few residuals."""
    r = np.sort(np.asarray(abs_residuals, float))
    n = r.size
    k = math.ceil((n + 1) * level)
    if n == 0 or k > n:
        return None
    return float(r[k - 1])


def mondrian_edges(pred_cal: np.ndarray, n_bins: int = 3) -> np.ndarray:
    """Bin edges from calibration predictions (quantiles), so that test predictions are binned by the SAME edges."""
    qs = np.linspace(0, 1, n_bins + 1)[1:-1]
    return np.quantile(pred_cal, qs)


def mondrian_conformal(pred_cal, y_cal, pred_test, level: float = 0.8, n_bins: int = 3) -> dict:
    """Absolute-residual split-conformal half-widths per prediction bin (Mondrian), calibrated on calibration data only. Returns half-widths for the test points."""
    edges = mondrian_edges(pred_cal, n_bins)
    bc = np.digitize(pred_cal, edges)
    bt = np.digitize(pred_test, edges)
    res = np.abs(np.asarray(y_cal, float) - np.asarray(pred_cal, float))
    q = np.full(n_bins, np.nan)
    for b in range(n_bins):
        v = conformal_quantile(res[bc == b], level)
        q[b] = np.nan if v is None else v
    return {"half_width": q[bt], "bin_quantiles": [None if np.isnan(x) else float(x) for x in q], "edges": [float(e) for e in edges], "n_cal": int(len(res))}


def interval_report(y, pred, half, mask=None) -> dict:
    """Coverage and width of [max(0, pred-half), pred+half]. Points with an undefined half-width are excluded and counted."""
    y, pred, half = np.asarray(y, float), np.asarray(pred, float), np.asarray(half, float)
    ok = ~np.isnan(half)
    if mask is not None:
        ok &= mask
    if not ok.any():
        return {"coverage": None, "mean_width": None, "relative_width": None, "n": 0}
    lo = np.maximum(0.0, pred[ok] - half[ok])
    hi = pred[ok] + half[ok]
    cov = float(np.mean((y[ok] >= lo) & (y[ok] <= hi)))
    width = float(np.mean(hi - lo))
    s = float(np.sum(np.abs(y[ok])))
    return {"coverage": cov, "mean_width": width, "relative_width": float(np.sum(hi - lo) / s) if s > 0 else None, "n": int(ok.sum()), "n_excluded": int((~ok).sum())}
