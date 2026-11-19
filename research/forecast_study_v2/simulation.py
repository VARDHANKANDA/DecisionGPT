"""Inference simulations of forecast_study_v2 (synthetic data only; run BEFORE the freeze; no real outcome is involved).

Q1. Item-day endpoint. Cell totals N_a[s,w], N_b[s,w] (absolute errors of the baseline and the model, summed over series s and 7-day block w) are simulated with series effects, week effects,
    week-specific shocks that hit the two methods differently, series-specific gains and cell noise, with a KNOWN true relative improvement g = 1 - E[N_b]/E[N_a]. Candidate 95% interval methods
    for theta = 1 - sum(N_b)/sum(N_a):
      PH   crossed (pigeonhole) percentile bootstrap: series and weeks resampled independently (B draws)
      CGMt two-way cluster-robust delta-method variance (Cameron-Gelbach-Miller) with a t(G-1) reference, G = min(#series, #weeks)
      CGMz the same variance with a normal reference
      SO   series-only bootstrap (the historical design), for contrast
    Pre-specified selection rule: the PRIMARY method is the one with the smallest worst-case absolute coverage error |coverage - 0.95| over the grid (ties -> PH). All methods are reported.
Q2. Subset-day endpoint. Daily total errors with AR(1) dependence; ratio of sums over 168 days; week-block bootstrap variants (iid weeks, stationary bootstrap with mean block 3 weeks, circular
    block of 3 weeks) compared the same way.

    python -m research.forecast_study_v2.simulation
"""
from __future__ import annotations

import itertools
import json
import math

import numpy as np
from scipy import stats

from .common import RESULTS, atomic_write_json

SEED = 20261023


def theta_draws(Na, Nb, B, rng, mode="crossed"):
    S, W = Na.shape
    Cs = np.zeros((B, S))
    Cw = np.zeros((B, W))
    for b in range(B):
        Cs[b] = np.bincount(rng.integers(0, S, S), minlength=S) if mode in ("crossed", "series") else np.ones(S)
        Cw[b] = np.bincount(rng.integers(0, W, W), minlength=W) if mode in ("crossed", "week") else np.ones(W)
    na = np.einsum("bw,bw->b", Cs @ Na, Cw)
    nb = np.einsum("bw,bw->b", Cs @ Nb, Cw)
    return 1.0 - nb / na


def cgm(Na, Nb):
    A, Bm = Na.sum(), Nb.sum()
    theta = 1.0 - Bm / A
    u = -(Nb - (Bm / A) * Na) / A
    v = (u.sum(axis=1) ** 2).sum() + (u.sum(axis=0) ** 2).sum() - (u ** 2).sum()
    return theta, math.sqrt(max(v, 1e-30))


def simulate_cells(rng, S, W, g, s_alpha, s_beta, s_delta, s_eta, s_zeta=0.3):
    a, b = rng.normal(0, s_alpha, (S, 1)), rng.normal(0, s_beta, (1, W))
    Na = np.exp(a + b + rng.normal(0, 0.3, (S, W)))
    rho = (1 - g) * np.exp(rng.normal(0, s_eta, (S, 1)) + rng.normal(0, s_delta, (1, W)) + rng.normal(0, s_zeta, (S, W)) - (s_eta ** 2 + s_delta ** 2 + s_zeta ** 2) / 2)
    return Na, Na * rho


def q1(reps=400, B=1000):
    rng = np.random.default_rng(SEED)
    grid = list(itertools.product((100, 350), (0.0, 0.03), (0.05, 0.15, 0.40), (0.1, 0.3)))
    out = {"grid": []}
    for S, g, s_delta, s_eta in grid:
        hit = {m: 0 for m in ("PH", "CGMt", "CGMz", "SO")}
        rej = {m: 0 for m in hit}
        W = 24
        G = min(S, W)
        tcrit = stats.t.ppf(0.975, G - 1)
        for _ in range(reps):
            Na, Nb = simulate_cells(rng, S, W, g, 1.0, 0.3, s_delta, s_eta)
            th, se = cgm(Na, Nb)
            ph = theta_draws(Na, Nb, B, rng, "crossed")
            so = theta_draws(Na, Nb, B, rng, "series")
            cis = {"PH": tuple(np.percentile(ph, [2.5, 97.5])), "SO": tuple(np.percentile(so, [2.5, 97.5])), "CGMz": (th - 1.959964 * se, th + 1.959964 * se), "CGMt": (th - tcrit * se, th + tcrit * se)}
            for m, (lo, hi) in cis.items():
                hit[m] += lo <= g <= hi
                if g == 0.0:
                    rej[m] += not (lo <= 0.0 <= hi)
        out["grid"].append({"series": S, "weeks": W, "true_gain": g, "week_shock_sd": s_delta, "series_gain_sd": s_eta, "reps": reps, "B": B,
                            "coverage95": {m: hit[m] / reps for m in hit}, "type_I_error_at_5pct_when_gain_is_0": ({m: rej[m] / reps for m in rej} if g == 0.0 else None)})
        print("Q1", out["grid"][-1]["series"], g, s_delta, s_eta, {m: round(v, 3) for m, v in out["grid"][-1]["coverage95"].items()}, flush=True)
    worst = {m: max(abs(r["coverage95"][m] - 0.95) for r in out["grid"]) for m in ("PH", "CGMt", "CGMz", "SO")}
    mean_cov = {m: float(np.mean([r["coverage95"][m] for r in out["grid"]])) for m in worst}
    primary = min(("PH", "CGMt", "CGMz"), key=lambda m: (round(worst[m], 4), m != "PH"))
    out.update({"worst_case_abs_coverage_error": worst, "mean_coverage": mean_cov, "primary_method_by_rule": primary})
    return out


def _ar1(rng, n, rho):
    from scipy.signal import lfilter

    return lfilter([1.0], [1.0, -rho], rng.normal(size=n))


def week_block_indices(rng, W, kind, mean_block=3):
    if kind == "iid":
        return rng.integers(0, W, W)
    if kind == "circular_block":
        starts = rng.integers(0, W, math.ceil(W / mean_block))
        return np.concatenate([(s + np.arange(mean_block)) % W for s in starts])[:W]
    restart = rng.random(W) < 1.0 / mean_block                       # stationary bootstrap: geometric block lengths with mean ``mean_block``
    restart[0] = True
    seg = np.cumsum(restart) - 1
    first_pos = np.flatnonzero(restart)
    start = rng.integers(0, W, len(first_pos))
    return (start[seg] + (np.arange(W) - first_pos[seg])) % W


def q2(reps=300, B=500):
    rng = np.random.default_rng(SEED + 1)
    out = {"grid": []}
    W = 24
    for rho, g in itertools.product((0.0, 0.3, 0.6), (0.0, 0.1)):
        hit = {k: 0 for k in ("iid", "circular_block", "stationary")}
        rej = {k: 0 for k in hit}
        tt = _true_theta(rng, rho, g)
        for _ in range(reps):
            err_a, err_b = _gen(rng, W * 7, rho, g)
            dA, dB = err_a.reshape(W, 7).sum(axis=1), err_b.reshape(W, 7).sum(axis=1)
            th = 1 - dB.sum() / dA.sum()
            for kind in hit:
                dr = np.empty(B)
                for b in range(B):
                    ix = week_block_indices(rng, W, kind)
                    dr[b] = 1 - dB[ix].sum() / dA[ix].sum()
                lo, hi = np.percentile(dr, [2.5, 97.5])
                hit[kind] += lo <= tt <= hi
                if g == 0.0:
                    rej[kind] += not (lo <= 0.0 <= hi)
        out["grid"].append({"ar1_rho": rho, "true_gain": g, "true_theta": tt, "reps": reps, "B": B, "coverage95": {k: hit[k] / reps for k in hit}, "type_I_error_at_5pct_when_gain_is_0": ({k: rej[k] / reps for k in rej} if g == 0.0 else None)})
        print("Q2", rho, g, {k: round(v, 3) for k, v in out["grid"][-1]["coverage95"].items()}, flush=True)
    worst = {k: max(abs(r["coverage95"][k] - 0.95) for r in out["grid"]) for k in ("iid", "circular_block", "stationary")}
    out.update({"worst_case_abs_coverage_error": worst, "primary_method_by_rule": min(worst, key=lambda k: (round(worst[k], 4), k != "stationary"))})
    return out


def _gen(rng, days, rho, g):
    lev = 100 + 20 * _ar1(rng, days, rho)
    err_a = np.abs(_ar1(rng, days, rho) * 8 + 0.30 * lev)
    err_b = np.abs(_ar1(rng, days, rho) * 8 + 0.30 * (1 - g) * lev)
    return err_a, err_b


def _true_theta(rng, rho, g):
    a, b = _gen(rng, 2_000_000, rho, g)
    return float(1 - b.mean() / a.mean())          # the population ratio the interval should cover


def main():
    res = {"seed": SEED, "q1_item_day": q1(), "q2_subset_day": q2()}
    atomic_write_json(RESULTS / "simulation_inference.json", res)
    print("Q1 primary:", res["q1_item_day"]["primary_method_by_rule"], res["q1_item_day"]["worst_case_abs_coverage_error"])
    print("Q2 primary:", res["q2_subset_day"]["primary_method_by_rule"], res["q2_subset_day"]["worst_case_abs_coverage_error"])


if __name__ == "__main__":
    main()
