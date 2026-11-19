"""POST-HOC EXPLORATORY follow-up (E1), added AFTER the confirmatory results were seen (see the deviations log in EXPERIMENT_PLAN.md).

Question: is the primary model's loss to the trailing-median baseline in pooled WAPE an objective mismatch (WAPE is minimised by a conditional median; the
validation-selected model fits a Tweedie/mean-type loss)? The same LightGBM configuration is refitted with the L1 (median) objective at every test origin, with
identical features, windows, training spans and seed, and scored on the SAME rows as the main run. No validation selection is done for it (one fixed variant),
it never enters H1/H2, and it is reported as exploratory.

    python -m research.forecast_study_v1.exploratory_l1 m5_ca1 28
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from ml.benchmark import direct as hist_direct
from research.forecast_study_v1 import inference as inf
from research.forecast_study_v1 import metrics as mt
from research.forecast_study_v1 import protocol as pr

RESULTS = Path(__file__).resolve().parent / "results"
SEED = 42


def run(dataset: str, H: int, log=print) -> dict:
    t0 = time.time()
    from lightgbm import LGBMRegressor

    cell = f"fs1_{dataset}_H{H}"
    main = np.load(RESULTS / cell / "predictions.npz")
    sel = json.load(open(RESULTS / cell / "selection.json", encoding="utf-8"))
    cfg = json.load(open(RESULTS / cell / "config.json", encoding="utf-8"))
    seg = json.load(open(RESULTS / cell / "segments.json", encoding="utf-8"))
    d = pr.load(dataset)
    F, names, valid = pr.build_features(d, H)
    preds = []
    for o in cfg["windows"]["test"]:
        Xtr, ytr, _, _ = hist_direct.rows(F, valid, d.y, max(0, o - pr.TRAIN_SPAN), o - 1)
        Xte, yte, s, t = hist_direct.rows(F, valid, d.y, o, o + pr.BLOCK - 1)
        m = LGBMRegressor(objective="l1", n_estimators=500, learning_rate=0.05, num_leaves=31, min_child_samples=40, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                          n_jobs=4, random_state=SEED, verbose=-1)
        m.fit(Xtr, ytr)
        p = np.maximum(m.predict(Xte), 0.0)
        # align to the main run's evaluated rows of this block (rows where all baselines were finite)
        bm = main["block"] == o
        key = {(int(a), int(b)): float(v) for a, b, v in zip(s, t, p)}
        preds.append(np.array([key[(int(a), int(b))] for a, b in zip(main["series"][bm], main["day"][bm])]))
        log(f"[E1 {cell}] block {o} done ({round(time.time() - t0)}s)")
    pred = np.concatenate(preds)
    y, s, day = main["y"].astype(float), main["series"], main["day"]
    ref_m, ref_a = "base__" + sel["reference_baseline_matched_information"], "base__" + sel["reference_baseline_any_information"]
    prim = "pred__" + sel["primary_learned_config"].replace(":", "__")
    methods = {"l1_model": pred, "tweedie_primary": main[prim].astype(float), "ref_matched": main[ref_m].astype(float), "ref_any": main[ref_a].astype(float)}
    cm = inf.cell_matrices(s, day, y, methods, len(seg["adi"]), cfg["windows"]["test"][0], 7)
    out = {"label": "POST-HOC EXPLORATORY (E1); not part of the confirmatory families", "cell": cell, "references": {"matched": ref_m, "any": ref_a, "primary_tweedie": prim},
           "table": {k: {"wape": mt.wape(y, v), "aggregate_wape": mt.aggregate_wape(y, v, day), "rel_bias": mt.rel_bias(y, v), "mae": mt.mae(y, v), "rmse": mt.rmse(y, v)} for k, v in methods.items()}}
    for a_key, b_key, lab in (("ref_matched", "l1_model", "l1_vs_matched_reference"), ("ref_any", "l1_model", "l1_vs_any_reference"), ("tweedie_primary", "l1_model", "l1_vs_tweedie_primary")):
        r = inf.crossed_bootstrap(cm["N"][a_key], cm["N"][b_key], cm["D"], B=2000)
        out[lab] = {k: r[k] for k in ("estimate", "ci95", "p_two_sided")}
    np.savez_compressed(RESULTS / f"E1_l1_{cell}.npz", pred_l1=pred, series=s, day=day, block=main["block"])
    (RESULTS / f"E1_l1_{cell}.json").write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    log(f"[E1 {cell}] done in {round(time.time() - t0)}s")
    return out


if __name__ == "__main__":
    r = run(sys.argv[1], int(sys.argv[2]), log=lambda s: print(s, flush=True))
    print(json.dumps({k: v for k, v in r.items() if k != "table"}, indent=1, default=float))
    print(json.dumps(r["table"], indent=1, default=float))
