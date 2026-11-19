"""S2 sensitivity (replaces the vacuous 'remove test customers' design, see the deviations log): customer-disjoint evaluation.

Every customer seen before a test cutoff appears in that test snapshot, so removing test customers from training leaves nothing. Instead the customers are split at random
(seed 42, 50/50) into G1 and G2: models, calibration and the threshold use ONLY G1 customers in the (chronologically earlier) training and validation snapshots, and the
test snapshot is scored only on G2 customers. The model family and baseline are the ones selected in the main S2 run (no re-selection).

    python -m research.forecast_study_v1.s2_customer_disjoint
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.benchmark import churn as ch
from ml.benchmark import datasets as ds
from research.forecast_study_v1 import run_classification_study as s2

RESULTS = Path(__file__).resolve().parent / "results"


def main() -> dict:
    d, _ = ds.load_online_retail_ii()
    main_res = json.load(open(RESULTS / "s2_online_retail_inactivity" / "results.json", encoding="utf-8"))
    ids = np.array(sorted(d["Customer ID"].dropna().unique()))
    rng = np.random.default_rng(s2.SEED)
    g1 = set(rng.permutation(ids)[: len(ids) // 2].tolist())
    out = {"label": "S2 sensitivity: customer-disjoint (random 50/50 customer split, seed 42; chronology preserved)", "n_customers": int(len(ids)), "n_g1": len(g1), "origins": {}}
    for name, spec in s2.ORIGINS.items():
        sel = main_res["origins"][name]["selection"]
        tr = pd.concat([ch.snapshot(d, c) for c in spec["train"]], ignore_index=True)
        va, te = ch.snapshot(d, spec["validation"]), ch.snapshot(d, spec["test"])
        tr, va, te = tr[tr["customer_id"].isin(g1)], va[va["customer_id"].isin(g1)], te[~te["customer_id"].isin(g1)]
        probs = s2.fit_score(tr, va, te, ch.FEATURES, s2.SEED)
        yte = te["inactive_90d"].to_numpy()
        m = sel["primary_model"]
        base = te[s2.BASELINE_COLS[sel["best_baseline"]]].to_numpy(float)
        paired = s2.paired_bootstrap(yte, probs[m][1], base, s2.B_SENS, s2.SEED + 3)
        out["origins"][name] = {"rows": {"train": len(tr), "validation": len(va), "test": len(te)}, "model": m, "baseline": sel["best_baseline"],
                                "test_roc_auc": s2.rank_metrics(yte, probs[m][1])["roc_auc"], "test_pr_auc": s2.rank_metrics(yte, probs[m][1])["pr_auc"],
                                "baseline_roc_auc": s2.rank_metrics(yte, base)["roc_auc"], "baseline_pr_auc": s2.rank_metrics(yte, base)["pr_auc"],
                                "prevalence_test": float(yte.mean()), "paired_model_minus_baseline": paired}
    (RESULTS / "S2_customer_disjoint.json").write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=float))
