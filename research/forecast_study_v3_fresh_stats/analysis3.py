"""Analysis of forecast_study_v3 (frozen with the protocol). The v2 analysis module is reused UNCHANGED (patched in memory: results directory and cell list).

Confirmatory family (window W4, 3 fresh stores x H in {28, 7} = 6 cells), hypotheses and rules identical to forecast_study_v2 (frozen decision rule, Holm within the 6 cells of each family):
  H1  item-day-selected model vs best-validation MATCHED baseline of the EXPANDED set (the 31 simple baselines plus matched__ets/arima/theta)      <- PRIMARY
  H1b the same vs the best-validation baseline of ANY information set of the expanded set
  H2  the same model vs the reference Tweedie p=1.1 model
  H3  subset-day-selected model vs best matched baseline of the expanded set, subset-day WAPE
Secondary (declared in advance): H1-orig = H1 against the best matched baseline of the ORIGINAL 31 only; H3-orig likewise; descriptive: best statistical baseline vs best simple baseline.
Declared in advance as a robustness report (does not change any verdict): the item-day H1 recomputed with weeks resampled in stationary blocks (mean 3 weeks), and the lag-1 autocorrelation of weekly differences.
"""
from __future__ import annotations

import json

import numpy as np

from research.forecast_study_v2 import analysis as an

from . import v3common as C

an.RESULTS = C.RESULTS
an.CELL_KEYS = [(k, H) for k in C.STORES for H in C.HORIZONS]
STAT = tuple(f"matched__{m}" for m in C.STAT_MODELS)
STAT_ALL = tuple(f"{p}__{m}" for p in ("matched", "fresh") for m in C.STAT_MODELS)
B = 10000
SEED = 7771234


def best(means: dict, names):
    return min(sorted(names), key=lambda k: (means[k], k))


def boot_stationary_weeks(Na, Nb, B=B, seed=SEED, mean_block=3.0):
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
    kle, kge = int((d <= 0).sum()), int((d >= 0).sum())
    return {"estimate": float(th), "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))], "p": min(1.0, 2 * min((kle + 1) / (B + 1), (kge + 1) / (B + 1)))}


def main():
    r = an.analyse_window(C.WINDOW)
    cells = r["cells"]
    extra = {}
    for c in cells:
        key, H = c.rsplit("_H", 1)
        A, sel, res = an.load_cell(C.WINDOW, key, int(H))
        S, day0, order = int(res["n_series"]), res["blocks"]["test"][0], res["blocks"]["test"]
        y, s, d, blk = A["y"].astype(float), A["series"].astype(int), A["day"].astype(int), A["block"].astype(int)
        means = {b: x["mean"] for b, x in sel["validation"]["baselines_item_day_wape"].items()}
        means_a = {b: x["mean"] for b, x in sel["validation"]["baselines_subset_day_wape"].items()}
        matched = [b for b in means if b.startswith("matched__")]
        orig_item = best(means, [b for b in matched if b not in STAT])
        orig_agg = best(means_a, [b for b in matched if b not in STAT])
        stat_item = best(means, list(STAT))
        stat_any = best(means, list(STAT_ALL))
        P = lambda n: A[f"pred__{n}"].astype(float)  # noqa: E731
        Bm = lambda n: A[f"base__{n}"].astype(float)  # noqa: E731
        m_item = sel["model_item_day"]
        Nm = an.cell_totals(s, d, y, P(m_item), S, day0)[0]
        ex = {"selected": {"item_day_model": m_item, "subset_day_model": sel["model_subset_day"], "best_matched_baseline_expanded": sel["baseline_item_day_matched"], "best_matched_baseline_original31": orig_item,
                           "best_matched_statistical_item": stat_item, "best_statistical_any": stat_any, "best_matched_baseline_original31_subset_day": orig_agg}}
        Na_o = an.cell_totals(s, d, y, Bm(orig_item), S, day0)[0]
        r_o = an.crossed_bootstrap(Na_o, Nm)
        ex["H1_orig"] = {"improvement": r_o["estimate"], "ci95": r_o["ci95"], "p": r_o["p"], "blocks_won": int(an._blocks_won(y, Bm(orig_item), P(m_item), blk, order)), "cgm_t": an.cgm_t(Na_o, Nm)}
        wape = lambda p: float(np.abs(p - y).sum() / y.sum())  # noqa: E731
        ex["descriptive_item_day_wape"] = {"model": wape(P(m_item)), "best_matched_expanded": wape(Bm(sel["baseline_item_day_matched"])), "best_matched_original31": wape(Bm(orig_item)), **{n: wape(Bm(n)) for n in STAT_ALL}}
        Nb = an.cell_totals(s, d, y, Bm(sel["baseline_item_day_matched"]), S, day0)[0]
        ex["H1_stationary_weeks"] = boot_stationary_weeks(Nb, Nm)
        dw = (Nb - Nm).sum(axis=0)
        ex["lag1_weekly_difference_H1"] = float(np.corrcoef(dw[:-1], dw[1:])[0, 1])
        days = np.unique(d)
        wk = (days - day0) // 7
        W = int(wk.max()) + 1

        def tot(p):
            t = np.zeros(len(days))
            np.add.at(t, np.searchsorted(days, d), p - y)
            return np.bincount(wk, weights=np.abs(t), minlength=W)
        wa, wb = tot(Bm(orig_agg)), tot(P(sel["model_subset_day"]))
        h3 = an.week_bootstrap(wa, wb, an.PRIMARY_SUBSET_DAY)
        h3s = an.week_bootstrap(wa, wb, "stationary")
        ex["H3_orig"] = {"improvement": h3["estimate"], "ci95": h3["ci95"], "p": h3["p"], "secondary_p": h3s["p"], "secondary_ci95": h3s["ci95"]}
        extra[c] = ex
    for h in ("H1_orig", "H3_orig"):
        adj = an.holm({c: extra[c][h]["p"] for c in extra})
        adj2 = an.holm({c: (extra[c][h]["cgm_t"]["p"] if h == "H1_orig" else extra[c][h]["secondary_p"]) for c in extra})
        for c in extra:
            e = extra[c][h]
            e["holm_p"], e["holm_p_secondary"] = adj[c], adj2[c]
            if h == "H1_orig":
                lo2, hi2 = e["cgm_t"]["ci95"]
                e["verdict_primary_method"] = an.verdict(e["improvement"], e["ci95"][0], e["ci95"][1], adj[c], e["blocks_won"])
                e["verdict_secondary_method"] = an.verdict(e["improvement"], lo2, hi2, adj2[c], e["blocks_won"])
                e["verdict"] = e["verdict_primary_method"] if e["verdict_primary_method"] == e["verdict_secondary_method"] else "INCONCLUSIVE"
    (C.RESULTS / "analysis" / "analysis3_W4_extra.json").write_text(json.dumps(extra, indent=1), encoding="utf-8")
    for c, v in cells.items():
        print(c, {h: (round(v[h]["improvement"], 4), v[h].get("verdict")) for h in ("H1", "H1b", "H2", "H3") if "improvement" in v[h]}, "| H1_orig", round(extra[c]["H1_orig"]["improvement"], 4), extra[c]["H1_orig"]["verdict"])


if __name__ == "__main__":
    main()
