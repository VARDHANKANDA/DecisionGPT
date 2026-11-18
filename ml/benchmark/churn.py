"""Customer-inactivity / churn classification benchmark.

Evidence classes are never mixed:
  * ``real_proxy_label``  - UCI Online Retail II. The source has NO churn field. The label is *purchase inactivity*: no invoice in the 90
    days after a cutoff, for customers seen before it. It is a documented operational proxy for non-contractual churn, NOT observed
    churn, and is reported as "inactivity prediction on a real retailer".
  * ``synthetic_label``   - ``data/platform/churn/customers.csv``; the label is drawn from a known logistic mechanism.

Temporal design (real data): features use transactions strictly before the cutoff; the label window is (cutoff, cutoff+90d];
train cutoffs have non-overlapping label windows that all end before the validation cutoff, which ends before the test cutoff.
Calibrators and decision thresholds are fitted on the validation snapshot only. Stacking uses out-of-fold base predictions
(customer-grouped folds), so the meta-model never sees in-sample base predictions.
"""
from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

WINDOW_DAYS = 90
CUTOFFS = {
    "train": ["2010-06-01", "2010-09-01", "2010-12-01", "2011-03-14"],
    "validation": "2011-06-12",
    "test": "2011-09-10",
}
FEATURES = ["recency_days", "tenure_days", "frequency", "monetary", "avg_order_value", "distinct_skus", "invoices_last_90d",
            "invoices_last_180d", "revenue_last_90d", "mean_gap_days", "recency_ratio"]
COST_FP, COST_FN = 1.0, 3.0  # ASSUMED business costs (stated in the report): missing an inactive customer costs 3x a wasted contact


# ------------------------------------------------------------------------------------------------ real data snapshots
def snapshot(d: pd.DataFrame, cutoff: str, window: int = WINDOW_DAYS) -> pd.DataFrame:
    c = pd.Timestamp(cutoff)
    e = c + pd.Timedelta(days=window)
    known = d[d["Customer ID"].notna()]
    past = known[known["day"] < c]
    fut = known[(known["day"] >= c) & (known["day"] < e)]
    inv = past.drop_duplicates(["Customer ID", "Invoice"])
    g = past.groupby("Customer ID")
    f = pd.DataFrame({
        "first_day": g["day"].min(), "last_day": g["day"].max(), "monetary": g["revenue"].sum(), "distinct_skus": g["StockCode"].nunique(),
    })
    gi = inv.groupby("Customer ID")
    f["frequency"] = gi["Invoice"].nunique()
    f["recency_days"] = (c - f["last_day"]).dt.days
    f["tenure_days"] = (c - f["first_day"]).dt.days
    f["avg_order_value"] = f["monetary"] / f["frequency"].clip(lower=1)
    for w in (90, 180):
        f[f"invoices_last_{w}d"] = inv[inv["day"] >= c - pd.Timedelta(days=w)].groupby("Customer ID")["Invoice"].nunique().reindex(f.index).fillna(0)
    f["revenue_last_90d"] = past[past["day"] >= c - pd.Timedelta(days=90)].groupby("Customer ID")["revenue"].sum().reindex(f.index).fillna(0.0)
    span = (f["last_day"] - f["first_day"]).dt.days
    f["mean_gap_days"] = np.where(f["frequency"] > 1, span / (f["frequency"] - 1).clip(lower=1), np.nan)
    f["mean_gap_days"] = f["mean_gap_days"].fillna(f["tenure_days"].clip(lower=1))
    f["recency_ratio"] = f["recency_days"] / f["tenure_days"].clip(lower=1)
    active = set(fut["Customer ID"].unique())
    f["inactive_90d"] = (~f.index.isin(active)).astype(int)
    f["cutoff"] = cutoff
    f = f.reset_index().rename(columns={"Customer ID": "customer_id"})
    return f[["customer_id", "cutoff"] + FEATURES + ["inactive_90d"]]


def build_real_splits(d: pd.DataFrame) -> dict[str, pd.DataFrame]:
    tr = pd.concat([snapshot(d, c) for c in CUTOFFS["train"]], ignore_index=True)
    return {"train": tr, "validation": snapshot(d, CUTOFFS["validation"]), "test": snapshot(d, CUTOFFS["test"])}


def check_temporal_integrity(d: pd.DataFrame) -> dict[str, Any]:
    last = d["day"].max()
    ends = {k: [pd.Timestamp(c) + pd.Timedelta(days=WINDOW_DAYS) for c in (v if isinstance(v, list) else [v])] for k, v in CUTOFFS.items()}
    ok = (max(ends["train"]) <= pd.Timestamp(CUTOFFS["validation"]) and max(ends["validation"]) <= pd.Timestamp(CUTOFFS["test"])
          and max(ends["test"]) <= last + pd.Timedelta(days=1))
    tr = sorted(pd.Timestamp(c) for c in CUTOFFS["train"])
    nonoverlap = all(tr[i] + pd.Timedelta(days=WINDOW_DAYS) <= tr[i + 1] for i in range(len(tr) - 1))
    return {"label_windows_precede_next_cutoff": bool(ok), "train_label_windows_non_overlapping": bool(nonoverlap),
            "data_last_day": str(last.date())}


# ------------------------------------------------------------------------------------------------ models
def base_models(seed: int, names: list[str] | None = None) -> dict[str, Any]:
    from catboost import CatBoostClassifier
    from xgboost import XGBClassifier

    return {
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, random_state=seed)),
        "random_forest": RandomForestClassifier(n_estimators=200, max_depth=8, min_samples_leaf=5, n_jobs=2, random_state=seed),
        "xgboost": XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, eval_metric="logloss",
                                 n_jobs=2, random_state=seed, verbosity=0),
        "catboost": CatBoostClassifier(iterations=300, depth=6, learning_rate=0.05, random_seed=seed, thread_count=2, verbose=0,
                                       allow_writing_files=False),
    }


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    tot = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            tot += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(tot)


def prob_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    prev = float(y.mean())
    return {"roc_auc": float(roc_auc_score(y, p)), "pr_auc": float(average_precision_score(y, p)), "brier": float(brier_score_loss(y, p)),
            "brier_prevalence_baseline": float(brier_score_loss(y, np.full_like(p, prev))), "log_loss": float(log_loss(y, p)), "ece": ece(y, p),
            "prevalence": prev, "n": int(len(y))}


def threshold_metrics(y: np.ndarray, p: np.ndarray, thr: float) -> dict[str, float]:
    pred = p >= thr
    tp = int(np.sum(pred & (y == 1)))
    fp = int(np.sum(pred & (y == 0)))
    fn = int(np.sum(~pred & (y == 1)))
    tn = int(np.sum(~pred & (y == 0)))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"threshold": float(thr), "precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "cost": float(COST_FP * fp + COST_FN * fn), "cost_per_customer": float((COST_FP * fp + COST_FN * fn) / len(y))}


def pick_thresholds(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    grid = np.unique(np.round(np.quantile(p, np.linspace(0.02, 0.98, 97)), 6))
    f1s = [threshold_metrics(y, p, t)["f1"] for t in grid]
    costs = [threshold_metrics(y, p, t)["cost"] for t in grid]
    return {"f1_max": float(grid[int(np.argmax(f1s))]), "cost_min": float(grid[int(np.argmin(costs))])}


def _fit_predict(models: dict[str, Any], Xtr, ytr, Xs: list[np.ndarray]) -> tuple[dict[str, list[np.ndarray]], dict[str, float]]:
    out: dict[str, list[np.ndarray]] = {}
    times: dict[str, float] = {}
    for name, m in models.items():
        t0 = time.time()
        m.fit(Xtr, ytr)
        times[name] = round(time.time() - t0, 2)
        out[name] = [m.predict_proba(X)[:, 1] for X in Xs]
    return out, times


def oof_predictions(make_models, Xtr: np.ndarray, ytr: np.ndarray, groups: np.ndarray | None, seed: int, k: int = 5) -> dict[str, np.ndarray]:
    """Out-of-fold probabilities of every base model on the TRAINING set (grouped folds when groups are given)."""
    oof = {n: np.zeros(len(ytr)) for n in make_models(seed)}
    splitter = GroupKFold(n_splits=k) if groups is not None else StratifiedKFold(n_splits=k, shuffle=True, random_state=seed)
    for tr, te in (splitter.split(Xtr, ytr, groups) if groups is not None else splitter.split(Xtr, ytr)):
        ms = make_models(seed)
        for n, m in ms.items():
            m.fit(Xtr[tr], ytr[tr])
            oof[n][te] = m.predict_proba(Xtr[te])[:, 1]
    return oof


def evaluate_classifiers(Xtr, ytr, Xva, yva, Xte, yte, *, groups_train=None, seed: int = 42, bootstrap: int = 1000) -> dict[str, Any]:
    for nm, yy in (("train", ytr), ("validation", yva), ("test", yte)):
        if len(np.unique(yy)) < 2:
            raise ValueError(f"unsupported target: the {nm} split has a single class, so no classifier can be evaluated")
    t0 = time.time()
    make = lambda s: base_models(s)  # noqa: E731
    probs, fit_times = _fit_predict(make(seed), Xtr, ytr, [Xva, Xte])
    names = list(probs)
    # soft voting (equal-weight mean of the four base probabilities)
    probs["soft_voting"] = [np.mean([probs[n][i] for n in names], axis=0) for i in range(2)]
    # stacking: out-of-fold base predictions on train -> logistic meta-model on logits; base models refit on all train (above)
    oof = oof_predictions(make, Xtr, ytr, groups_train, seed)
    Z_tr = np.column_stack([logit(np.clip(oof[n], 1e-6, 1 - 1e-6)) for n in names])
    meta = LogisticRegression(C=1.0, max_iter=1000).fit(Z_tr, ytr)
    Z = [np.column_stack([logit(np.clip(probs[n][i], 1e-6, 1 - 1e-6)) for n in names]) for i in range(2)]
    probs["stacking_logistic_meta"] = [meta.predict_proba(z)[:, 1] for z in Z]

    results: dict[str, Any] = {}
    cal: dict[str, dict[str, list[np.ndarray]]] = {}
    for name, (pva, pte) in probs.items():
        sig = LogisticRegression(C=1e6, max_iter=1000).fit(logit(np.clip(pva, 1e-6, 1 - 1e-6)).reshape(-1, 1), yva)  # Platt on validation
        iso = IsotonicRegression(out_of_bounds="clip", y_min=1e-6, y_max=1 - 1e-6).fit(pva, yva)
        variants = {"uncalibrated": (pva, pte),
                    "sigmoid": (sig.predict_proba(logit(np.clip(pva, 1e-6, 1 - 1e-6)).reshape(-1, 1))[:, 1],
                                sig.predict_proba(logit(np.clip(pte, 1e-6, 1 - 1e-6)).reshape(-1, 1))[:, 1]),
                    "isotonic": (iso.predict(pva), iso.predict(pte))}
        cal[name] = {k: [v[0], v[1]] for k, v in variants.items()}
        results[name] = {"fit_seconds": fit_times.get(name)}
        for cname, (cva, cte) in variants.items():
            thr = pick_thresholds(yva, cva)
            results[name][cname] = {
                "validation": prob_metrics(yva, cva), "test": prob_metrics(yte, cte),
                "thresholds_chosen_on_validation": thr,
                "test_at_f1_threshold": threshold_metrics(yte, cte, thr["f1_max"]),
                "test_at_cost_threshold": threshold_metrics(yte, cte, thr["cost_min"]),
            }
    # paired AUC differences on identical test customers (customer bootstrap)
    best_single = max(names, key=lambda n: results[n]["uncalibrated"]["validation"]["roc_auc"])
    rng = np.random.default_rng(seed)
    idx = [rng.integers(0, len(yte), len(yte)) for _ in range(bootstrap)]
    paired = {}
    for other in [n for n in probs if n != best_single]:
        a, b = probs[other][1], probs[best_single][1]
        diffs = []
        for ii in idx:
            if len(np.unique(yte[ii])) < 2:
                continue
            diffs.append(roc_auc_score(yte[ii], a[ii]) - roc_auc_score(yte[ii], b[ii]))
        paired[f"{other} minus {best_single}"] = {"delta_auc": float(roc_auc_score(yte, a) - roc_auc_score(yte, b)),
                                                   "ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
                                                   "method": "bootstrap over test customers on identical rows"}
    return {"models": results, "paired_vs_best_single_by_validation_auc": paired, "best_single_by_validation_auc": best_single,
            "base_models": names, "elapsed_s": round(time.time() - t0, 1)}
