"""Confirmatory analysis of forecast_study_v2 (frozen with the protocol). Reads stored predictions only.

Hypotheses (per cell = dataset x minimum lag H; EXPERIMENT_PROTOCOL.md section 5)
  H1   the model selected on validation ITEM-DAY WAPE beats the best-validation MATCHED-information baseline in pooled item-day WAPE        (family F1)
  H1b  the same against the best-validation baseline of ANY information set                                                              (family F1b)
  H2   the same model beats the original reference model (LightGBM, Tweedie p=1.1, refit on the same window) in pooled item-day WAPE        (family F2)   [objective effect]
  H3   the model selected on validation SUBSET-DAY WAPE beats the best-validation matched baseline (selected on subset-day WAPE) in subset-day WAPE   (family F3)
Estimand: relative improvement (E_ref - E_model) / E_ref of the endpoint error E; positive = the model is better. Minimum relevant improvement 2 %.
Decision per cell: SUPPORTED iff Holm-adjusted p < 0.05 AND the 95 % interval excludes 0 AND improvement >= 2 % AND the model wins >= 4 of the 6 test blocks;
                   CONTRADICTED iff the 95 % interval lies below 0 (not multiplicity-adjusted); otherwise INCONCLUSIVE. Holm is applied across the cells of a family within a window.
Inference
  item-day endpoints : paired crossed bootstrap over series and 7-day target blocks (B=10000), and a two-way cluster-robust delta-method interval with a t(G-1) reference (G = min(series, weeks));
                       the PRIMARY method is fixed in PRIMARY_ITEM_DAY below from the pre-freeze simulation rule; both are always reported and a disagreement of the verdict is flagged.
  subset-day endpoint: bootstrap over 7-day blocks of daily totals (series are aggregated away), method fixed in PRIMARY_SUBSET_DAY below; the stationary block bootstrap is the secondary method.
Dual-method rule (pre-specified after the pre-freeze simulation showed both methods mildly liberal): the final verdict is the primary verdict only if the secondary method, applied with the same rule
(and its own Holm adjustment), gives the same verdict; otherwise the verdict is INCONCLUSIVE and both are reported.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy import stats

from . import metrics as mt
from .common import RESULTS, atomic_write_json

B_BOOT = 10000
SEED_BOOT = 20261024
MIN_GAIN = 0.02
PRIMARY_ITEM_DAY = "PH"          # fixed after the pre-freeze simulation (results/simulation_inference.json); see EXPERIMENT_PROTOCOL.md section 7
PRIMARY_SUBSET_DAY = "iid"
MEAN_BLOCK_WEEKS = 3
CONF_WINDOW = "W2"
CELL_KEYS = [("m5_ca1", 28), ("m5_ca1", 7), ("m5_tx1", 28), ("m5_tx1", 7), ("m5_wi1", 28), ("m5_wi1", 7), ("or2", 28), ("or2", 7)]


def load_cell(window: str, key: str, H: int):
    d = RESULTS / window / f"{key}_H{H}"
    z = np.load(d / "predictions.npz")
    return {k: z[k] for k in z.files}, json.loads((d / "selection.json").read_text(encoding="utf-8")), json.loads((d / "results.json").read_text(encoding="utf-8"))


def cell_totals(series, day, y, p, S, day0):
    W = int((day.max() - day0) // 7) + 1
    idx = series.astype(np.int64) * W + (day - day0) // 7
    N = np.bincount(idx, weights=np.abs(p - y), minlength=S * W).reshape(S, W)
    return N, W


def _improvement_counts(Na, Nb, Cs, Cw):
    a = np.einsum("bw,bw->b", Cs @ Na, Cw)
    b = np.einsum("bw,bw->b", Cs @ Nb, Cw)
    return 1.0 - b / a


def crossed_bootstrap(Na, Nb, B=B_BOOT, seed=SEED_BOOT, rows=None):
    """Paired crossed bootstrap of theta = 1 - sum(Nb)/sum(Na). ``rows`` restricts the series dimension (segment analysis)."""
    rng = np.random.default_rng(seed)
    S0, W = Na.shape
    idx = np.arange(S0) if rows is None else np.asarray(rows)
    S = len(idx)
    Na_, Nb_ = Na[idx], Nb[idx]
    Cs = np.empty((B, S))
    Cw = np.empty((B, W))
    for b in range(B):
        Cs[b] = np.bincount(rng.integers(0, S, S), minlength=S)
        Cw[b] = np.bincount(rng.integers(0, W, W), minlength=W)
    d = _improvement_counts(Na_, Nb_, Cs, Cw)
    th = 1.0 - Nb_.sum() / Na_.sum()
    k_le, k_ge = int((d <= 0).sum()), int((d >= 0).sum())
    p = min(1.0, 2 * min((k_le + 1) / (B + 1), (k_ge + 1) / (B + 1)))
    return {"estimate": float(th), "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))], "p": p, "B": B, "method": "crossed bootstrap (series x 7-day blocks)"}


def cgm_t(Na, Nb, rows=None):
    idx = np.arange(Na.shape[0]) if rows is None else np.asarray(rows)
    Na_, Nb_ = Na[idx], Nb[idx]
    S, W = Na_.shape
    A, Bm = Na_.sum(), Nb_.sum()
    th = 1.0 - Bm / A
    u = -(Nb_ - (Bm / A) * Na_) / A
    v = (u.sum(axis=1) ** 2).sum() + (u.sum(axis=0) ** 2).sum() - (u ** 2).sum()
    se = math.sqrt(max(v, 1e-30))
    G = min(S, W)
    t = stats.t.ppf(0.975, G - 1)
    return {"estimate": float(th), "ci95": [float(th - t * se), float(th + t * se)], "p": float(2 * (1 - stats.t.cdf(abs(th / se), G - 1))), "se": se, "df": G - 1, "method": "two-way cluster-robust delta method, t(G-1)"}


def week_block_idx(rng, W, kind):
    if kind == "iid":
        return rng.integers(0, W, W)
    restart = rng.random(W) < 1.0 / MEAN_BLOCK_WEEKS
    restart[0] = True
    seg = np.cumsum(restart) - 1
    first_pos = np.flatnonzero(restart)
    start = rng.integers(0, W, len(first_pos))
    return (start[seg] + (np.arange(W) - first_pos[seg])) % W


def week_bootstrap(dA, dB, kind=PRIMARY_SUBSET_DAY, B=B_BOOT, seed=SEED_BOOT):
    rng = np.random.default_rng(seed)
    W = len(dA)
    d = np.empty(B)
    for b in range(B):
        ix = week_block_idx(rng, W, kind)
        d[b] = 1.0 - dB[ix].sum() / dA[ix].sum()
    th = 1.0 - dB.sum() / dA.sum()
    k_le, k_ge = int((d <= 0).sum()), int((d >= 0).sum())
    return {"estimate": float(th), "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))], "p": min(1.0, 2 * min((k_le + 1) / (B + 1), (k_ge + 1) / (B + 1))), "B": B,
            "method": f"{kind} bootstrap over 7-day blocks of daily totals"}


def holm(p: dict) -> dict:
    items = sorted(((k, v) for k, v in p.items() if v is not None), key=lambda kv: kv[1])
    m, run, out = len(items), 0.0, {}
    for i, (k, v) in enumerate(items):
        run = max(run, min(1.0, (m - i) * v))
        out[k] = run
    return {k: out.get(k) for k in p}


def verdict(est, lo, hi, holm_p, wins) -> str:
    if lo is not None and lo > 0 and est >= MIN_GAIN and wins >= 4 and holm_p is not None and holm_p < 0.05:
        return "SUPPORTED"
    if hi is not None and hi < 0:
        return "CONTRADICTED"
    return "INCONCLUSIVE"


def _blocks_won(y, a, b, block, order):
    """Number of test blocks in which method b has the lower pooled item-day WAPE than a (a = reference)."""
    return sum(1 for o in order if mt.wape(y[block == o], b[block == o]) < mt.wape(y[block == o], a[block == o]))


def _blocks_won_subset(y, a, b, block, day, order):
    return sum(1 for o in order if mt.subset_day_wape(y[block == o], b[block == o], day[block == o]) < mt.subset_day_wape(y[block == o], a[block == o], day[block == o]))


def analyse_cell(window: str, key: str, H: int) -> dict:
    A, sel, res = load_cell(window, key, H)
    y, s, d, blk = A["y"].astype(float), A["series"].astype(int), A["day"].astype(int), A["block"].astype(int)
    S = int(res["n_series"])
    order = res["blocks"]["test"]
    day0 = order[0]
    m_item, m_agg, ref_model = sel["model_item_day"], sel["model_subset_day"], sel["reference_model"]
    P = lambda n: A[f"pred__{n}"].astype(float)  # noqa: E731
    Bm = lambda n: A[f"base__{n}"].astype(float)  # noqa: E731
    out: dict = {"window": window, "dataset": key, "H": H, "n_rows": int(len(y)), "selection": {k: sel[k] for k in ("model_item_day", "model_subset_day", "reference_model", "baseline_item_day_matched", "baseline_item_day_any", "baseline_subset_day_matched")}}

    def item_cmp(ref, mod, label):
        Na, W = cell_totals(s, d, y, ref, S, day0)
        Nb, _ = cell_totals(s, d, y, mod, S, day0)
        ph = crossed_bootstrap(Na, Nb)
        cg = cgm_t(Na, Nb)
        prim = ph if PRIMARY_ITEM_DAY == "PH" else cg
        wins = _blocks_won(y, ref, mod, blk, order)
        return {"label": label, "wape_reference": mt.wape(y, ref), "wape_model": mt.wape(y, mod), "improvement": prim["estimate"], "primary": prim, "crossed_bootstrap": ph, "cgm_t": cg, "blocks_won": int(wins), "n_weekly_blocks": int(W)}

    out["H1"] = item_cmp(Bm(sel["baseline_item_day_matched"]), P(m_item), "model(item-day) vs best matched baseline")
    out["H1b"] = item_cmp(Bm(sel["baseline_item_day_any"]), P(m_item), "model(item-day) vs best baseline of any information set")
    if m_item == ref_model:
        out["H2"] = {"label": "model(item-day) vs reference Tweedie model", "not_applicable": "the validation-selected model IS the reference configuration"}
    else:
        out["H2"] = item_cmp(P(ref_model), P(m_item), "model(item-day) vs reference Tweedie model (p=1.1) refit on the same window")
    # H3: subset-day endpoint
    refb = Bm(sel["baseline_subset_day_matched"])
    pm = P(m_agg)
    day_sets = np.unique(d)
    wk = (day_sets - day0) // 7

    def daily_abs_totals(p):
        tot = np.zeros(len(day_sets))
        np.add.at(tot, np.searchsorted(day_sets, d), p - y)
        return np.abs(tot)

    dA, dB = daily_abs_totals(refb), daily_abs_totals(pm)
    W = int(wk.max()) + 1
    wA, wB = np.bincount(wk, weights=dA, minlength=W), np.bincount(wk, weights=dB, minlength=W)
    h3 = week_bootstrap(wA, wB, PRIMARY_SUBSET_DAY)
    h3b = week_bootstrap(wA, wB, "stationary")
    out["H3"] = {"label": "model(subset-day) vs best matched baseline on subset-day WAPE", "wape_reference": mt.subset_day_wape(y, refb, d), "wape_model": mt.subset_day_wape(y, pm, d), "improvement": h3["estimate"], "primary": h3,
                 "secondary": h3b, "blocks_won": int(_blocks_won_subset(y, refb, pm, blk, d, order)), "n_weekly_blocks": W}
    # descriptive ladder for the selected models and baselines
    out["ladder"] = {n: res["summary"][n] for n in res["summary"] if n.startswith("pred__") or n in (f"base__{sel['baseline_item_day_matched']}", f"base__{sel['baseline_item_day_any']}", f"base__{sel['baseline_subset_day_matched']}", "base__matched__zero")}
    # endpoint dependence (descriptive)
    out["endpoint_dependence"] = {"item_day_improvement_vs_matched": out["H1"]["improvement"], "subset_day_improvement_vs_matched": out["H3"]["improvement"],
                                  "reversed": bool(np.sign(out["H1"]["improvement"]) != np.sign(out["H3"]["improvement"]))}
    # seed sensitivity (descriptive)
    seeds = [k for k in A if k.startswith("seed")]
    if seeds:
        Nb0 = cell_totals(s, d, y, Bm(sel["baseline_item_day_matched"]), S, day0)[0]
        out["seed_sensitivity"] = {"seed42": out["H1"]["improvement"], **{k.split("__")[0]: float(1.0 - cell_totals(s, d, y, A[k].astype(float), S, day0)[0].sum() / Nb0.sum()) for k in seeds}}
    # exploratory segments (item-day, vs matched baseline)
    seg = res["segments"]
    Na, W = cell_totals(s, d, y, Bm(sel["baseline_item_day_matched"]), S, day0)
    Nb, _ = cell_totals(s, d, y, P(m_item), S, day0)
    segs = {}
    for dim in ("frequency", "volume"):
        lab = np.array(seg[dim])
        for v in sorted(set(lab.tolist())):
            idx = np.flatnonzero(lab == v)
            if len(idx) >= 20:
                r = crossed_bootstrap(Na, Nb, B=2000, rows=idx)
                segs[f"{dim}={v}"] = {"n_series": int(len(idx)), "improvement": r["estimate"], "ci95": r["ci95"]}
            else:
                segs[f"{dim}={v}"] = {"n_series": int(len(idx)), "note": "fewer than 20 series: not estimated"}
    out["segments_exploratory"] = segs
    return out


def analyse_window(window: str, cells=None) -> dict:
    cells = cells or CELL_KEYS
    per = {}
    for key, H in cells:
        if (RESULTS / window / f"{key}_H{H}" / "results.json").exists():
            per[f"{key}_H{H}"] = analyse_cell(window, key, H)
    fam = {}
    for h in ("H1", "H1b", "H2", "H3"):
        raw = {c: (per[c][h]["primary"]["p"] if "primary" in per[c][h] else None) for c in per}
        sec_key = "secondary" if h == "H3" else "cgm_t"
        raw2 = {c: (per[c][h][sec_key]["p"] if sec_key in per[c][h] else None) for c in per}
        adj, adj2 = holm(raw), holm(raw2)
        fam[h] = adj
        for c in per:
            r = per[c][h]
            if "primary" not in r:
                continue
            r["holm_p"] = adj[c]
            lo, hi = r["primary"]["ci95"]
            r["verdict_primary_method"] = verdict(r["improvement"], lo, hi, adj[c], r["blocks_won"])
            lo2, hi2 = r[sec_key]["ci95"]
            r["holm_p_secondary"] = adj2[c]
            r["verdict_secondary_method"] = verdict(r["improvement"], lo2, hi2, adj2[c], r["blocks_won"])
            r["methods_agree_on_verdict"] = bool(r["verdict_primary_method"] == r["verdict_secondary_method"])
            r["verdict"] = r["verdict_primary_method"] if r["methods_agree_on_verdict"] else "INCONCLUSIVE"
    out = {"window": window, "cells": per, "holm_adjusted_p": fam, "primary_method_item_day": PRIMARY_ITEM_DAY, "primary_method_subset_day": PRIMARY_SUBSET_DAY, "B": B_BOOT, "min_gain": MIN_GAIN}
    atomic_write_json(RESULTS / "analysis" / f"analysis_{window}.json", out)
    return out


if __name__ == "__main__":
    import sys

    for w in sys.argv[1:] or [CONF_WINDOW]:
        r = analyse_window(w)
        for c, v in r["cells"].items():
            print(w, c, {h: (round(v[h]["improvement"], 4), v[h].get("verdict")) for h in ("H1", "H1b", "H2", "H3") if "improvement" in v[h]})
