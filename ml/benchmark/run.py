"""Benchmark CLI.

    python -m ml.benchmark.run f1            # M5 CA_1 subset, direct H=28, rolling-origin validation, untouched final window
    python -m ml.benchmark.run f2            # UCI Online Retail II: total revenue and top-20 SKU units
    python -m ml.benchmark.run c1            # Online Retail II customer INACTIVITY (proxy label), temporal splits
    python -m ml.benchmark.run c2            # synthetic platform churn (labelled synthetic)
    python -m ml.benchmark.run reproduce     # recompute the provisional baselines from the original files / code
    python -m ml.benchmark.run f1 --quick    # smoke run (few series, one origin, one variant per family); NOT a result

Each run writes a NEW ``experiments/ml_benchmark_v1/<run_id>/`` (config.json, metadata.json, results.json). Nothing existing is overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from ml.benchmark import datasets as ds
from ml.benchmark import direct
from ml.benchmark import models as zoo

ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = ROOT / "experiments" / "ml_benchmark_v1"


def _git_rev() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def _versions() -> dict[str, str]:
    import catboost, lightgbm, pandas, scipy, sklearn, xgboost  # noqa: E401

    return {"python": sys.version.split()[0], "platform": platform.platform(), "numpy": np.__version__, "pandas": pandas.__version__,
            "scipy": scipy.__version__, "scikit-learn": sklearn.__version__, "xgboost": xgboost.__version__,
            "lightgbm": lightgbm.__version__, "catboost": catboost.__version__}


def _run_dir(task: str, config: dict) -> tuple[str, Path]:
    h = hashlib.sha256(json.dumps(config, sort_keys=True, default=str).encode()).hexdigest()[:8]
    rid = f"{task}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{h}"
    out = OUT_ROOT / rid
    out.mkdir(parents=True, exist_ok=False)
    return rid, out


def _write(out: Path, config: dict, meta: dict, results: dict, preds: dict | None = None) -> None:
    (out / "config.json").write_text(json.dumps(config, indent=2, default=str), encoding="utf-8")
    (out / "metadata.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    (out / "results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    if preds:
        np.savez_compressed(out / "test_predictions.npz", **{k.replace(":", "__"): v for k, v in preds.items()})


def _meta(run_id: str, t0: float, evidence: str, dataset: Any, seed: int, quick: bool = False) -> dict:
    return {"run_id": run_id, "created_utc": datetime.now(timezone.utc).isoformat(), "git_revision": _git_rev(), "versions": _versions(),
            "runtime_seconds_total": round(time.time() - t0), "quick": quick, "evidence_type": evidence, "dataset": dataset, "seed": seed}


# ------------------------------------------------------------------------------------------------ F1: M5
def run_f1(quick: bool = False, seed: int = 42, H: int = 28) -> Path:
    t0 = time.time()
    m = ds.load_m5_subset(n_series=60 if quick else 350)
    static = {k: m.meta[c].astype("category").cat.codes.to_numpy() for k, c in
              (("dept_code", "dept_id"), ("cat_code", "cat_id"), ("item_code", "item_id"))}
    test_lo = ds.M5_LAST_TRAIN_DAY  # 0-based index of d_1914
    val_origins = [test_lo - H * k for k in (3, 2, 1)]
    if quick:
        val_origins = val_origins[-1:]
    families = {f: (list(v) if not quick else [list(v)[0]]) for f, v in zoo.GRID.items()}
    config = {"task": "f1_m5_ca1_direct_h28", "H": H, "seed": seed, "n_series": len(m.meta), "store": "CA_1", "quick": quick,
              "test_window_days": [test_lo + 1, test_lo + H], "validation_windows_days": [[o + 1, o + H] for o in val_origins],
              "train_span_days": 730, "families": families}
    rid, out = _run_dir("f1", config)
    r = direct.run_direct(m.y, m.price, m.calendar, static, H=H, test_lo=test_lo, val_origins=val_origins, train_span=730,
                          families=families, seed=seed, log=lambda s: print(s, flush=True))
    res = r["results"]
    res.update({"task": "Daily unit sales, 28-day direct horizon, global models, M5 store CA_1 subset",
                "evidence_class": "public_benchmark_real_data",
                "test_window": [str(m.calendar.date.iloc[test_lo].date()), str(m.calendar.date.iloc[test_lo + H - 1].date())],
                "notes": ["The test window is scored once, after variant and method selection on validation only.",
                          "Rows where the item has no selling price (not yet on sale) are excluded from training and scoring."]})
    config["features"] = res["features"]
    _write(out, config, _meta(rid, t0, "public_benchmark_data (M5, Walmart)", m.info, seed, quick), res, r["predictions"])
    print("wrote", out)
    return out


# ------------------------------------------------------------------------------------------------ F2: Online Retail II
def run_f2(seed: int = 42, quick: bool = False) -> Path:
    from ml.benchmark import f2_retail

    t0 = time.time()
    fams = {f: ([list(v)[0]] if quick else list(v)) for f, v in zoo.GRID.items()}
    config = {"task": "f2_online_retail_ii_direct_h28", "H": f2_retail.H, "seed": seed, "families": fams, "quick": quick,
              "train_span_days": f2_retail.TRAIN_SPAN}
    rid, out = _run_dir("f2", config)
    r = f2_retail.run_f2(seed=seed, families=fams, log=lambda s: print(s, flush=True))
    res = r["results"]
    res["evidence_class"] = "real_single_business_transactions (UCI Online Retail II)"
    flat = {}
    for task, p in r["predictions"].items():
        for k, v in p.items():
            flat[f"{task}__{k}"] = v
    _write(out, config, _meta(rid, t0, "public_real_transactions (UCI Online Retail II)", res.get("dataset"), seed, quick), res, flat)
    print("wrote", out)
    return out


# ------------------------------------------------------------------------------------------------ C1 / C2
def run_c1(seed: int = 42) -> Path:
    from ml.benchmark import churn

    t0 = time.time()
    d, info = ds.load_online_retail_ii()
    sp = churn.build_real_splits(d)
    integ = churn.check_temporal_integrity(d)
    if not all(v for k, v in integ.items() if k != "data_last_day"):
        raise RuntimeError(f"temporal integrity check failed: {integ}")
    feats = churn.FEATURES
    tr, va, te = sp["train"], sp["validation"], sp["test"]
    config = {"task": "c1_online_retail_ii_inactivity_90d", "seed": seed, "label": "no purchase in the 90 days after cutoff (PROXY, not churn)",
              "cutoffs": churn.CUTOFFS, "window_days": churn.WINDOW_DAYS, "features": feats, "cost_fp": churn.COST_FP, "cost_fn": churn.COST_FN}
    rid, out = _run_dir("c1", config)
    r = churn.evaluate_classifiers(tr[feats].to_numpy(float), tr["inactive_90d"].to_numpy(), va[feats].to_numpy(float), va["inactive_90d"].to_numpy(),
                                   te[feats].to_numpy(float), te["inactive_90d"].to_numpy(), groups_train=tr["customer_id"].to_numpy(), seed=seed)
    r.update({"evidence_class": "real_data_proxy_label (inactivity, NOT observed churn)", "temporal_integrity": integ,
              "rows": {"train": int(len(tr)), "validation": int(len(va)), "test": int(len(te))},
              "prevalence": {"train": float(tr["inactive_90d"].mean()), "validation": float(va["inactive_90d"].mean()), "test": float(te["inactive_90d"].mean())},
              "unique_customers": {"train": int(tr["customer_id"].nunique()), "validation": int(va["customer_id"].nunique()), "test": int(te["customer_id"].nunique())}})
    _write(out, config, _meta(rid, t0, "public_real_transactions_proxy_label", info, seed), r)
    print("wrote", out)
    return out


def run_c2(seed: int = 42) -> Path:
    import pandas as pd
    from sklearn.model_selection import train_test_split

    from ml.benchmark import churn

    t0 = time.time()
    path = ROOT / "data" / "platform" / "churn" / "customers.csv"
    from ml.features.churn_features import FEATURE_COLUMNS as PROD_FEATURES, build_churn_features

    df = build_churn_features(pd.read_csv(path))
    feats = list(PROD_FEATURES)  # identical permissible information to the production model (support_tickets / discount_usage_rate are
    #                              deliberately excluded there: a business cannot supply them at inference)
    # stratified 64 / 16 / 20 (the dataset has no time dimension; the existing pipeline also splits 80/20 at random)
    dev, te = train_test_split(df, test_size=0.20, stratify=df["churned"], random_state=seed)
    tr, va = train_test_split(dev, test_size=0.20, stratify=dev["churned"], random_state=seed)
    config = {"task": "c2_platform_churn_synthetic", "seed": seed, "features": feats, "split": "stratified 64/16/20", "feature_set": "production FEATURE_COLUMNS", "file": str(path.relative_to(ROOT)),
              "cost_fp": churn.COST_FP, "cost_fn": churn.COST_FN}
    rid, out = _run_dir("c2", config)
    r = churn.evaluate_classifiers(tr[feats].to_numpy(float), tr["churned"].to_numpy(), va[feats].to_numpy(float), va["churned"].to_numpy(),
                                   te[feats].to_numpy(float), te["churned"].to_numpy(), groups_train=None, seed=seed)
    r.update({"evidence_class": "SYNTHETIC label drawn from a known logistic mechanism (scripts/generate_platform_data.py)",
              "rows": {"train": int(len(tr)), "validation": int(len(va)), "test": int(len(te))}})
    _write(out, config, _meta(rid, t0, "synthetic", {"file": config["file"], "sha256": ds.sha256_of(path)}, seed), r)
    print("wrote", out)
    return out


def run_p1(seed: int = 42) -> Path:
    """Price-response identification on M5 (CA_1 subset) and on the synthetic platform file used by the production forecaster."""
    from ml.benchmark import features as ft
    from ml.benchmark import price_identification as pid

    t0 = time.time()
    H = 28
    m = ds.load_m5_subset()
    static = {k: m.meta[c].astype("category").cat.codes.to_numpy() for k, c in
              (("dept_code", "dept_id"), ("cat_code", "cat_id"), ("item_code", "item_id"))}
    test_lo = ds.M5_LAST_TRAIN_DAY
    test_hi = test_lo + H - 1
    month_idx = (m.calendar["date"].dt.year * 12 + m.calendar["date"].dt.month).to_numpy()
    dow = m.calendar["dow"].to_numpy()
    cfg = {"task": "p1_price_identification", "seed": seed, "H": H, "scenario": "price x(1+pct) on every scored day of the final window, all price-derived features recomputed",
           "model_variants": {"linear": "linear:ols", "hist_gradient_boosting": "hist_gradient_boosting:depth6", "xgboost": "xgboost:depth6",
                              "lightgbm": "lightgbm:tweedie", "catboost": "catboost:depth6"}}
    rid, out = _run_dir("p1", cfg)

    res: dict[str, Any] = {"m5_ca1_subset": {}, "platform_synthetic": {}}
    # (1) identification: within-item fixed effects on the TRAINING period only (days before the scored window)
    res["m5_ca1_subset"]["fixed_effects_all_days"] = pid.within_item_elasticity(m.y, m.price, dow, month_idx, t_lo=0, t_hi=test_lo - 1)
    res["m5_ca1_subset"]["fixed_effects_positive_sales_days"] = pid.within_item_elasticity(m.y, m.price, dow, month_idx, t_lo=0, t_hi=test_lo - 1, positive_only=True)
    # share of item-weeks with a price change; the variation that identifies the coefficient
    pr = m.price[:, :test_lo]
    chg = ~np.isclose(pr[:, 1:], pr[:, :-1], equal_nan=True) & ~np.isnan(pr[:, 1:]) & ~np.isnan(pr[:, :-1])
    res["m5_ca1_subset"]["price_variation"] = {"share_of_item_days_with_price_change": float(chg.mean()),
                                               "items_with_any_price_change": int((chg.sum(axis=1) > 0).sum()), "n_items": int(len(m.meta))}

    # (2) what the fitted models do under a counterfactual price (property of the model, not of demand)
    F0, names = ft.build_direct_features(m.y, m.price, m.calendar, static, H)
    valid = ft.valid_mask(m.y, m.price, H)
    Xtr, ytr, _, _ = direct.rows(F0, valid, m.y, test_lo - 730, test_lo - 1)
    _, _, s_te, d_te = direct.rows(F0, valid, m.y, test_lo, test_hi)
    models = {}
    for fam, cid in cfg["model_variants"].items():
        f, v = cid.split(":")
        models[fam] = zoo.build(f, v, names, seed).fit(Xtr, ytr)
    for pct in (-10, 10, 25):
        price_cf = m.price.copy()
        price_cf[:, test_lo: test_hi + 1] = price_cf[:, test_lo: test_hi + 1] * (1 + pct / 100)
        F1, _ = ft.build_direct_features(m.y, price_cf, m.calendar, static, H)
        for fam, pr_model in models.items():
            r = pid.model_price_counterfactual(pr_model.predict, F0, F1, (s_te, d_te), pct)
            res["m5_ca1_subset"].setdefault("model_counterfactuals", {}).setdefault(fam, {})[f"{pct:+d}%"] = r

    # (3) the synthetic platform file behind the production forecaster
    import pandas as pd
    import joblib
    from ml.features.forecasting_features import FEATURE_COLUMNS, build_forecasting_features

    df = pd.read_csv(ROOT / "data" / "platform" / "forecasting" / "sales_timeseries.csv")
    ds_info = {"rows": int(len(df)), "series": int(df["series_id"].nunique())}
    g = df.groupby("series_id")["price"]
    ds_info["within_series_price_cv_mean"] = float((g.std() / g.mean()).mean())
    ds_info["distinct_prices_per_series_median"] = int(g.nunique().median())
    ds_info["pooled_corr_price_units"] = float(df["price"].corr(df["units_sold"]))
    lp = np.log(df["price"]); lu = np.log1p(df["units_sold"])
    lpc = lp - lp.groupby(df["series_id"]).transform("mean"); luc = lu - lu.groupby(df["series_id"]).transform("mean")
    ds_info["within_series_loglog_slope_ols"] = float((lpc * luc).sum() / (lpc ** 2).sum())
    res["platform_synthetic"]["data"] = ds_info
    feat = build_forecasting_features(df)
    model = joblib.load(ROOT / "models" / "sales_forecast_xgboost" / "v1" / "model.joblib")
    X0 = feat[FEATURE_COLUMNS].copy()
    base = np.asarray(model.predict(X0), dtype=float)
    cf = {}
    for pct in (-10, 10, 25):
        X1 = X0.copy(); X1["price"] = X1["price"] * (1 + pct / 100)
        d = np.asarray(model.predict(X1), dtype=float) - base
        cf[f"{pct:+d}%"] = {"mean_change_pct_of_total": float(d.sum() / base.sum() * 100), "share_rows_decrease": float(np.mean(d < -1e-9)),
                            "share_rows_increase": float(np.mean(d > 1e-9)), "share_rows_unchanged": float(np.mean(np.abs(d) <= 1e-9)), "n_rows": int(len(d))}
    res["platform_synthetic"]["production_xgboost_v1_counterfactuals_on_training_file_rows"] = cf
    res["reading"] = ["Fixed-effects coefficients are associations (promotions, availability and seasonality are not randomised).",
                      "Model counterfactuals describe the fitted model; a model trained without identifying price variation has no reliable price response.",
                      "No elasticity is imposed and no sign is forced."]
    _write(out, cfg, _meta(rid, t0, "public_benchmark_data + synthetic", {"m5": m.info, "platform": ds_info}, seed), res)
    print("wrote", out)
    return out


def run_reproduce(seed: int = 42) -> Path:
    """Recompute the provisional baselines from the ORIGINAL files with the ORIGINAL code paths (no persistence, no registry writes) and
    store them next to the values recorded earlier. Differences are reported, not smoothed."""
    import pandas as pd

    from ml.pipeline.loaders import load_platform_dataset
    from ml.training import train_churn, train_forecasting

    t0 = time.time()
    config = {"task": "reproduce_baselines", "seed": seed}
    rid, out = _run_dir("reproduce", config)
    stored: dict[str, dict] = {}
    for line in open(ROOT / "models" / "registry_index.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r["version"] == "v1" and r["dataset_version"] in ("platform-forecasting-v1", "platform-churn-v1"):
            stored[r["model_name"]] = r["metrics"]
    res: dict[str, Any] = {"forecasting_platform_synthetic": {}, "churn_platform_synthetic": {}, "model_comparison": {}}
    f_df = load_platform_dataset("forecasting", "sales_timeseries.csv").dataframe
    for mt in train_forecasting.SUPPORTED_MODEL_TYPES:
        m = train_forecasting.train_one(f_df, mt, seed)["metrics"]
        ref = stored.get(f"sales_forecast_{mt}", {})
        res["forecasting_platform_synthetic"][mt] = {"recomputed": {k: m[k] for k in ("mae", "rmse", "mape")}, "stored": {k: ref.get(k) for k in ("mae", "rmse", "mape")},
                                                     "max_abs_diff": max(abs(m[k] - ref[k]) for k in ("mae", "rmse", "mape") if k in ref)}
    c_df = load_platform_dataset("churn", "customers.csv").dataframe
    for mt in train_churn.SUPPORTED_MODEL_TYPES:
        m = train_churn.train_one(c_df, mt, seed)["metrics"]
        ref = stored.get(f"churn_{mt}", {})
        keys = ("precision", "recall", "f1", "roc_auc")
        res["churn_platform_synthetic"][mt] = {"recomputed": {k: m[k] for k in keys}, "stored": {k: ref.get(k) for k in keys},
                                               "max_abs_diff": max(abs(m[k] - ref[k]) for k in keys if k in ref)}
    from app.services import model_comparison_service as mcs

    for key in ("pos_daily_revenue", "platform_units"):
        r = mcs.run_dataset(key, seed)
        folder = sorted((ROOT / "experiments" / "model_comparison_v1").glob(f"mc_*_{key}_*"))[-1]
        old = json.loads((folder / "results.json").read_text(encoding="utf-8"))
        cmp = {}
        for mk, v in r["models"].items():
            o = old["models"][mk]
            cmp[mk] = {"recomputed_test_rmse": v["test"]["rmse"], "stored_test_rmse": o["test"]["rmse"], "recomputed_cv_rmse": v["cv_rmse_mean"],
                       "stored_cv_rmse": o["cv_rmse_mean"], "max_abs_diff": max(abs(v["test"]["rmse"] - o["test"]["rmse"]), abs(v["cv_rmse_mean"] - o["cv_rmse_mean"]))}
        res["model_comparison"][key] = {"stored_run": folder.name, "models": cmp,
                                        "recomputed_selected": r["selection"].get("selected")}
    worst = max(x["max_abs_diff"] for part in ("forecasting_platform_synthetic", "churn_platform_synthetic") for x in res[part].values())
    worst_mc = max(m["max_abs_diff"] for d in res["model_comparison"].values() for m in d["models"].values())
    res["summary"] = {"max_abs_diff_registry_metrics": worst, "max_abs_diff_model_comparison": worst_mc,
                      "note": "installed scikit-learn / pandas / xgboost differ from the versions the stored values were produced under; any non-zero difference is reported as is"}
    _write(out, config, _meta(rid, t0, "recomputation_of_stored_baselines", None, seed), res)
    print("wrote", out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ml.benchmark.run")
    ap.add_argument("task", choices=["f1", "f2", "c1", "c2", "p1", "reproduce"])
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args(argv)
    if a.task == "f1":
        run_f1(quick=a.quick, seed=a.seed)
    elif a.task == "f2":
        run_f2(seed=a.seed, quick=a.quick)
    elif a.task == "c1":
        run_c1(seed=a.seed)
    elif a.task == "c2":
        run_c2(seed=a.seed)
    elif a.task == "p1":
        run_p1(seed=a.seed)
    elif a.task == "reproduce":
        run_reproduce(seed=a.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
