"""Step 3: statistical audit. (a) independent re-implementation of the crossed bootstrap + two secondary methods (two-way cluster-robust delta method; one-way bootstraps);
(b) Holm and decision rules recomputed under the frozen plan; (c) dependence diagnostics (variance components, autocorrelation of weekly differentials);
(d) a simulation of the bootstrap's coverage under a known two-way dependence structure. Writes work/step3.json."""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import ind_core as ic  # noqa: E402

AUD = Path(__file__).parent
MIN_REL = 0.02
out = {"cells": {}}
p_h1, p_h2 = {}, {}
raw_cgm_h1, raw_cgm_h2 = {}, {}

for cell in ic.CELLS:
    A = ic.stored(cell)
    sel = ic.jload(ic.RES / cell / "selection.json")
    cfg = ic.jload(ic.RES / cell / "config.json")
    ana = ic.jload(ic.RES / cell / "analysis.json")
    y, s, d, blk = A["y"].astype(float), A["series"].astype(int), A["day"].astype(int), A["block"].astype(int)
    S = int(s.max()) + 1
    day0 = cfg["windows"]["test"][0]
    prim = A["pred__" + sel["primary_learned_config"].replace(":", "__")].astype(float)
    refs = {"H1": A["base__" + sel["reference_baseline_matched_information"]].astype(float), "H2": A["base__" + sel["reference_baseline_any_information"]].astype(float)}
    r = {}
    for h, ref in refs.items():
        Na, D = ic.cells_from_rows(s, d, np.abs(ref - y), y, S, day0)
        Nb, _ = ic.cells_from_rows(s, d, np.abs(prim - y), y, S, day0)
        pt, ci, p, se_b = ic.pigeonhole_ci(Na, Nb)
        cg = ic.cgm_linearised(Na, Nb)
        _, ci_s, se_s = ic.one_way_ci(Na, Nb, 0)
        _, ci_w, se_w = ic.one_way_ci(Na, Nb, 1)
        study = ana["H1_vs_matched_reference" if h == "H1" else "H2_vs_any_reference"]
        wins = sum(ic.wape(y[blk == o], prim[blk == o]) < ic.wape(y[blk == o], ref[blk == o]) for o in cfg["windows"]["test"])
        r[h] = {"point": pt, "pigeonhole_independent": {"ci95": ci, "p": p, "se": se_b}, "study_reported": {"ci95": study["ci95"], "p": study["p_two_sided"]},
                "cgm_twoway_delta": {"ci95": cg["ci95_twoway"], "se": cg["se_twoway"], "p": cg["p_twoway"], "var_series_only": cg["var_series"], "var_week_only": cg["var_week"],
                                     "var_cell": cg["var_cell"], "var_twoway": cg["var_twoway"]},
                "series_only_bootstrap": {"ci95": ci_s, "se": se_s}, "week_only_bootstrap": {"ci95": ci_w, "se": se_w},
                "blocks_won": int(wins), "shape": [int(S), int(Na.shape[1])],
                "ratio_pigeonhole_se_over_cgm_se": se_b / cg["se_twoway"]}
        # frozen decision rule (EXPERIMENT_PLAN.md section 5), applied to the INDEPENDENT numbers
        if h == "H1":
            p_h1[cell] = p
            raw_cgm_h1[cell] = cg["p_twoway"]
        else:
            p_h2[cell] = p
            raw_cgm_h2[cell] = cg["p_twoway"]
        r[h]["rule_inputs"] = {"point": pt, "ci_lo": ci[0], "ci_hi": ci[1], "blocks_won": int(wins)}
    # dependence diagnostics on the H1 loss-differential cells
    Na, D = ic.cells_from_rows(s, d, np.abs(refs["H1"] - y), y, S, day0)
    Nb, _ = ic.cells_from_rows(s, d, np.abs(prim - y), y, S, day0)
    dl = (Na - Nb) / Na.sum()                                   # contribution of each (series, week) cell to the improvement
    row_m, col_m, g = dl.mean(axis=1, keepdims=True), dl.mean(axis=0, keepdims=True), dl.mean()
    resid = dl - row_m - col_m + g
    W = dl.shape[1]
    wk = (Na - Nb).sum(axis=0)
    ac1 = float(np.corrcoef(wk[:-1], wk[1:])[0, 1])
    sd_iid = math.sqrt(dl.size * dl.var(ddof=1))                # naive: all cells independent
    r["dependence"] = {"cells": int(dl.size), "series": int(dl.shape[0]), "week_blocks": int(W),
                       "var_share_series_effect": float(dl.shape[1] * row_m.var(ddof=1) / dl.var(ddof=1)), "var_share_week_effect": float(dl.shape[0] * col_m.var(ddof=1) / dl.var(ddof=1)),
                       "var_share_interaction_residual": float(resid.var(ddof=1) / dl.var(ddof=1)),
                       "weekly_differential_lag1_autocorrelation": ac1, "weekly_differential_values": [float(x) for x in wk / Na.sum()],
                       "naive_iid_cells_se": sd_iid, "design_effect_cgm_se_over_iid_se": r["H1"]["cgm_twoway_delta"]["se"] / sd_iid,
                       "effective_independent_cells_approx": float((sd_iid / r["H1"]["cgm_twoway_delta"]["se"]) ** 2 * dl.size)}
    out["cells"][cell] = r

# ---- Holm on the independent p-values and on the study's, and the frozen decision rule per cell
def decide(point, lo, hi, wins, holm_p):
    if lo is not None and lo > 0 and point >= MIN_REL and wins >= 4 and holm_p < 0.05:
        return "SUPPORTED"
    if hi < 0:
        return "CONTRADICTED"
    return "INCONCLUSIVE"


stud = ic.jload(ic.RES / "CONFIRMATORY_SUMMARY.json")["families"]
out["holm"] = {}
for fam, pdict, cg_raw, key in (("H1", p_h1, raw_cgm_h1, "H1_vs_matched_reference"), ("H2", p_h2, raw_cgm_h2, "H2_vs_any_reference")):
    hp = ic.holm(pdict)
    hp_cgm = ic.holm(cg_raw)
    rows = {}
    for cell in ic.CELLS:
        rr = out["cells"][cell][fam]
        ri = rr["rule_inputs"]
        rows[cell] = {"independent_bootstrap_p": pdict[cell], "independent_holm_p": hp[cell], "study_holm_p": stud[key][cell]["holm_p"], "study_verdict": stud[key][cell]["verdict"],
                      "independent_verdict_bootstrap": decide(ri["point"], ri["ci_lo"], ri["ci_hi"], ri["blocks_won"], hp[cell]),
                      "cgm_p": cg_raw[cell], "cgm_holm_p": hp_cgm[cell],
                      "independent_verdict_cgm": decide(rr["point"], rr["cgm_twoway_delta"]["ci95"][0], rr["cgm_twoway_delta"]["ci95"][1], rr["blocks_won"], hp_cgm[cell])}
    out["holm"][fam] = rows

# ---- simulation of CI coverage under a known two-way dependence structure (S=300, W=24, like the M5 cells)
def sim(S=300, W=24, g=0.0, s_eta=0.15, s_delta=0.15, s_zeta=0.3, s_alpha=1.0, s_beta=0.3, reps=300, B=400, seed=7):
    rng = np.random.default_rng(seed)
    hit = {"pigeonhole": 0, "series_only": 0, "cgm": 0}
    width = {"pigeonhole": [], "series_only": [], "cgm": []}
    for _ in range(reps):
        a, b = rng.normal(0, s_alpha, (S, 1)), rng.normal(0, s_beta, (1, W))
        Na = np.exp(a + b + rng.normal(0, 0.3, (S, W)))
        rho = (1 - g) * np.exp(rng.normal(0, s_eta, (S, 1)) + rng.normal(0, s_delta, (1, W)) + rng.normal(0, s_zeta, (S, W)) - (s_eta ** 2 + s_delta ** 2 + s_zeta ** 2) / 2)
        Nb = Na * rho
        # target: 1 - E[rho] = g  (rho independent of Na)
        bs = np.empty(B)
        bo = np.empty(B)
        for k in range(B):
            bs[k] = ic.improvement(Na, Nb, rng.integers(0, S, S), rng.integers(0, W, W))
            bo[k] = ic.improvement(Na, Nb, rng.integers(0, S, S), np.arange(W))
        cg = ic.cgm_linearised(Na, Nb)
        for name, lo, hi in (("pigeonhole", *np.percentile(bs, [2.5, 97.5])), ("series_only", *np.percentile(bo, [2.5, 97.5])), ("cgm", *cg["ci95_twoway"])):
            hit[name] += lo <= g <= hi
            width[name].append(hi - lo)
    return {"reps": reps, "target": g, "coverage_95": {k: v / reps for k, v in hit.items()}, "mean_width": {k: float(np.mean(v)) for k, v in width.items()},
            "params": {"series_effect_sd_on_log_scale": s_alpha, "week_shock_on_log_gain_sd": s_delta, "series_gain_heterogeneity_sd": s_eta, "cell_noise_sd": s_zeta}}


out["simulation"] = {"week_shock_0.15": sim(), "week_shock_0.40": sim(s_delta=0.40, seed=11)}
(AUD / "work" / "step3.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
print("step3 done")
for cell in ic.CELLS:
    h = out["holm"]["H1"][cell]
    print(cell, "H1 indep p=%.4f holm=%.4f verdict=%s (study %s) cgm=%s" % (h["independent_bootstrap_p"], h["independent_holm_p"], h["independent_verdict_bootstrap"], h["study_verdict"], h["independent_verdict_cgm"]))
print(json.dumps(out["simulation"], indent=1))
