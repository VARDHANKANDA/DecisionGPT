"""Analysis of one finished cell: ``python -m research.forecast_study_v1.analyze fs1_m5_ca1_H28``  ->  ``<cell>/analysis.json``.

Reads only the stored ``predictions.npz`` / ``selection.json`` / ``segments.json`` / ``results.json`` (no refitting, no test-time choices): the primary model and the
reference baselines are the ones written to ``selection.json`` from validation data before the test blocks were fitted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

from research.forecast_study_v1 import inference as inf
from research.forecast_study_v1 import metrics as mt

RESULTS = Path(__file__).resolve().parent / "results"
B_MAIN, B_SENS, B_SEG = 2000, 1000, 600
MIN_SEGMENT_SERIES = 20
MIN_RELEVANT = 0.02          # EXPERIMENT_PLAN.md section 5: minimum practically relevant relative WAPE improvement


def _pred_key(config_id: str) -> str:
    return "pred__" + config_id.replace(":", "__")


def load(cell: str):
    out = RESULTS / cell
    z = np.load(out / "predictions.npz")
    arr = {k: z[k] for k in z.files}
    return out, arr, json.load(open(out / "selection.json", encoding="utf-8")), json.load(open(out / "segments.json", encoding="utf-8")), json.load(open(out / "config.json", encoding="utf-8"))


def analyse(cell: str, log=print) -> dict:
    out, A, sel, seg, cfg = load(cell)
    y, s, day, blk = A["y"].astype(float), A["series"], A["day"], A["block"]
    S = len(seg["adi"])
    day0 = cfg["windows"]["test"][0]
    methods = {k: A[k].astype(float) for k in A if k.startswith(("pred__", "base__"))}
    primary = _pred_key(sel["primary_learned_config"])
    ref_any = "base__" + sel["reference_baseline_any_information"]
    ref_matched = "base__" + sel["reference_baseline_matched_information"]
    cells = inf.cell_matrices(s, day, y, methods, S, day0, 7)
    D, N = cells["D"], cells["N"]
    blocks = cfg["windows"]["test"]
    res: dict = {"cell": cell, "primary": primary, "reference_any": ref_any, "reference_matched": ref_matched, "n_points": int(len(y)), "n_series": S, "n_week_blocks": int(cells["W"]),
                 "family_selection_rule": sel.get("rule")}

    # ---- table of every method, pooled
    table = {}
    for k, p in methods.items():
        table[k] = {"wape": mt.wape(y, p), "mae": mt.mae(y, p), "rmse": mt.rmse(y, p), "rel_bias": mt.rel_bias(y, p), "aggregate_wape": mt.aggregate_wape(y, p, day),
                    "wape_by_block": [mt.wape(y[blk == o], p[blk == o]) for o in blocks]}
    res["table"] = table
    res["ranking_pooled_wape"] = sorted(table, key=lambda k: table[k]["wape"])
    res["ranking_aggregate_wape"] = sorted(table, key=lambda k: table[k]["aggregate_wape"])
    tau = stats.kendalltau([table[k]["wape"] for k in table], [table[k]["aggregate_wape"] for k in table])
    res["kendall_tau_pooled_vs_aggregate"] = {"tau": float(tau.statistic), "p": float(tau.pvalue), "n_methods": len(table)}

    # ---- confirmatory comparisons (H1: vs matched reference; H2: vs best any-information reference)
    def compare(base_key: str, label: str, B=B_MAIN):
        r = inf.crossed_bootstrap(N[base_key], N[primary], D, B=B)
        wins = [(table[base_key]["wape_by_block"][i] is not None and table[primary]["wape_by_block"][i] is not None and table[primary]["wape_by_block"][i] < table[base_key]["wape_by_block"][i])
                for i in range(len(blocks))]
        r |= {"baseline": base_key, "wape_baseline": table[base_key]["wape"], "wape_model": table[primary]["wape"], "model_wins_blocks": int(sum(wins)), "n_blocks": len(blocks),
              "label": label}
        e, lo = r["estimate"], r["ci95"][0]
        r["decision_rule_H"] = ("SUPPORTED" if (e is not None and lo is not None and lo > 0 and e >= MIN_RELEVANT and sum(wins) >= 4 and r["p_two_sided"] is not None)
                                else "CONTRADICTED" if (r["ci95"][1] is not None and r["ci95"][1] < 0) else "INCONCLUSIVE")
        r["decision_note"] = "decision also needs Holm p < 0.05 across the 6 confirmatory cells (applied in aggregate.py)"
        return r

    res["H1_vs_matched_reference"] = compare(ref_matched, "model vs best-validation matched-information baseline")
    res["H2_vs_any_reference"] = compare(ref_any, "model vs best-validation baseline of any information set")

    # ---- H4 / sensitivity: bootstrap designs
    res["bootstrap_designs_vs_matched"] = {
        "crossed": {k: res["H1_vs_matched_reference"][k] for k in ("estimate", "ci95", "p_two_sided")},
        "stationary_weeks": inf.stationary_bootstrap_weeks(N[ref_matched], N[primary], D, B=B_SENS),
        "series_only_historical": inf.series_only_bootstrap(N[ref_matched], N[primary], D, B=B_SENS)}
    c, so = res["bootstrap_designs_vs_matched"]["crossed"]["ci95"], res["bootstrap_designs_vs_matched"]["series_only_historical"]["ci95"]
    res["bootstrap_designs_vs_matched"]["ci_width_ratio_crossed_over_series_only"] = float((c[1] - c[0]) / (so[1] - so[0])) if so[1] != so[0] else None

    # ---- sensitivity: every baseline as the reference (point estimates + crossed CI at reduced B)
    alt = {}
    for k in sorted(k for k in methods if k.startswith("base__")):
        r = inf.crossed_bootstrap(N[k], N[primary], D, B=B_SENS // 2)
        alt[k] = {"wape_baseline": table[k]["wape"], "relative_improvement": r["estimate"], "ci95": r["ci95"]}
    res["model_vs_each_baseline"] = alt

    # ---- leave-one-origin-out of the headline estimate
    loo = {}
    for i, o in enumerate(blocks):
        m = blk != o
        a = np.sum(np.abs(methods[ref_matched][m] - y[m]))
        b = np.sum(np.abs(methods[primary][m] - y[m]))
        loo[str(o)] = float((a - b) / a) if a > 0 else None
    res["leave_one_origin_out_improvement_vs_matched"] = loo

    # ---- H7: segments (frequency and volume), within-segment crossed bootstrap
    seg_res = {}
    for dim in ("frequency", "volume", "pattern"):
        labels = np.asarray(seg[dim])
        for v in sorted(set(labels.tolist())):
            idx = np.flatnonzero(labels == v)
            if len(idx) < MIN_SEGMENT_SERIES:
                seg_res[f"{dim}={v}"] = {"n_series": int(len(idx)), "note": f"fewer than {MIN_SEGMENT_SERIES} series: not estimated"}
                continue
            for lab, ref in (("vs_matched", ref_matched), ("vs_any", ref_any)):
                r = inf.crossed_bootstrap(N[ref], N[primary], D, B=B_SEG, series_subset=idx)
                seg_res.setdefault(f"{dim}={v}", {"n_series": int(len(idx))})[lab] = {k: r[k] for k in ("estimate", "ci95", "wape_diff_point")}
            m = np.isin(s, idx)
            seg_res[f"{dim}={v}"]["wape_model"] = mt.wape(y[m], methods[primary][m])
            seg_res[f"{dim}={v}"]["wape_matched_reference"] = mt.wape(y[m], methods[ref_matched][m])
            seg_res[f"{dim}={v}"]["wape_any_reference"] = mt.wape(y[m], methods[ref_any][m])
    res["segments"] = seg_res

    # ---- exploratory DM on the store-day aggregate (short series: optimistic normal approximation)
    days = np.unique(day)
    agg = lambda p: np.array([np.abs(p[day == d].sum() - y[day == d].sum()) for d in days])
    res["diebold_mariano_aggregate_exploratory"] = {"vs_matched": inf.diebold_mariano(agg(methods[ref_matched]), agg(methods[primary]), h=int(cfg["H"])),
                                                    "vs_any": inf.diebold_mariano(agg(methods[ref_any]), agg(methods[primary]), h=int(cfg["H"]))}

    # ---- H6: Mondrian split-conformal 80 % intervals, calibrated on validation predictions of the same method
    cov = {}
    if "val_y" in A:
        pairs = {"model": primary, "reference_any": ref_any, "reference_matched": ref_matched}
        for name, tk in pairs.items():
            vkey =("val_pred__" + tk[len("pred__"):]) if tk.startswith("pred__") else ("val_base__" + tk[len("base__"):])
            if vkey not in A:
                cov[name] = {"note": f"{vkey} not stored"}
                continue
            m = inf.mondrian_conformal(A[vkey].astype(float), A["val_y"].astype(float), methods[tk], level=0.8, n_bins=3)
            overall = inf.interval_report(y, methods[tk], m["half_width"])
            by_block = {str(o): inf.interval_report(y, methods[tk], m["half_width"], mask=(blk == o))["coverage"] for o in blocks}
            by_freq = {}
            for v in sorted(set(seg["frequency"])):
                by_freq[v] = inf.interval_report(y, methods[tk], m["half_width"], mask=np.isin(s, np.flatnonzero(np.asarray(seg["frequency"]) == v)))
            cov[name] = {"method": tk, "level": 0.8, "bin_edges": m["edges"], "bin_quantiles": m["bin_quantiles"], "n_calibration": m["n_cal"], "overall": overall,
                         "coverage_by_test_block": by_block, "by_frequency_segment": by_freq}
    res["conformal_80"] = cov

    (out / "analysis.json").write_text(json.dumps(res, indent=2, default=lambda o: None if o != o else float(o) if isinstance(o, (np.floating,)) else int(o) if isinstance(o, np.integer) else str(o)), encoding="utf-8")
    log(f"[{cell}] analysis.json written")
    return res


if __name__ == "__main__":
    for c in sys.argv[1:]:
        analyse(c, log=lambda s: print(s, flush=True))
