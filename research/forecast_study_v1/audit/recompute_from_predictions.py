"""Independent recomputation of the historical forecast benchmark metrics from the STORED prediction arrays.

The metric code here is written from the metric definitions (docs/ML_BENCHMARK_REPORT.md; ml/benchmark/evaluate.py docstring), not imported from the
historical evaluator, so agreement is evidence that the stored numbers follow from the stored predictions and the stated definitions.

Read-only: it opens ``experiments/ml_benchmark_v1/*`` for reading and writes ``audit/recompute_report.json`` next to this file.

    python -m research.forecast_study_v1.audit.recompute_from_predictions
"""
from __future__ import annotations

import glob
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HIST = ROOT / "experiments" / "ml_benchmark_v1"
OUT = Path(__file__).resolve().parent / "recompute_report.json"


# ---- metric definitions (independent implementation) ------------------------------------------------------------------------------------
def wape(y, p):
    d = float(np.sum(np.abs(y)))
    return float(np.sum(np.abs(p - y)) / d) if d > 0 else None


def metrics(y, p, series, day, scale=None):
    e = p - y
    out = {"n_points": int(y.size), "n_series": int(np.unique(series).size), "mae": float(np.mean(np.abs(e))), "rmse": float(np.sqrt(np.mean(e * e))),
           "wape": wape(y, p), "bias": float(e.sum() / y.sum()) if y.sum() > 0 else None, "zero_share": float(np.mean(y == 0))}
    per, rms, excluded = [], [], 0
    for s in np.unique(series):
        m = series == s
        w = wape(y[m], p[m])
        if w is not None:
            per.append(w)
        if scale is not None:
            sc = scale.get(int(s))
            if sc and sc > 0:
                rms.append(float(np.sqrt(np.mean(e[m] ** 2) / sc)))
            else:
                excluded += 1
    out["median_series_wape"] = float(np.median(per)) if per else None
    out["series_with_defined_wape"] = len(per)
    if scale is not None:
        out["rmsse_mean"] = float(np.mean(rms)) if rms else None
        out["rmsse_series_excluded_constant_history"] = excluded
    days = np.unique(day)
    ya = np.array([y[day == d].sum() for d in days])
    pa = np.array([p[day == d].sum() for d in days])
    out["aggregate_daily_wape"] = wape(ya, pa)
    out["aggregate_daily_mae"] = float(np.mean(np.abs(pa - ya)))
    return out


def compare(stored: dict, mine: dict, tol=1e-9):
    diffs, missing = {}, []
    for k, v in mine.items():
        if k not in stored:
            continue
        s = stored[k]
        if v is None or s is None:
            if (v is None) != (s is None):
                diffs[k] = "one side undefined"
            continue
        diffs[k] = abs(float(v) - float(s))
    bad = {k: d for k, d in diffs.items() if d == "one side undefined" or d > tol * max(1.0, abs(float(stored[k])))}
    return diffs, bad


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    report: dict = {"purpose": "recompute stored metrics from stored predictions with independent code", "runs": {}}
    # ---------------- f1: M5 ----------------
    f1 = Path(sorted(glob.glob(str(HIST / "f1_*")))[-1])
    res = json.load(open(f1 / "results.json", encoding="utf-8"))
    z = np.load(f1 / "test_predictions.npz")
    y, s, d = z["y"].astype(np.float64), z["series"], z["day"]
    from ml.benchmark import datasets as ds  # loader only (raw M5 files, read-only): needed for the training history used by RMSSE

    m5 = ds.load_m5_subset(n_series=350)
    cfg = json.load(open(f1 / "config.json", encoding="utf-8"))
    test_lo, test_hi = cfg["test_window_days"][0] - 1, cfg["test_window_days"][1] - 1       # 1-based day numbers in the config -> 0-based indices
    hist = m5.y[:, :test_lo].astype(np.float64)
    dd = np.diff(hist, axis=1)
    scale = {i: float(v) for i, v in enumerate(np.mean(dd ** 2, axis=1))}
    checks = {
        "n_rows_equals_series_times_days": bool(len(y) == 350 * 28),
        "test_days_inside_declared_window": bool(d.min() >= test_lo and d.max() <= test_hi and np.unique(d).size == 28),
        "y_equals_raw_target_at_those_cells": bool(np.array_equal(y, m5.y[s, d].astype(np.float64))),
        "test_window_is_the_last_28_days_of_the_file": bool(test_hi == m5.y.shape[1] - 1 and test_lo == m5.y.shape[1] - 28),
        "scale_uses_history_strictly_before_test_window": bool(hist.shape[1] == test_lo),
    }
    method_rows, worst = {}, 0.0
    names = [k for k in z.files if k not in ("y", "series", "day")]
    for key in names:
        method = key.replace("__", ":")
        if method not in res["test"]:
            method_rows[method] = {"status": "prediction array has no stored metric row"}
            continue
        mine = metrics(y, z[key].astype(np.float64), s, d, scale)
        diffs, bad = compare(res["test"][method], mine)
        num = [v for v in diffs.values() if isinstance(v, float)]
        worst = max(worst, max(num) if num else 0.0)
        method_rows[method] = {"compared_metrics": sorted(diffs), "max_abs_diff": max(num) if num else 0.0, "mismatches": bad}
    report["runs"][f1.name] = {"checks": checks, "methods": method_rows, "max_abs_diff_all_methods": worst,
                               "prediction_file_sha256": sha(f1 / "test_predictions.npz"), "results_file_sha256": sha(f1 / "results.json"),
                               "all_match": bool(all(checks.values()) and all(not r.get("mismatches") for r in method_rows.values()))}
    # ---------------- f2: Online Retail II ----------------
    f2 = Path(sorted(glob.glob(str(HIST / "f2_*")))[-1])
    res2 = json.load(open(f2 / "results.json", encoding="utf-8"))
    z2 = np.load(f2 / "test_predictions.npz")
    out2, worst2 = {}, 0.0
    for task in ("total_daily_revenue", "top20_sku_daily_units"):
        y2, s2, d2 = (z2[f"{task}__{k}"].astype(np.float64) for k in ("y", "series", "day"))
        task_rows = {}
        for key in [k for k in z2.files if k.startswith(task + "__") and k.split("__", 1)[1] not in ("y", "series", "day")]:
            method = key.split("__", 1)[1].replace("__", ":")
            if method not in res2[task]["test"]:
                task_rows[method] = {"status": "no stored metric row"}
                continue
            mine = metrics(y2, z2[key].astype(np.float64), s2.astype(int), d2)
            mine.pop("rmsse_mean", None)
            diffs, bad = compare(res2[task]["test"][method], mine)
            num = [v for v in diffs.values() if isinstance(v, float)]
            worst2 = max(worst2, max(num) if num else 0.0)
            task_rows[method] = {"max_abs_diff": max(num) if num else 0.0, "mismatches": bad}
        out2[task] = {"n_points": int(y2.size), "n_series": int(np.unique(s2).size), "methods": task_rows}
    report["runs"][f2.name] = {"tasks": out2, "max_abs_diff_all_methods": worst2, "rmsse_not_recomputed": "needs the per-series training history; not stored with the predictions",
                               "prediction_file_sha256": sha(f2 / "test_predictions.npz"), "results_file_sha256": sha(f2 / "results.json"),
                               "all_match": bool(all(not r.get("mismatches") for t in out2.values() for r in t["methods"].values()))}
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    ok = all(r["all_match"] for r in report["runs"].values())
    print(json.dumps({k: {"all_match": v["all_match"], "max_abs_diff": v["max_abs_diff_all_methods"]} for k, v in report["runs"].items()}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
