"""Step 5: independent re-implementation of the Mondrian split-conformal 80% intervals (calibration = stored VALIDATION predictions, test = stored TEST predictions),
coverage overall / by block / by segment / by zero vs positive demand, and a check of the exchangeability assumption. Writes work/step5.json."""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import ind_core as ic  # noqa: E402

AUD = Path(__file__).parent
step4 = ic.jload(AUD / "work" / "step4.json")
out = {}
LEVEL = 0.8
for cell in ic.CELLS:
    A = ic.stored(cell)
    sel = ic.jload(ic.RES / cell / "selection.json")
    cfg = ic.jload(ic.RES / cell / "config.json")
    seg = ic.jload(ic.RES / cell / "segments.json")
    ana = ic.jload(ic.RES / cell / "analysis.json")
    y, s, blk = A["y"].astype(float), A["series"].astype(int), A["block"].astype(int)
    starts = cfg["windows"]["test"]
    vy, vs, vd = A["val_y"].astype(float), A["val_series"].astype(int), A["val_day"].astype(int)
    pk = sel["primary_learned_config"].replace(":", "__")
    pairs = {"model": ("pred__" + pk, "val_pred__" + pk), "ref_any": ("base__" + sel["reference_baseline_any_information"], "val_base__" + sel["reference_baseline_any_information"]),
             "ref_matched": ("base__" + sel["reference_baseline_matched_information"], "val_base__" + sel["reference_baseline_matched_information"])}
    freq = np.array(seg["frequency"])
    vol = np.array(step4[cell]["segment_counts_independent"] and [None]) if False else None
    r = {"n_calibration": int(len(vy)), "n_test": int(len(y)), "calibration_blocks_are_before_test": bool(vd.max() < A["day"].min())}
    for name, (tk, vk) in pairs.items():
        p, vp = A[tk].astype(float), A[vk].astype(float)
        edges = np.quantile(vp, [1 / 3, 2 / 3])
        bc, bt = np.digitize(vp, edges), np.digitize(p, edges)
        res = np.abs(vy - vp)
        q = np.full(3, np.nan)
        for b in range(3):
            rb = np.sort(res[bc == b])
            k = math.ceil((len(rb) + 1) * LEVEL)
            if len(rb) and k <= len(rb):
                q[b] = rb[k - 1]
        half = q[bt]
        lo, hi = np.maximum(0, p - half), p + half
        cov = (y >= lo) & (y <= hi)
        entry = {"coverage_overall": float(cov.mean()), "mean_width": float((hi - lo).mean()), "bin_quantiles": [float(x) for x in q],
                 "coverage_by_block": {str(o): float(cov[blk == o].mean()) for o in starts},
                 "coverage_on_zero_demand_rows": float(cov[y == 0].mean()), "coverage_on_positive_demand_rows": float(cov[y > 0].mean()),
                 "share_zero_demand_rows": float((y == 0).mean()),
                 "by_frequency_segment": {v: float(cov[np.isin(s, np.flatnonzero(freq == v))].mean()) for v in sorted(set(freq))},
                 "by_prediction_bin": {str(b): {"n": int((bt == b).sum()), "coverage": float(cov[bt == b].mean())} for b in range(3) if (bt == b).any()}}
        # volume tercile coverage using the stored volume labels
        volL = np.array(seg["volume"])
        entry["by_volume_segment"] = {v: float(cov[np.isin(s, np.flatnonzero(volL == v))].mean()) for v in sorted(set(volL))}
        # exchangeability diagnostic: calibration residual scale vs test residual scale, per bin
        tres = np.abs(y - p)
        entry["mean_abs_residual_calibration_vs_test_by_bin"] = {str(b): [float(res[bc == b].mean()), float(tres[bt == b].mean()) if (bt == b).any() else None] for b in range(3)}
        r[name] = entry
    # study's own numbers for comparison
    r["study_overall_coverage_model"] = ana["conformal_80"]["model"]["overall"]["coverage"]
    r["agrees_with_study_model_coverage"] = abs(r["study_overall_coverage_model"] - r["model"]["coverage_overall"]) < 1e-9
    out[cell] = r
    print(cell, "model cov %.4f (study %.4f) | freq %s | zero-demand rows cov %.3f pos %.3f" % (r["model"]["coverage_overall"], r["study_overall_coverage_model"], {k: round(v, 3) for k, v in r["model"]["by_frequency_segment"].items()},
                                                                                              r["model"]["coverage_on_zero_demand_rows"], r["model"]["coverage_on_positive_demand_rows"]), flush=True)
(AUD / "work" / "step5.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
