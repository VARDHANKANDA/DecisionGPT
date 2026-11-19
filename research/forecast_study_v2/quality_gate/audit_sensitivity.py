"""R3 quality gate — READ-ONLY sensitivity and audit calculations on the stored v2 results (nothing in results/ is modified; outputs go to quality_gate/results/).

All analyses here are POST-HOC and EXPLORATORY/SUPPLEMENTARY unless stated; none replaces a frozen result.
  A  weekly dependence of the item-day comparison: lag-1 autocorrelation of the weekly differences and a crossed bootstrap whose week dimension is resampled in stationary blocks
     (mean 3 weeks), applied with the frozen decision rule (analysis.verdict, Holm within window) to H1 and H2 — a dependence-robust sensitivity analysis of the two methods that share an iid-week assumption
  B  validation-selection margins (how close were the selected model and its runner-up in the three validation blocks?)
  C  asymmetric (pinball) loss: does the item-day gain of the median-type model survive when under-forecasting is penalised more? (illustrative; no cost data exist)
  D  independent recomputation of headline point estimates from predictions.npz with code that does not import the study's metric code (cross-check of analysis_*.json)

    python research/forecast_study_v2/quality_gate/audit_sensitivity.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parents[1]))
from research.forecast_study_v2 import analysis as an  # noqa: E402  (read-only use of the frozen module: bootstrap helpers, Holm, verdict rule)

R = HERE / "results"
OUT = HERE / "quality_gate" / "results"
OUT.mkdir(parents=True, exist_ok=True)
WINDOWS = ("W2", "W3", "W1")
B = 10000
SEED = 7771234
TAUS = (0.5, 0.7, 0.8, 0.9)


def load(window, cell):
    d = R / window / cell
    z = np.load(d / "predictions.npz")
    res = json.loads((d / "results.json").read_text(encoding="utf-8"))
    sel = json.loads((d / "selection.json").read_text(encoding="utf-8"))
    return {k: z[k] for k in z.files}, res, sel


def totals(series, day, loss, S, day0):
    W = int((day.max() - day0) // 7) + 1
    N = np.bincount(series.astype(np.int64) * W + (day - day0) // 7, weights=loss, minlength=S * W).reshape(S, W)
    return N


def crossed_boot_stationary_weeks(Na, Nb, B=B, seed=SEED, mean_block=3.0):
    """Series resampled iid, weeks resampled in stationary blocks; same estimand and percentile/p-value convention as the frozen crossed bootstrap."""
    rng = np.random.default_rng(seed)
    S, W = Na.shape
    Cs, Cw = np.empty((B, S)), np.empty((B, W))
    for b in range(B):
        Cs[b] = np.bincount(rng.integers(0, S, S), minlength=S)
        restart = rng.random(W) < 1.0 / mean_block
        restart[0] = True
        seg = np.cumsum(restart) - 1
        first = np.flatnonzero(restart)
        start = rng.integers(0, W, len(first))
        Cw[b] = np.bincount((start[seg] + (np.arange(W) - first[seg])) % W, minlength=W)
    d = an._improvement_counts(Na, Nb, Cs, Cw)
    th = 1.0 - Nb.sum() / Na.sum()
    k_le, k_ge = int((d <= 0).sum()), int((d >= 0).sum())
    return {"estimate": float(th), "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))], "p": min(1.0, 2 * min((k_le + 1) / (B + 1), (k_ge + 1) / (B + 1)))}


def lag1(x):
    return float(np.corrcoef(x[:-1], x[1:])[0, 1])


def analysis_A():
    out = {}
    for w in WINDOWS:
        a = json.loads((R / "analysis" / f"analysis_{w}.json").read_text(encoding="utf-8"))["cells"]
        rows = {}
        for c, v in a.items():
            A_, res, sel = load(w, c)
            y, s, d = A_["y"].astype(float), A_["series"].astype(int), A_["day"].astype(int)
            S, day0 = int(res["n_series"]), res["blocks"]["test"][0]
            base = A_["base__" + sel["baseline_item_day_matched"]].astype(float)
            m = A_["pred__" + sel["model_item_day"]].astype(float)
            ref = A_["pred__" + sel["reference_model"]].astype(float)
            Na, Nb, Nr = (totals(s, d, np.abs(p - y), S, day0) for p in (base, m, ref))
            dw = (Na - Nb).sum(axis=0)
            rho = lag1(dw)
            r1 = crossed_boot_stationary_weeks(Na, Nb)
            r2 = crossed_boot_stationary_weeks(Nr, Nb, seed=SEED + 1) if sel["model_item_day"] != sel["reference_model"] else None
            rows[c] = {"lag1_weekly_difference": rho, "ar1_effective_weeks": float(len(dw) * (1 - rho) / (1 + rho)), "H1_stationary_weeks": r1, "H2_stationary_weeks": r2, "blocks_won_H1": a[c]["H1"]["blocks_won"], "blocks_won_H2": a[c]["H2"]["blocks_won"],
                       "frozen": {"H1": a[c]["H1"]["verdict"], "H2": a[c]["H2"].get("verdict")}, "frozen_ci_H1": a[c]["H1"]["primary"]["ci95"]}
        for h, key in (("H1", "H1_stationary_weeks"), ("H2", "H2_stationary_weeks")):
            hp = an.holm({c: (r[key]["p"] if r[key] else None) for c, r in rows.items()})
            for c, r in rows.items():
                if r[key]:
                    r[key]["holm_p"] = hp[c]
                    r[key]["verdict_frozen_rule"] = an.verdict(r[key]["estimate"], r[key]["ci95"][0], r[key]["ci95"][1], hp[c], r[f"blocks_won_{h}"])
        out[w] = rows
    return out


def analysis_B():
    out = {}
    for w in WINDOWS:
        for cdir in sorted((R / w).iterdir()):
            sel = json.loads((cdir / "selection.json").read_text(encoding="utf-8"))
            v = sel["validation"]
            row = {}
            for endpoint, key in (("item_day", "models_item_day_wape"), ("subset_day", "models_subset_day_wape")):
                means = {c: x["mean"] for c, x in v[key].items()}
                srt = sorted(means.items(), key=lambda kv: kv[1])
                (b1, m1), (b2, m2) = srt[0], srt[1]
                med = {c: m for c, m in means.items() if c in ("lgbm_l1", "lgbm_l1_small", "lgbm_quantile50", "xgb_l1")}
                best_med = min(med, key=med.get)
                row[endpoint] = {"selected": b1, "runner_up": b2, "relative_margin": (m2 - m1) / m1, "best_median_type": best_med,
                                 "by_block_rank_of_selected": [int(sorted(x["by_block"][i] for x in v[key].values()).index(v[key][b1]["by_block"][i]) + 1) for i in range(3)],
                                 "by_block_values_selected": v[key][b1]["by_block"], "by_block_values_runner_up": v[key][b2]["by_block"]}
            bl = {c: x["mean"] for c, x in v["baselines_item_day_wape"].items() if c.startswith("matched__")}
            sb = sorted(bl.items(), key=lambda kv: kv[1])
            row["matched_baseline_item_day"] = {"selected": sb[0][0], "runner_up": sb[1][0], "relative_margin": (sb[1][1] - sb[0][1]) / sb[0][1]}
            out[f"{w}/{cdir.name}"] = row
    return out


def pinball_totals(y, p, tau):
    r = y - p
    return np.where(r >= 0, tau * r, (tau - 1.0) * r)


def analysis_C():
    out = {}
    a = json.loads((R / "analysis" / "analysis_W2.json").read_text(encoding="utf-8"))["cells"]
    for c, v in a.items():
        A_, res, sel = load("W2", c)
        y, s, d = A_["y"].astype(float), A_["series"].astype(int), A_["day"].astype(int)
        S, day0 = int(res["n_series"]), res["blocks"]["test"][0]
        base = A_["base__" + sel["baseline_item_day_matched"]].astype(float)
        m = A_["pred__" + sel["model_item_day"]].astype(float)
        row = {}
        for tau in TAUS:
            Na, Nb = totals(s, d, pinball_totals(y, base, tau), S, day0), totals(s, d, pinball_totals(y, m, tau), S, day0)
            r = an.crossed_bootstrap(Na, Nb, B=2000, seed=SEED + int(tau * 100))
            row[str(tau)] = {"improvement": r["estimate"], "ci95": r["ci95"]}
        out[c] = row
    return out


def analysis_D():
    """Independent recomputation of the headline point estimates (item-day WAPE improvements H1/H1b/H2, subset-day H3) directly from predictions.npz."""
    out, worst = {}, 0.0
    for w in WINDOWS:
        a = json.loads((R / "analysis" / f"analysis_{w}.json").read_text(encoding="utf-8"))["cells"]
        for c, v in a.items():
            A_, res, sel = load(w, c)
            y, d = A_["y"].astype(np.float64), A_["day"].astype(int)
            wape = lambda p: np.abs(p.astype(np.float64) - y).sum() / y.sum()  # noqa: E731

            def sd(p):
                e = np.zeros(d.max() + 1)
                t = np.zeros(d.max() + 1)
                np.add.at(e, d, p.astype(np.float64) - y)
                np.add.at(t, d, y)
                return np.abs(e).sum() / t.sum()
            m, ma, ref = A_["pred__" + sel["model_item_day"]], A_["pred__" + sel["model_subset_day"]], A_["pred__" + sel["reference_model"]]
            bm, ba = A_["base__" + sel["baseline_item_day_matched"]], A_["base__" + sel["baseline_item_day_any"]]
            bs = A_["base__" + sel["baseline_subset_day_matched"]]
            rec = {"H1": 1 - wape(m) / wape(bm), "H1b": 1 - wape(m) / wape(ba), "H3": 1 - sd(ma) / sd(bs)}
            if sel["model_item_day"] != sel["reference_model"]:
                rec["H2"] = 1 - wape(m) / wape(ref)
            for h, x in rec.items():
                worst = max(worst, abs(x - v[h]["improvement"]))
            out[f"{w}/{c}"] = rec
    return {"max_abs_difference_vs_analysis_json": worst, "n_cells": len(out), "values": out}


def main():
    res = {"A_weekly_dependence": analysis_A(), "B_selection_margins": analysis_B(), "C_pinball_exploratory": analysis_C(), "D_recomputation": analysis_D()}
    (OUT / "audit_sensitivity.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("D: max abs diff", res["D_recomputation"]["max_abs_difference_vs_analysis_json"], "over", res["D_recomputation"]["n_cells"], "cells")
    for w, rows in res["A_weekly_dependence"].items():
        ch = [c for c, r in rows.items() if r["H1_stationary_weeks"]["verdict_frozen_rule"] != r["frozen"]["H1"]]
        ch2 = [c for c, r in rows.items() if r["H2_stationary_weeks"] and r["H2_stationary_weeks"]["verdict_frozen_rule"] != r["frozen"]["H2"]]
        print("A", w, "H1 verdict changes under stationary-week bootstrap:", ch, "| H2:", ch2, "| max lag1", round(max(r["lag1_weekly_difference"] for r in rows.values()), 2))


if __name__ == "__main__":
    main()
