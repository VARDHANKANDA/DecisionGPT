"""E1 — compare the clean-environment re-run of all v2 cells (scratch directory) with the stored v2 results. READ-ONLY on results/; the re-run lives outside the repository.

Compares: selection records (selected model / baseline names and every validation mean), every stored method summary (all metrics and per-block WAPEs), the stored forecasts element-wise
(only the maximum absolute differences are reported; no forecast values are written), and the verdicts/improvements/Holm p-values recomputed by the frozen analysis code from the re-run.

    python research/forecast_study_v2/quality_gate/e1_compare.py <scratch_results_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parents[1]))
from research.forecast_study_v2 import analysis as an  # noqa: E402

REPO = HERE / "results"
SCR = Path(sys.argv[1])
METRICS = ("item_day_wape", "item_week_wape", "subset_week_wape", "subset_day_wape", "rel_bias", "mae", "rmse", "zero_forecast_share")


def maxdiff_tree(a, b):
    if isinstance(a, dict):
        return max([maxdiff_tree(a[k], b[k]) for k in a] + [0.0])
    if isinstance(a, (list, tuple)):
        return max([maxdiff_tree(x, y) for x, y in zip(a, b)] + [0.0])
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b))
    return 0.0 if a == b else float("inf")


def main():
    out = {"scratch": "scratch directory outside the repository (not recorded)", "cells": {}, "windows": {}}
    for wdir in sorted(p for p in REPO.iterdir() if p.is_dir() and p.name in ("W1", "W2", "W3")):
        for cdir in sorted(wdir.iterdir()):
            name = f"{wdir.name}/{cdir.name}"
            s = SCR / wdir.name / cdir.name
            if not (s / "results.json").exists():
                out["cells"][name] = {"status": "NOT RE-RUN"}
                continue
            sa, sb = json.loads((cdir / "selection.json").read_text(encoding="utf-8")), json.loads((s / "selection.json").read_text(encoding="utf-8"))
            names = ("model_item_day", "model_subset_day", "reference_model", "baseline_item_day_matched", "baseline_item_day_any", "baseline_subset_day_matched", "baseline_subset_day_any")
            same_sel = all(sa[k] == sb[k] for k in names)
            val_diff = maxdiff_tree(sa["validation"], sb["validation"])
            ra, rb = json.loads((cdir / "results.json").read_text(encoding="utf-8")), json.loads((s / "results.json").read_text(encoding="utf-8"))
            mdiff, n_methods = 0.0, 0
            for m, v in ra["summary"].items():
                if m not in rb["summary"]:
                    mdiff = float("inf")
                    continue
                n_methods += 1
                for k in METRICS:
                    mdiff = max(mdiff, abs(v[k] - rb["summary"][m][k]))
                mdiff = max(mdiff, maxdiff_tree(v["item_day_wape_by_block"], rb["summary"][m]["item_day_wape_by_block"]))
            za, zb = np.load(cdir / "predictions.npz"), np.load(s / "predictions.npz")
            fdiff, n_arr = 0.0, 0
            for k in za.files:
                if k not in zb.files or za[k].shape != zb[k].shape:
                    fdiff = float("inf")
                    continue
                n_arr += 1
                fdiff = max(fdiff, float(np.nanmax(np.abs(za[k].astype(np.float64) - zb[k].astype(np.float64)))) if za[k].size else 0.0)
            out["cells"][name] = {"selection_identical": bool(same_sel), "validation_tables_max_abs_diff": val_diff, "methods_compared": n_methods, "max_abs_diff_metrics": mdiff, "arrays_compared": n_arr, "max_abs_diff_forecasts": fdiff,
                                  "config_hash_identical": json.loads((cdir / "config.json").read_text(encoding="utf-8"))["config_hash"] == json.loads((s / "config.json").read_text(encoding="utf-8"))["config_hash"]}
    # verdicts recomputed by the frozen analysis code from the re-run
    old_results = an.RESULTS
    an.RESULTS = SCR
    (SCR / "analysis").mkdir(exist_ok=True)
    for w in ("W2", "W3", "W1"):
        stored = json.loads((REPO / "analysis" / f"analysis_{w}.json").read_text(encoding="utf-8"))["cells"]
        cells = [(k, H) for k, H in an.CELL_KEYS if (SCR / w / f"{k}_H{H}" / "results.json").exists()]
        if len(cells) != len(stored):
            out["windows"][w] = {"status": f"only {len(cells)} of {len(stored)} cells re-run"}
            continue
        new = an.analyse_window(w, cells)["cells"]
        diff_v, diff_i, diff_h = [], 0.0, 0.0
        for c, v in stored.items():
            for h in ("H1", "H1b", "H2", "H3"):
                if "verdict" in v[h]:
                    if v[h]["verdict"] != new[c][h]["verdict"]:
                        diff_v.append(f"{c}:{h}")
                    diff_i = max(diff_i, abs(v[h]["improvement"] - new[c][h]["improvement"]))
                    diff_h = max(diff_h, abs(v[h]["holm_p"] - new[c][h]["holm_p"]), abs(v[h]["primary"]["p"] - new[c][h]["primary"]["p"]))
        out["windows"][w] = {"cells": len(stored), "verdict_differences": diff_v, "max_abs_diff_improvement": diff_i, "max_abs_diff_p_values": diff_h}
    an.RESULTS = old_results
    for c, r in out["cells"].items():
        r["verdicts_identical"] = all(not out["windows"].get(c.split("/")[0], {}).get("verdict_differences", ["x"]) for _ in [0])
    (HERE / "quality_gate" / "results").mkdir(exist_ok=True)
    (HERE / "quality_gate" / "results" / "e1_reproduction.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    ok = [c for c, r in out["cells"].items() if r.get("selection_identical")]
    print(len(ok), "of", len(out["cells"]), "cells re-run with identical selection;", {w: (v.get("verdict_differences"), v.get("max_abs_diff_improvement")) for w, v in out["windows"].items()})
    print("max metric diff", max((r.get("max_abs_diff_metrics", 0) for r in out["cells"].values() if "max_abs_diff_metrics" in r), default=None), "| max forecast diff", max((r.get("max_abs_diff_forecasts", 0) for r in out["cells"].values() if "max_abs_diff_forecasts" in r), default=None))


if __name__ == "__main__":
    main()
