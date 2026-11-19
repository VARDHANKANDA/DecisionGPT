"""Independent verification of forecast_study_v2 results (Phase K). Imports NOTHING from the study package (only numpy/pandas/scipy/stdlib): targets are rebuilt from the raw files, the 31 baselines are
re-implemented from their written specification (EXPERIMENT_PROTOCOL.md section 6) and evaluated row by row with explicit access to the cutoff history only, every metric / effect size / interval /
decision is recomputed, and the file-order and hash checks are repeated.

    python research/forecast_study_v2/verify_independent.py [W2 W3 W1 ...]    ->  results/verification/independent_verification_<window>.json   (exit 1 on any failed check)

Added AFTER the freeze (it does not generate or alter any result); logged in DEVIATIONS.md.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
RES = STUDY / "results"
RAW = ROOT / "data" / "external" / "m5_forecasting" / "raw"
OR2 = ROOT / "data" / "external" / "uci_online_retail_ii" / "processed" / "online_retail_ii_raw_as_csv.csv"
NON_PRODUCT = {"ADJUST", "AMAZONFEE", "B", "BANK CHARGES", "C2", "CRUK", "D", "DOT", "GIFT", "M", "PADS", "POST", "S", "TEST001", "TEST002"}
STORE = {"m5_ca1": "CA_1", "m5_tx1": "TX_1", "m5_wi1": "WI_1"}
OFFSET = {"W1": 0, "W2": 252, "W3": 504}
EST = ("naive", "seasonal_naive", "weekday_mean4", "weekday_mean8", "weekday_median4", "weekday_median8", "trailing_mean28", "trailing_mean91", "trailing_median14", "trailing_median28",
       "trailing_median56", "trailing_median91", "croston", "croston_sba", "tsb", "zero")
_cache: dict = {}


# ---------------------------------------------------------------------------------------------------------------------------- raw data
def m5_matrix(store, ids):
    if "m5" not in _cache:
        _cache["m5"] = pd.read_csv(RAW / "sales_train_evaluation.csv", usecols=lambda c: c in ("id", "store_id") or c.startswith("d_"))
    df = _cache["m5"]
    df = df[df["store_id"] == store].set_index("id")
    return df.loc[ids, [f"d_{i}" for i in range(1, 1942)]].to_numpy(dtype=float)


def or2_matrix(Tp):
    if "or2" not in _cache:
        raw = pd.read_csv(OR2, dtype={"Invoice": str, "StockCode": str}, parse_dates=["InvoiceDate"])
        c = raw[~raw["Invoice"].str.startswith("C") & (raw["Quantity"] > 0) & (raw["Price"] > 0) & ~raw["StockCode"].isin(NON_PRODUCT)]
        c = c[~c.duplicated(["Invoice", "StockCode", "Quantity", "InvoiceDate", "Price", "Customer ID"])].copy()
        c["day"] = c["InvoiceDate"].dt.normalize()
        c["rev"] = c["Quantity"] * c["Price"]
        _cache["or2"] = (c, pd.date_range(c["day"].min(), c["day"].max(), freq="D"))
    c, full = _cache["or2"]
    first_val = Tp - 252
    top = c[c["day"] < full[first_val]].groupby("StockCode")["rev"].sum().sort_values(ascending=False, kind="mergesort").head(100).index.tolist()
    cut = full[Tp] if Tp < len(full) else full[-1] + pd.Timedelta(days=1)
    u = c[c["StockCode"].isin(top) & (c["day"] < cut)].groupby(["StockCode", "day"])["Quantity"].sum().unstack(fill_value=0).reindex(index=top, columns=full[:Tp], fill_value=0)
    return u.to_numpy(dtype=float), top


# ---------------------------------------------------------------------------------------------------------------------------- baselines (explicit cutoff access)
def croston_state(y, sba):
    z, p, q, seen = 0.0, 1.0, 1.0, False
    out = np.zeros(len(y))
    for t, v in enumerate(y):
        if v > 0:
            if not seen:
                z, p, seen = v, q, True
            else:
                z += 0.1 * (v - z)
                p += 0.1 * (q - p)
            q = 1.0
        else:
            q += 1.0
        out[t] = ((0.95 if sba else 1.0) * z / max(p, 1e-12)) if seen else 0.0
    return out


def tsb_state(y):
    z, prob, seen = 0.0, 0.0, False
    out = np.zeros(len(y))
    for t, v in enumerate(y):
        d = 1.0 if v > 0 else 0.0
        if d and not seen:
            z, prob, seen = v, 1.0 / (1.0 + t), True
        elif seen:
            if d:
                z += 0.1 * (v - z)
            prob += 0.1 * (d - prob)
        out[t] = prob * z if seen else 0.0
    return out


def baseline_for_day(Y, t, c, name, st):
    """Forecast (all series) of baseline ``name`` for target day t from information up to day c only."""
    hist = Y[:, : c + 1]                                      # nothing after the cutoff is reachable
    k = math.ceil((t - c) / 7)
    src = [t - 7 * (k + i) for i in range(8)]
    if name == "zero":
        return np.zeros(Y.shape[0])
    if name == "naive":
        return hist[:, c]
    if name == "seasonal_naive":
        return hist[:, src[0]] if src[0] >= 0 else np.full(Y.shape[0], np.nan)
    if name.startswith("weekday_"):
        n = int(name[-1])
        if src[n - 1] < 0:
            return np.full(Y.shape[0], np.nan)
        v = hist[:, src[:n]]
        return v.mean(axis=1) if "mean" in name else np.median(v, axis=1)
    if name.startswith("trailing_mean") or name.startswith("trailing_median"):
        w = int(name.split("n")[-1]) if False else int("".join(ch for ch in name if ch.isdigit()))
        if c + 1 < w:
            return np.full(Y.shape[0], np.nan)
        v = hist[:, c - w + 1: c + 1]
        return v.mean(axis=1) if name.startswith("trailing_mean") else np.median(v, axis=1)
    return st[name][:, c]


def make_states(Y):
    return {"croston": np.vstack([croston_state(r, False) for r in Y]), "croston_sba": np.vstack([croston_state(r, True) for r in Y]), "tsb": np.vstack([tsb_state(r) for r in Y])}


def cutoff(t, H, kind, blocks):
    if kind == "matched":
        return t - H
    o = max(b for b in blocks if b <= t)
    return (o - 1) if H >= 28 else (o + 7 * ((t - o) // 7) - 1)


# ---------------------------------------------------------------------------------------------------------------------------- metrics and inference (own code)
def wape(y, p):
    return float(np.abs(p - y).sum() / np.abs(y).sum())


def subset_day(y, p, d):
    e = pd.Series(p - y).groupby(d).sum()
    t = pd.Series(y).groupby(d).sum()
    return float(np.abs(e).sum() / np.abs(t).sum())


def item_week(y, p, s, d, day0):
    g = pd.DataFrame({"s": s, "w": (d - day0) // 7, "y": y, "p": p}).groupby(["s", "w"]).sum()
    return float(np.abs(g["p"] - g["y"]).sum() / np.abs(g["y"]).sum())


def cells(s, d, y, p, S, day0):
    W = int((d.max() - day0) // 7) + 1
    N = np.bincount(s * W + (d - day0) // 7, weights=np.abs(p - y), minlength=S * W).reshape(S, W)
    return N


def cgm(Na, Nb):
    S, W = Na.shape
    A, Bm = Na.sum(), Nb.sum()
    th = 1 - Bm / A
    u = -(Nb - (Bm / A) * Na) / A
    v = (u.sum(axis=1) ** 2).sum() + (u.sum(axis=0) ** 2).sum() - (u ** 2).sum()
    se = math.sqrt(max(v, 1e-30))
    G = min(S, W)
    t = stats.t.ppf(0.975, G - 1)
    return th, [th - t * se, th + t * se], float(2 * (1 - stats.t.cdf(abs(th / se), G - 1)))


def pigeonhole(Na, Nb, B=4000, seed=777):
    rng = np.random.default_rng(seed)
    S, W = Na.shape
    Cs = np.stack([np.bincount(rng.integers(0, S, S), minlength=S) for _ in range(B)])
    Cw = np.stack([np.bincount(rng.integers(0, W, W), minlength=W) for _ in range(B)])
    d = 1 - np.einsum("bw,bw->b", Cs @ Nb, Cw) / np.einsum("bw,bw->b", Cs @ Na, Cw)
    th = 1 - Nb.sum() / Na.sum()
    p = min(1.0, 2 * min((np.sum(d <= 0) + 1) / (B + 1), (np.sum(d >= 0) + 1) / (B + 1)))
    return th, [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))], float(p)


def weekboot(wa, wb, B=4000, seed=555):
    rng = np.random.default_rng(seed)
    W = len(wa)
    idx = rng.integers(0, W, (B, W))
    d = 1 - wb[idx].sum(axis=1) / wa[idx].sum(axis=1)
    th = 1 - wb.sum() / wa.sum()
    p = min(1.0, 2 * min((np.sum(d <= 0) + 1) / (B + 1), (np.sum(d >= 0) + 1) / (B + 1)))
    return th, [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))], float(p)


def holm(p):
    it = sorted(((k, v) for k, v in p.items()), key=lambda kv: kv[1])
    m, run, out = len(it), 0.0, {}
    for i, (k, v) in enumerate(it):
        run = max(run, min(1.0, (m - i) * v))
        out[k] = run
    return out


def verdict(est, lo, hi, hp, wins):
    if lo > 0 and est >= 0.02 and wins >= 4 and hp < 0.05:
        return "SUPPORTED"
    return "CONTRADICTED" if hi < 0 else "INCONCLUSIVE"


# ---------------------------------------------------------------------------------------------------------------------------- per cell
def verify_cell(window, key, H):
    d_ = STUDY / "results" / window / f"{key}_H{H}"
    z = np.load(d_ / "predictions.npz")
    A = {k: z[k] for k in z.files}
    sel = json.loads((d_ / "selection.json").read_text(encoding="utf-8"))
    res = json.loads((d_ / "results.json").read_text(encoding="utf-8"))
    meta = json.loads((d_ / "metadata.json").read_text(encoding="utf-8"))
    cfg = json.loads((d_ / "config.json").read_text(encoding="utf-8"))
    y, s, t, blk = A["y"].astype(float), A["series"].astype(int), A["day"].astype(int), A["block"].astype(int)
    out = {"cell": f"{window}/{key}_H{H}", "n_rows": int(len(y)), "checks": []}

    def chk(name, ok, detail=""):
        out["checks"].append({"check": name, "passed": bool(ok), "detail": str(detail)[:200]})

    # ---- targets from raw
    if key in STORE:
        T_full = 1941
        Tp = T_full - OFFSET[window]
        Y = m5_matrix(STORE[key], meta["series_ids"])[:, :Tp]
    else:
        Tp = 739 - OFFSET[window]
        Y, top = or2_matrix(Tp)
        chk("Online Retail II SKU list rederived from raw transactions equals the stored list", top == meta["series_ids"])
    chk("evaluation targets equal the raw data", np.array_equal(Y[s, t], y), f"max diff {np.abs(Y[s, t] - y).max()}")
    chk("no test day at or after the first unused day", t.max() < Tp, f"last test day {t.max()} < {Tp}")
    chk("stored row set: unique (series, day) pairs", len(set(zip(s.tolist(), t.tolist()))) == len(y))
    blocks_test = res["blocks"]["test"]
    chk("six 28-day test blocks end at the last day of the truncated series", blocks_test[-1] + 28 == Tp and all(blocks_test[i] + 28 == blocks_test[i + 1] for i in range(5)))
    chk("validation blocks end before the first test block", res["blocks"]["val"][-1] + 28 == blocks_test[0])
    # ---- baselines row by row (all 31)
    st = make_states(Y)
    n_bad = {}
    for kind in ("matched", "fresh"):
        starts = res["blocks"]["val"] + res["blocks"]["test"]
        for name in EST:
            if name == "zero" and kind == "fresh":
                continue
            mine = np.empty(len(y))
            for day in np.unique(t):
                c = cutoff(int(day), H, kind, starts)
                v = baseline_for_day(Y, int(day), c, name, st)
                m = t == day
                mine[m] = v[s[m]]
            sto = A[f"base__{kind}__{name}"].astype(float)
            n_bad[f"{kind}__{name}"] = int((np.abs(mine - sto) > 1e-4 + 1e-5 * np.abs(sto)).sum())
    chk("all 31 stored baselines equal the independent re-implementation (explicit cutoff access)", sum(n_bad.values()) == 0, {k: v for k, v in n_bad.items() if v})
    # ---- metrics
    day0 = blocks_test[0]
    S = res["n_series"]
    worst = 0.0
    for name in [k for k in A if k.startswith(("pred__", "base__", "seed"))]:
        p = A[name].astype(float)
        sm = res["summary"][name]
        mine = {"item_day_wape": wape(y, p), "subset_day_wape": subset_day(y, p, t), "item_week_wape": item_week(y, p, s, t, day0), "rel_bias": float((p - y).sum() / y.sum()), "mae": float(np.abs(p - y).mean()), "rmse": float(np.sqrt(((p - y) ** 2).mean()))}
        for k, v in mine.items():
            worst = max(worst, abs(v - sm[k]))
    chk("every stored method's item-day, item-week, subset-day WAPE, bias, MAE, RMSE equals the independent value (max abs diff)", worst < 1e-9, worst)
    chk("all-zero baseline has item-day WAPE 1", abs(wape(y, A["base__matched__zero"].astype(float)) - 1.0) < 1e-12)
    # ---- hypotheses
    P = lambda n: A[f"pred__{n}"].astype(float)  # noqa: E731
    Bm = lambda n: A[f"base__{n}"].astype(float)  # noqa: E731
    mi, ma, ref = sel["model_item_day"], sel["model_subset_day"], sel["reference_model"]
    est = {}
    for h, (a, b) in {"H1": (Bm(sel["baseline_item_day_matched"]), P(mi)), "H1b": (Bm(sel["baseline_item_day_any"]), P(mi)), "H2": (P(ref), P(mi))}.items():
        if h == "H2" and mi == ref:
            continue
        Na, Nb = cells(s, t, y, a, S, day0), cells(s, t, y, b, S, day0)
        th1, ci1, p1 = pigeonhole(Na, Nb)
        th2, ci2, p2 = cgm(Na, Nb)
        wins = sum(wape(y[blk == o], b[blk == o]) < wape(y[blk == o], a[blk == o]) for o in blocks_test)
        est[h] = {"improvement": float(th1), "ci_pigeonhole": ci1, "p_pigeonhole": p1, "ci_cgm_t": ci2, "p_cgm_t": p2, "blocks_won": int(wins)}
    a, b = Bm(sel["baseline_subset_day_matched"]), P(ma)
    days = np.unique(t)
    def dtot(p):
        tot = np.zeros(len(days)); np.add.at(tot, np.searchsorted(days, t), p - y); return np.abs(tot)
    wk = (days - day0) // 7
    W = int(wk.max()) + 1
    wa, wb = np.bincount(wk, weights=dtot(a), minlength=W), np.bincount(wk, weights=dtot(b), minlength=W)
    th, ci, p = weekboot(wa, wb)
    wins3 = sum(subset_day(y[blk == o], b[blk == o], t[blk == o]) < subset_day(y[blk == o], a[blk == o], t[blk == o]) for o in blocks_test)
    est["H3"] = {"improvement": float(th), "ci_iid_week": ci, "p_iid_week": p, "blocks_won": int(wins3)}
    out["independent_estimates"] = est
    out["selection_before_test"] = {"results_json_flag": res.get("test_fits_after_selection")}
    fits = [f.stat().st_mtime for f in (d_ / "fits").glob("test_*.npy")]
    chk("selection.json is older than every test fit file", bool(fits) and min(fits) >= (d_ / "selection.json").stat().st_mtime)
    chk("config hash in selection equals the config hash of the run", sel["config_hash"] == cfg["config_hash"] == meta["config_hash"])
    chk("validation-only selection re-derived: model_item_day and model_subset_day are the argmin of the stored validation means", (
        min(sorted(sel["validation"]["models_item_day_wape"]), key=lambda k: (sel["validation"]["models_item_day_wape"][k]["mean"], k)) == mi
        and min(sorted(sel["validation"]["models_subset_day_wape"]), key=lambda k: (sel["validation"]["models_subset_day_wape"][k]["mean"], k)) == ma))
    chk("leakage perturbation checks recorded in the validation stage all passed", all(x.get("history_features_unchanged_when_future_is_perturbed", True) for x in sel["leakage_checks"]))
    out["n_failed"] = sum(not c["passed"] for c in out["checks"])
    return out


def verify_window(window):
    cellsd = []
    for key in ("m5_ca1", "m5_tx1", "m5_wi1", "or2"):
        for H in (28, 7):
            if (STUDY / "results" / window / f"{key}_H{H}" / "results.json").exists():
                cellsd.append((key, H))
    per = {f"{k}_H{H}": verify_cell(window, k, H) for k, H in cellsd}
    # independent Holm and verdicts per family
    fam_out = {}
    for h in ("H1", "H1b", "H2", "H3"):
        pk = {"H3": "p_iid_week"}.get(h, "p_pigeonhole")
        ps = {c: v["independent_estimates"][h][pk] for c, v in per.items() if h in v["independent_estimates"]}
        if not ps:
            continue
        adj = holm(ps)
        fam_out[h] = {}
        for c in ps:
            e = per[c]["independent_estimates"][h]
            ci = e.get("ci_pigeonhole") or e.get("ci_iid_week")
            fam_out[h][c] = {"improvement": e["improvement"], "holm_p": adj[c], "verdict_independent_primary": verdict(e["improvement"], ci[0], ci[1], adj[c], e["blocks_won"])}
    out = {"window": window, "cells": per, "families": fam_out, "freeze": None}
    # compare with the study's own analysis file when present
    af = STUDY / "results" / "analysis" / f"analysis_{window}.json"
    cmp = []
    if af.exists():
        an = json.loads(af.read_text(encoding="utf-8"))
        for h, rows in fam_out.items():
            for c, r in rows.items():
                s = an["cells"][c][h]
                cmp.append({"cell": c, "hypothesis": h, "study_improvement": s.get("improvement"), "independent_improvement": r["improvement"], "abs_diff": abs(s["improvement"] - r["improvement"]) if "improvement" in s else None,
                            "study_verdict": s.get("verdict"), "independent_primary_verdict": r["verdict_independent_primary"], "verdict_agrees": s.get("verdict") == r["verdict_independent_primary"]})
    out["comparison_with_study_analysis"] = cmp
    out["n_cell_checks_failed"] = sum(v["n_failed"] for v in per.values())
    fz = STUDY / "FREEZE.json"
    rec = json.loads(fz.read_text(encoding="utf-8"))
    out["freeze"] = {"files": len(rec["sha256"]), "changed_since_freeze": [k for k, v in rec["sha256"].items() if (ROOT / k).exists() and hashlib.sha256((ROOT / k).read_bytes()).hexdigest() != v]}
    (STUDY / "results" / "verification").mkdir(parents=True, exist_ok=True)
    (STUDY / "results" / "verification" / f"independent_verification_{window}.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    return out


if __name__ == "__main__":
    bad = 0
    for w in sys.argv[1:] or ["W2", "W3", "W1"]:
        r = verify_window(w)
        n = sum(len(v["checks"]) for v in r["cells"].values())
        print(f"{w}: {len(r['cells'])} cells, {n - r['n_cell_checks_failed']}/{n} checks passed; verdict disagreements: {sum(1 for c in r['comparison_with_study_analysis'] if not c['verdict_agrees'])}; frozen files changed: {r['freeze']['changed_since_freeze']}")
        bad += r["n_cell_checks_failed"] + sum(1 for c in r["comparison_with_study_analysis"] if not c["verdict_agrees"])
    sys.exit(1 if bad else 0)
