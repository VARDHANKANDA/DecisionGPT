"""Build the machine-readable inventory of the existing ML experiments and fingerprint every historical artifact (read-only).

Facts that exist in stored files (config, metadata, results) are read from them; everything else is curated text that was checked against the code
named in ``sources``. Output: ``experiment_inventory.json`` and ``artifact_fingerprints.json`` next to this file.

    python -m research.forecast_study_v1.inventory.build_inventory
"""
from __future__ import annotations

import glob
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
EXP = ROOT / "experiments"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def latest(pattern: str, skip_superseded: bool = True) -> Path:
    dirs = [Path(d) for d in sorted(glob.glob(str(EXP / "ml_benchmark_v1" / pattern))) if not (skip_superseded and (Path(d) / "SUPERSEDED.md").exists())]
    return dirs[-1]


def meta_of(d: Path) -> dict:
    m = json.load(open(d / "metadata.json", encoding="utf-8"))
    return {"run_id": m.get("run_id"), "created_utc": m.get("created_utc"), "git_revision": m.get("git_revision"), "seed": m.get("seed"),
            "runtime_seconds": m.get("runtime_seconds_total"), "versions": m.get("versions"), "quick": m.get("quick")}


def git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


METRIC_DEFS = {
    "mae": "mean(|forecast - actual|) over all (series, day) points; units of the target",
    "rmse": "sqrt(mean((forecast - actual)^2))",
    "wape": "sum|forecast - actual| / sum(actual); None when sum(actual) = 0 (never reported as 0)",
    "bias": "sum(forecast - actual) / sum(actual) (relative bias; positive = over-forecast); None when sum(actual) = 0",
    "rmsse_mean": "per series sqrt(mean e^2 / mean((y_t - y_{t-1})^2 over TRAINING history)); unweighted mean over series; constant-history series excluded and counted",
    "aggregate_daily_wape": "WAPE after summing all series per day (store-day aggregate level); NOT comparable with per-series WAPE",
    "median_series_wape": "median over series of per-series WAPE (series with sum(actual) > 0)",
    "roc_auc": "area under ROC; ranking only", "pr_auc": "average precision", "brier": "mean squared error of the score as a probability",
    "ece": "expected calibration error, 10 equal-width bins on [0,1] (ml/benchmark/churn.py ece)", "log_loss": "negative log-likelihood, scores clipped to [1e-6, 1-1e-6]",
}

SOURCES = {
    "ml_benchmark": ["ml/benchmark/run.py", "ml/benchmark/direct.py", "ml/benchmark/features.py", "ml/benchmark/models.py", "ml/benchmark/evaluate.py", "ml/benchmark/datasets.py"],
}


def build() -> dict:
    f1, f2, c1, c2 = latest("f1_*"), latest("f2_*"), latest("c1_*"), latest("c2_*")
    p1, rep = latest("p1_*"), latest("reproduce_*")
    cfg1 = json.load(open(f1 / "config.json", encoding="utf-8"))
    cfg2 = json.load(open(f2 / "config.json", encoding="utf-8"))
    mc_pos = Path(sorted(glob.glob(str(EXP / "model_comparison_v1" / "*pos*")))[0])
    mc_syn = Path(sorted(glob.glob(str(EXP / "model_comparison_v1" / "*platform*")))[0])
    inv = {
        "inventory_version": 1,
        "built_from_git_revision": git("rev-parse", "--short", "HEAD"),
        "working_tree_modified_paths": len([ln for ln in git("status", "--porcelain").splitlines() if ln.strip()]),
        "note": "Historical results are quoted as stored. Nothing here edits them. 'reproducibility' states what was independently verified in this study.",
        "experiments": [
            {
                "id": "E1_m5_ca1_direct_h28", "run": meta_of(f1) | {"path": str(f1.relative_to(ROOT)).replace("\\", "/")},
                "research_question": "Do global learned models beat seasonal baselines for 28-day-ahead daily unit demand of sparse retail series?",
                "intended_claim": "Boosted trees reduce per-series WAPE relative to seasonal naive; ensembles add nothing. (Exploratory single-window result.)",
                "dataset": {"name": "M5 Forecasting Accuracy, store CA_1, seeded 350-series department-stratified subset", "evidence_class": "public_benchmark_real_data",
                            "source": "Zenodo record 12636070 (files of the M5 competition); licence label cc-by-4.0 set by the uploader, NOT independently verified against the competition rules",
                            "version": "sales_train_evaluation.csv (1,941 days, 2011-01-29..2016-05-22)", "subset_seed": 20261015, "eligibility": "first sale on or before day 1100"},
                "unit_of_observation": "series x day (units sold)", "n_series": 350, "n_test_points": 9800, "target": "units_sold (non-negative integers); 48.7% zeros in the test window",
                "features": "lags H..H+28 (weekly steps), rolling mean 7/28/84, rolling std 28, non-zero share 28, days since last sale, same-weekday mean of 4 lags, calendar, event flag, SNAP flag, selling price + 3 price-derived features, department/category/item codes",
                "feature_availability": "history features use days <= origin (t - H); calendar, event, SNAP and selling price are published in advance",
                "split": {"scheme": "chronological; 3 validation windows of 28 days then one untouched 28-day test window", "validation_windows_days": cfg1["validation_windows_days"], "test_window_days": cfg1["test_window_days"], "train_span_days": cfg1["train_span_days"]},
                "horizon": "28 days, direct strategy, single forecast origin (day 1913)",
                "baselines": ["seasonal_naive_28 (lag_28)", "same_weekday_mean4"], "models": {k: v for k, v in cfg1["families"].items()},
                "hyperparameter_selection": "fixed 2-variant grid per family; variant chosen per family by mean WAPE on the 3 validation origins; test scored once",
                "ensembles": ["mean_all", "mean_top3", "nnls_weighted (weights fitted on validation predictions)"],
                "metrics": {k: METRIC_DEFS[k] for k in ("mae", "rmse", "wape", "bias", "rmsse_mean", "aggregate_daily_wape", "median_series_wape")},
                "uncertainty": "paired series-cluster bootstrap of WAPE differences (2000 draws, seed 42); resamples series only",
                "warnings_and_limitations": ["one forecast origin: results are conditional on a single 28-day window", "series-cluster bootstrap ignores cross-sectional dependence through shared calendar days and store-level shocks",
                                             "one store, 350 of the eligible series: no hierarchy, no between-store generalisation", "tiny fixed hyperparameter grid", "no prediction intervals evaluated"],
                "reproducibility": {"stored_predictions": True, "metrics_recomputed_independently": "audit/recompute_report.json (max |diff| ~5e-10)", "rerun": "audit/reruns (see REPRODUCIBILITY.md)"},
                "sources": SOURCES["ml_benchmark"],
            },
            {
                "id": "E2_online_retail_ii_direct_h28", "run": meta_of(f2) | {"path": str(f2.relative_to(ROOT)).replace("\\", "/")},
                "research_question": "Same protocol as E1 on one real retailer's total revenue and its 20 top SKUs.",
                "intended_claim": "Exploratory: learned models vs baselines on small real series.",
                "dataset": {"name": "UCI Online Retail II (one UK online gift retailer)", "evidence_class": "public_real_transactions", "source": "https://archive.ics.uci.edu/dataset/502/online+retail+ii (doi 10.24432/C5CG6D)",
                            "licence": "CC BY 4.0 (stated on the UCI page)", "version": "2009-12-01..2011-12-09, 1,067,371 source rows", "cleaning": "drop cancellations, non-positive quantity or price, 15 non-product stock codes, exact duplicate lines (counts stored in the run)"},
                "unit_of_observation": "day (revenue) or SKU x day (units)", "targets": {"total_daily_revenue": "1 series, 28 test points", "top20_sku_daily_units": "20 series, 560 test points; SKUs chosen by revenue BEFORE the first validation origin"},
                "features": "same builder as E1 with price/availability and department/category columns dropped; calendar flags incl. Christmas closure window",
                "split": {"scheme": "chronological; 3 validation windows then the final 28 days", "validation_windows": cfg2.get("families") and None, "train_span_days": cfg2["train_span_days"]},
                "horizon": "28 days, direct, single origin", "baselines": ["seasonal_naive", "same_weekday_mean4"], "models": cfg2["families"],
                "hyperparameter_selection": "as E1", "metrics": {k: METRIC_DEFS[k] for k in ("mae", "rmse", "wape", "bias", "aggregate_daily_wape", "median_series_wape")},
                "uncertainty": "series-cluster bootstrap for the 20-SKU task only; none for the single series",
                "warnings_and_limitations": ["28 test points for the revenue series: no inference possible", "single retailer, wholesaler-like customers", "one origin", "currency not stated per line"],
                "reproducibility": {"stored_predictions": True, "metrics_recomputed_independently": "audit/recompute_report.json (max |diff| 0.0)"}, "sources": ["ml/benchmark/f2_retail.py"],
            },
            {
                "id": "E3_online_retail_ii_inactivity_c1", "run": meta_of(c1) | {"path": str(c1.relative_to(ROOT)).replace("\\", "/")},
                "research_question": "How well do classifiers rank customers who will make no purchase in the next 90 days?",
                "intended_claim": "Exploratory ranking performance and calibration on a PROXY label.",
                "dataset": {"name": "UCI Online Retail II customers with a Customer ID", "evidence_class": "real_data_proxy_label", "label": "no invoice in the 90 days after a cutoff (inactivity); NOT observed churn",
                            "licence": "CC BY 4.0"},
                "unit_of_observation": "customer x cutoff snapshot", "rows": {"train": 14805, "validation": 4951, "test": 5256}, "positive_rate": {"train": 0.576, "validation": 0.677, "test": 0.565},
                "features": ["recency_days", "tenure_days", "frequency", "monetary", "avg_order_value", "distinct_skus", "invoices_last_90d", "invoices_last_180d", "revenue_last_90d", "mean_gap_days", "recency_ratio"],
                "feature_availability": "transactions strictly before the cutoff",
                "split": {"scheme": "temporal snapshots: train cutoffs 2010-06-01, 2010-09-01, 2010-12-01, 2011-03-14; validation 2011-06-12; test 2011-09-10; 90-day label windows non-overlapping and ordered"},
                "models": ["logistic_regression", "random_forest", "xgboost", "catboost", "soft_voting", "stacking_logistic_meta"],
                "hyperparameter_selection": "fixed configurations; calibrators (sigmoid, isotonic) and thresholds (F1-max, cost-min) fitted on the validation snapshot only",
                "metrics": {k: METRIC_DEFS[k] for k in ("roc_auc", "pr_auc", "brier", "ece", "log_loss")},
                "warnings_and_limitations": ["label is a proxy", "the same customers appear in several snapshots (temporal, not group-disjoint, split)", "no stored predictions: metrics cannot be recomputed without a rerun",
                                             "thresholded accuracy is not stored (derivable from stored confusion counts)", "assumed costs (FP 1, FN 3) for the cost threshold"],
                "reproducibility": {"stored_predictions": False, "rerun": "audit/reruns"}, "sources": ["ml/benchmark/churn.py"],
            },
            {
                "id": "E4_synthetic_churn_c2", "run": meta_of(c2) | {"path": str(c2.relative_to(ROOT)).replace("\\", "/")},
                "research_question": "Same classifiers on the synthetic platform churn file.",
                "dataset": {"name": "data/platform/churn/customers.csv", "evidence_class": "synthetic_label", "label": "drawn from a known logistic mechanism (generator seed recorded in the data metadata)"},
                "rows": {"train": 3840, "validation": 960, "test": 1200}, "limitations": ["the label is a function of the features by construction: the result measures how well a model recovers the generator, not customer behaviour",
                                                                                          "an earlier c2 run (c2_20261015T073608Z_4598ea68) used columns production excludes and is SUPERSEDED (kept, not used)"],
                "reproducibility": {"stored_predictions": False}, "sources": ["ml/benchmark/churn.py"],
            },
            {
                "id": "E5_price_identification_p1", "run": meta_of(p1), "research_question": "Is a price response identifiable in M5 and in the platform data, and do the models imply one?",
                "claim_type": "NOT a prediction benchmark: fixed-effects association + model counterfactual sweeps", "limitations": ["association only", "no elasticity is imposed"], "reproducibility": {"stored_predictions": False},
            },
            {
                "id": "E6_reproduce", "run": meta_of(rep), "research_question": "Recompute the earlier provisional baselines (registry metrics, model comparison) from original files.",
                "result": "max abs difference 0.0 on both", "reproducibility": {"note": "software versions differ from the original runs; the run records any non-zero difference as is"},
            },
            {
                "id": "E7_pos_register_model_comparison", "run": {"path": str(mc_pos.relative_to(ROOT)).replace("\\", "/"), "run_id": mc_pos.name.split("_", 1)[1], "seed": 42},
                "research_question": "One-day-ahead daily revenue of one real Indian local store: do learned models beat a seasonal naive baseline?",
                "dataset": {"name": "Indian POS register (Kaggle retail-sales-register)", "evidence_class": "real, provenance not independently verified", "licence": "CC BY-NC-SA 4.0", "n_days": 80, "unit": "INR/day"},
                "features": ["lag_1", "lag_7", "rolling_mean_7", "dow_0..dow_6"], "split": {"train": "2025-01-08..2025-03-04 (56 d)", "validation": "2025-03-05..2025-03-16 (12 d)", "test": "2025-03-17..2025-03-31 (12 d)"},
                "hyperparameter_selection": "lowest mean expanding-window CV RMSE (3 folds) among 4 learned models; test unused", "uncertainty": "split-conformal 80% interval; 12 test points",
                "limitations": ["12 test days: any ranking is unstable", "negative R2 for every model", "exclusion rule removes 34,046 of 94,290 lines (qty<=0, non-integer qty, amount mismatch)"],
                "reproducibility": {"rerun": "reproduce run recomputed it with max |diff| 0.0"},
            },
            {
                "id": "E8_platform_units_model_comparison", "run": {"path": str(mc_syn.relative_to(ROOT)).replace("\\", "/"), "run_id": mc_syn.name.split("_", 1)[1], "seed": 42},
                "dataset": {"name": "Synthetic D2C platform", "evidence_class": "synthetic", "n_series": 40, "n_days": 710},
                "limitations": ["synthetic generator; results describe the generator"], "reproducibility": {"rerun": "reproduce run: max |diff| 0.0"},
            },
            {
                "id": "E9_real_public_own_history_backtests", "run": {"path": "experiments/real_world_validation_v1/results.json", "git_revision": "41c1d14"},
                "research_question": "How do the product's own forecasting methods do in a chronological own-history backtest on real public retail series?",
                "datasets": ["Indian POS register (90 d)", "Indian e-commerce, Benroshan (365 d, ~500 orders)", "UCI Online Retail II (739 d)"], "horizons": [7, 14, 28], "origin_step_days": 7,
                "baselines": ["naive_last", "seasonal_naive_7", "trailing_mean_28"], "limitations": ["a handful of overlapping origins; coverage is dependent", "not a DecisionGPT customer business"],
                "reproducibility": {"stored_predictions": False},
            },
            {
                "id": "E10_registered_platform_models", "run": {"path": "models/registry_index.jsonl", "trained": "2026-08-30", "seed": 42},
                "dataset": {"name": "platform-forecasting-v1 / platform-churn-v1", "evidence_class": "synthetic"},
                "models": ["sales_forecast_naive|linear|xgboost", "churn_logistic_regression|random_forest|xgboost"],
                "metrics_recorded": "forecast: MAE, RMSE, MAPE; churn: precision, recall, F1 (default 0.5 cut-off), ROC-AUC",
                "limitations": ["synthetic data", "the churn label is generated from recency and tenure, which are also features", "no PR-AUC, calibration, confusion matrix, baseline MAE or sample counts recorded"],
            },
            {
                "id": "E11_business_specific_validation", "status": "no stored result on any real business",
                "detail": "forecast_validation_service (own-history rolling-origin backtest) and customer-score validation exist and are tested; the development database holds 0 forecast_eval and 0 customer_eval runs and 0 outcome observations.",
            },
        ],
        "metric_definitions": METRIC_DEFS,
    }
    return inv


def fingerprints() -> dict:
    files = {}
    roots = [EXP / "ml_benchmark_v1", EXP / "model_comparison_v1", EXP / "real_world_validation_v1", ROOT / "models" / "registry_index.jsonl", ROOT / "data" / "external" / "DATASET_REGISTRY.json",
             EXP / "experiment_manifest.json"]
    for r in roots:
        paths = [r] if r.is_file() else [p for p in sorted(r.rglob("*")) if p.is_file()]
        for p in paths:
            files[str(p.relative_to(ROOT)).replace("\\", "/")] = sha(p)
    return {"git_revision": git("rev-parse", "HEAD"), "n_files": len(files), "sha256": files}


if __name__ == "__main__":
    (HERE / "experiment_inventory.json").write_text(json.dumps(build(), indent=2, default=str), encoding="utf-8")
    fp = fingerprints()
    (HERE / "artifact_fingerprints.json").write_text(json.dumps(fp, indent=2), encoding="utf-8")
    print("inventory written;", fp["n_files"], "artifacts fingerprinted at", fp["git_revision"][:10])
