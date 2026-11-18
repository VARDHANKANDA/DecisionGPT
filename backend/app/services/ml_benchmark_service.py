"""Read model for the ML benchmark runs stored under ``experiments/ml_benchmark_v1/`` (research console, admin only).

Reads files only. Nothing is computed, estimated or written here, and a run flagged ``quick`` (smoke) or carrying a ``SUPERSEDED.md`` is
never shown as a result. Evidence classes (public real data / real transactions / proxy label / synthetic) are carried through unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
RUNS_DIR = ROOT / "experiments" / "ml_benchmark_v1"

_TASK_TITLES = {
    "f1": "Daily unit sales, many series (M5, store CA_1 subset, 28-day direct horizon)",
    "f2": "Demand of one UK online retailer (Online Retail II, 28-day direct horizon)",
    "c1": "Customer inactivity in the next 90 days (Online Retail II; proxy label, not observed churn)",
    "c2": "Customer churn on the synthetic platform file (synthetic label)",
    "p1": "Price-response identification (association vs model counterfactuals)",
    "reproduce": "Recomputation of the earlier stored baselines",
}


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _kind(name: str) -> str:
    return "baseline" if name.startswith("baseline:") else "ensemble" if name.startswith("ensemble:") else "single"


def _forecast_rows(test: dict, best_single: str | None, selected_method: str | None) -> list[dict[str, Any]]:
    """``selected_by_validation``: the method the validation procedure chose (a single model or an ensemble). ``best_single_by_validation``:
    the best individual model on validation. They coincide unless an ensemble won validation."""
    chosen = selected_method.replace("single:", "").replace("(LOO)", "") if selected_method else None
    if best_single is None and selected_method and selected_method.startswith("single:"):
        best_single = chosen
    rows = []
    for name, m in test.items():
        rows.append({
            "method": name, "kind": _kind(name), "wape": m.get("wape"), "mae": m.get("mae"), "rmse": m.get("rmse"), "bias": m.get("bias"),
            "aggregate_daily_wape": m.get("aggregate_daily_wape"), "n_points": m.get("n_points"), "zero_share": m.get("zero_share"),
            "rmsse_mean": m.get("rmsse_mean"), "rmsse_excluded": m.get("rmsse_series_excluded_constant_history"),
            "median_series_wape": m.get("median_series_wape"), "series_with_defined_wape": m.get("series_with_defined_wape"), "n_series": m.get("n_series"),
            "selected_by_validation": name == chosen,
            "best_single_by_validation": name == best_single,
        })
    return sorted(rows, key=lambda r: (r["wape"] is None, r["wape"]))


def _summarise(run_dir: Path) -> dict[str, Any] | None:
    res, meta = _load(run_dir / "results.json"), _load(run_dir / "metadata.json")
    if res is None or meta is None or meta.get("quick") or (run_dir / "SUPERSEDED.md").exists():
        return None
    task = run_dir.name.split("_", 1)[0]
    base: dict[str, Any] = {
        "run_id": run_dir.name, "task": task, "title": _TASK_TITLES.get(task, task), "created_utc": meta.get("created_utc"),
        "git_revision": meta.get("git_revision"), "evidence_class": res.get("evidence_class") or meta.get("evidence_type"),
        "versions": meta.get("versions"), "runtime_seconds": meta.get("runtime_seconds_total"),
    }
    if task == "f1":
        base.update(kind="forecast", sections=[{
            "name": "Daily unit sales", "n_series": res.get("n_series"), "n_test_points": res.get("n_test_points"), "test_window": res.get("test_window"),
            "validation_selected_method": res.get("validation_selected_method"),
            "rows": _forecast_rows(res.get("test", {}), res.get("best_single_by_validation") or None, res.get("validation_selected_method")),
            "paired": res.get("paired_test_comparisons", {}),
        }])
    elif task == "f2":
        base.update(kind="forecast", sections=[])
        for key, label in (("total_daily_revenue", "Total daily revenue (one series)"), ("top20_sku_daily_units", "Top-20 SKU daily units")):
            sec = res.get(key)
            if sec:
                base["sections"].append({
                    "name": label, "n_series": sec.get("n_series"), "n_test_points": sec.get("n_test_points"), "test_window": res.get("test_window"),
                    "validation_selected_method": sec.get("validation_selected_method"),
                    "rows": _forecast_rows(sec.get("test", {}), sec.get("best_single_by_validation"), sec.get("validation_selected_method")),
                    "paired": sec.get("paired_test_comparisons", {}),
                })
    elif task in ("c1", "c2"):
        rows = []
        for name, v in (res.get("models") or {}).items():
            u = (v.get("uncalibrated") or {}).get("test", {})
            rows.append({"method": name, "roc_auc": u.get("roc_auc"), "pr_auc": u.get("pr_auc"), "brier": u.get("brier"), "ece": u.get("ece"),
                         "brier_prevalence_baseline": u.get("brier_prevalence_baseline"), "log_loss": u.get("log_loss"), "n_test": u.get("n"), "test_prevalence": u.get("prevalence"),
                         "isotonic_ece": ((v.get("isotonic") or {}).get("test") or {}).get("ece"),
                         "sigmoid_ece": ((v.get("sigmoid") or {}).get("test") or {}).get("ece"),
                         "selected_by_validation": name == res.get("best_single_by_validation_auc")})
        base.update(kind="classification", rows=rows, rows_per_split=res.get("rows"), prevalence=res.get("prevalence"),
                    temporal_integrity=res.get("temporal_integrity"), paired=res.get("paired_vs_best_single_by_validation_auc", {}),
                    best_single=res.get("best_single_by_validation_auc"))
    elif task == "p1":
        m5 = res.get("m5_ca1_subset", {})
        base.update(kind="price_identification", fixed_effects={k: m5.get(k) for k in ("fixed_effects_all_days", "fixed_effects_positive_sales_days")},
                    price_variation=m5.get("price_variation"), model_counterfactuals=m5.get("model_counterfactuals"),
                    platform=res.get("platform_synthetic"), reading=res.get("reading"))
    elif task == "reproduce":
        s = res.get("summary", {})
        base.update(kind="reproduction", summary=s)
    else:
        return None
    return base


def latest_results() -> dict[str, Any]:
    if not RUNS_DIR.exists():
        return {"available": False, "runs": [], "message": "No benchmark runs are stored yet."}
    latest: dict[str, dict[str, Any]] = {}
    for d in sorted(p for p in RUNS_DIR.iterdir() if p.is_dir()):
        s = _summarise(d)
        if s is not None:
            latest[s["task"]] = s  # directories sort by timestamp: the newest valid run per task wins
    order = ["f1", "f2", "c1", "c2", "p1", "reproduce"]
    runs = [latest[t] for t in order if t in latest]
    return {
        "available": bool(runs), "runs": runs,
        "reading_notes": [
            "Public benchmark and real-transaction results describe those datasets, not Indian SMEs.",
            "The customer-inactivity label is a proxy; the synthetic churn label comes from a known generator.",
            "Ensembles are shown next to the best single model; none was supported by the paired comparisons.",
        ],
    }
