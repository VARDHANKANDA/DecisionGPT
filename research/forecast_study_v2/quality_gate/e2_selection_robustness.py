"""E2 — selection-robustness check (POST-HOC, EXPLORATORY; does not replace any frozen result).

Question (quality-gate audit, issue SI-01): the frozen analysis scored only the validation-selected models on the test blocks. Validation margins between the selected median-type model and its
runner-up were tiny (0.02-1.1 %). Does the item-day advantage over the best matched baseline belong to the median-type CLASS, or to the particular selected configuration (winner's curse)?
Method: on window W2 (the confirmatory window) refit ALL eight candidates on the six test blocks with the frozen pipeline functions (same data, features, seeds, hyper-parameters), score each on the
same eligible rows, and compare the improvement over the SAME validation-selected best matched baselines as in the frozen analysis. Outputs (summaries only; per-row forecasts of M5 sales are kept
in a scratch directory outside the repository) -> quality_gate/results/e2_selection_robustness.json.

    python research/forecast_study_v2/quality_gate/e2_selection_robustness.py <scratch_dir>
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parents[1]))
from research.forecast_study_v2 import metrics as mt  # noqa: E402
from research.forecast_study_v2 import models as md  # noqa: E402
from research.forecast_study_v2 import pipeline as pl  # noqa: E402

SCR = Path(sys.argv[1])
pl.RESULTS = SCR
MEDIAN_TYPE = md.MEDIAN_TARGETING


def main():
    an = json.loads((HERE / "results" / "analysis" / "analysis_W2.json").read_text(encoding="utf-8"))["cells"]
    out = {}
    for cell, v in an.items():
        key, H = cell.rsplit("_H", 1)
        H = int(H)
        sel = v["selection"]
        P = pl.Prepared(key, "W2", H, lambda s: print(s, flush=True))
        o_dir = pl.cell_dir("W2", key, H)
        (o_dir / "fits").mkdir(parents=True, exist_ok=True)
        ys, ss, dd = [], [], []
        preds = {c: [] for c in md.CANDIDATES}
        base_item, base_agg = [], []
        t0 = time.time()
        for o in P.blocks["test"]:
            X, y, s, t, ok = P.block_rows(o)
            ys.append(y[ok]); ss.append(s[ok]); dd.append(t[ok])
            for c in md.CANDIDATES:
                preds[c].append(pl._fit_predict(P, o_dir, "test", o, c, pl.SEED, {})[ok])
            base_item.append(P.base[sel["baseline_item_day_matched"]][s, t][ok].astype(float))
            base_agg.append(P.base[sel["baseline_subset_day_matched"]][s, t][ok].astype(float))
            print(f"[{cell}] test block {o} all candidates done ({round(time.time() - t0)}s)", flush=True)
        y, d = np.concatenate(ys), np.concatenate(dd)
        bi, ba = np.concatenate(base_item), np.concatenate(base_agg)
        rows = {}
        for c in md.CANDIDATES:
            p = np.concatenate(preds[c])
            rows[c] = {"item_day_wape": mt.wape(y, p), "subset_day_wape": mt.subset_day_wape(y, p, d), "rel_bias": mt.rel_bias(y, p)}
            rows[c]["item_day_improvement_vs_matched_baseline"] = 1 - rows[c]["item_day_wape"] / mt.wape(y, bi)
            rows[c]["subset_day_improvement_vs_matched_baseline"] = 1 - rows[c]["subset_day_wape"] / mt.subset_day_wape(y, ba, d)
        item_rank = sorted(rows, key=lambda c: rows[c]["item_day_wape"])
        agg_rank = sorted(rows, key=lambda c: rows[c]["subset_day_wape"])
        med = [c for c in rows if c in MEDIAN_TYPE]
        out[cell] = {"selected_item_day": sel["model_item_day"], "selected_subset_day": sel["model_subset_day"], "candidates": rows, "test_rank_item_day": item_rank, "test_rank_subset_day": agg_rank,
                     "selected_item_day_test_rank": item_rank.index(sel["model_item_day"]) + 1, "selected_subset_day_test_rank": agg_rank.index(sel["model_subset_day"]) + 1,
                     "median_type_item_day_improvement": {c: rows[c]["item_day_improvement_vs_matched_baseline"] for c in med},
                     "median_type_min_item_day_improvement": min(rows[c]["item_day_improvement_vs_matched_baseline"] for c in med),
                     "best_in_hindsight_item_day_improvement": rows[item_rank[0]]["item_day_improvement_vs_matched_baseline"],
                     "selected_item_day_improvement": rows[sel["model_item_day"]]["item_day_improvement_vs_matched_baseline"],
                     "frozen_selected_item_day_improvement": v["H1"]["improvement"], "mean_type_item_day_improvement": {c: rows[c]["item_day_improvement_vs_matched_baseline"] for c in rows if c not in MEDIAN_TYPE}}
    (HERE / "quality_gate" / "results" / "e2_selection_robustness.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("done")


if __name__ == "__main__":
    main()
