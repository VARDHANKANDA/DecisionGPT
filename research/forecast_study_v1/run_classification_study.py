"""S2 — customer-inactivity scoring on Online Retail II (PROXY label: no invoice in the 90 days after the cutoff; not observed churn).

    python -m research.forecast_study_v1.run_classification_study [--quick]

Design is fixed in EXPERIMENT_PLAN.md section 10.1. Two rolling origins; models fitted on training snapshots only; the calibrators and the single decision threshold are fitted on the
validation snapshot only; the test snapshot is scored once. Writes ``results/s2_online_retail_inactivity/`` (config, results, predictions.npz, metadata). Nothing under ``experiments/`` is touched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

from ml.benchmark import churn as ch
from ml.benchmark import datasets as ds
from research.forecast_study_v1 import inference as inf
from research.forecast_study_v1.run_forecast_study import code_fingerprint, git, versions

RESULTS = Path(__file__).resolve().parent / "results"
SEED = 42
B_MAIN, B_SENS = 2000, 1000
ORIGINS = {
    "A": {"train": ["2010-06-01", "2010-09-01", "2010-12-01"], "validation": "2011-03-14", "test": "2011-06-12"},
    "B": {"train": ["2010-06-01", "2010-09-01", "2010-12-01", "2011-03-14"], "validation": "2011-06-12", "test": "2011-09-10"},
}
BASELINE_COLS = {"recency_rank": "recency_days", "recency_ratio_rank": "recency_ratio"}
CLIP = 1e-6


def check_origin(spec: dict, last_day: pd.Timestamp) -> dict:
    w = pd.Timedelta(days=ch.WINDOW_DAYS)
    tr = sorted(pd.Timestamp(c) for c in spec["train"])
    ok = (all(tr[i] + w <= tr[i + 1] for i in range(len(tr) - 1)) and tr[-1] + w <= pd.Timestamp(spec["validation"])
          and pd.Timestamp(spec["validation"]) + w <= pd.Timestamp(spec["test"]) and pd.Timestamp(spec["test"]) + w <= last_day + pd.Timedelta(days=1))
    if not ok:
        raise AssertionError(f"label windows overlap the next stage: {spec}")
    return {"train_label_windows_end_before_validation_cutoff": True, "validation_label_window_ends_before_test_cutoff": True, "test_label_window_inside_data": True}


def top_decile_lift(y, s):
    k = max(1, int(np.ceil(0.1 * len(y))))
    order = np.argsort(-s, kind="mergesort")
    return float(y[order[:k]].mean() / y.mean()) if y.mean() > 0 else None


def ece(y, p, bins=10, equal_mass=False):
    if equal_mass:
        edges = np.quantile(p, np.linspace(0, 1, bins + 1)[1:-1])
        idx = np.digitize(p, edges)
    else:
        idx = np.clip(np.digitize(p, np.linspace(0, 1, bins + 1)[1:-1]), 0, bins - 1)
    return float(sum((idx == b).mean() * abs(y[idx == b].mean() - p[idx == b].mean()) for b in range(bins) if (idx == b).any()))


def prob_metrics(y, p):
    p = np.clip(p, CLIP, 1 - CLIP)
    prev = float(y.mean())
    b = float(brier_score_loss(y, p))
    b0 = float(brier_score_loss(y, np.full_like(p, prev)))
    return {"roc_auc": float(roc_auc_score(y, p)), "pr_auc": float(average_precision_score(y, p)), "log_loss": float(log_loss(y, p)), "brier": b, "brier_prevalence": b0,
            "brier_skill_vs_prevalence": (1 - b / b0) if b0 > 0 else None, "ece_10_equal_width": ece(y, p), "ece_10_equal_mass": ece(y, p, equal_mass=True),
            "top_decile_lift": top_decile_lift(y, p), "prevalence": prev, "n": int(len(y))}


def rank_metrics(y, s):
    return {"roc_auc": float(roc_auc_score(y, s)), "pr_auc": float(average_precision_score(y, s)), "top_decile_lift": top_decile_lift(y, s), "prevalence": float(y.mean()), "n": int(len(y))}


def best_f1_threshold(y, s):
    grid = np.unique(np.round(np.quantile(s, np.linspace(0.02, 0.98, 97)), 8))
    f1 = []
    for t in grid:
        pred = s >= t
        tp, fp, fn = int((pred & (y == 1)).sum()), int((pred & (y == 0)).sum()), int((~pred & (y == 1)).sum())
        f1.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0)
    return float(grid[int(np.argmax(f1))])


def at_threshold(y, s, t):
    pred = s >= t
    tp, fp, fn, tn = int((pred & (y == 1)).sum()), int((pred & (y == 0)).sum()), int((~pred & (y == 1)).sum()), int((~pred & (y == 0)).sum())
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else None
    return {"threshold": t, "precision": prec, "recall": rec, "f1": f1, "accuracy": (tp + tn) / len(y), "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn}}


def paired_bootstrap(y, a, b, B, seed):
    """Customer bootstrap (one snapshot row per customer) of metric(a) - metric(b) on identical rows; a = model, b = baseline."""
    rng = np.random.default_rng(seed)
    n = len(y)
    d_auc, d_pr = [], []
    for _ in range(B):
        i = rng.integers(0, n, n)
        if y[i].min() == y[i].max():
            continue
        d_auc.append(roc_auc_score(y[i], a[i]) - roc_auc_score(y[i], b[i]))
        d_pr.append(average_precision_score(y[i], a[i]) - average_precision_score(y[i], b[i]))
    out = {}
    for name, arr, pt in (("roc_auc", d_auc, roc_auc_score(y, a) - roc_auc_score(y, b)), ("pr_auc", d_pr, average_precision_score(y, a) - average_precision_score(y, b))):
        arr = np.asarray(arr)
        out[name] = {"difference": float(pt), "ci95": [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))],
                     "p_two_sided": float(min(1.0, 2 * min(np.mean(arr <= 0), np.mean(arr >= 0)))), "B": int(len(arr))}
    return out


def metric_cis(y, p, B, seed):
    rng = np.random.default_rng(seed)
    n = len(y)
    keys = ("roc_auc", "pr_auc", "log_loss", "brier", "brier_skill_vs_prevalence", "ece_10_equal_width", "top_decile_lift")
    draws = {k: [] for k in keys}
    for _ in range(B):
        i = rng.integers(0, n, n)
        if y[i].min() == y[i].max():
            continue
        m = prob_metrics(y[i], p[i])
        for k in keys:
            draws[k].append(m[k])
    return {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in draws.items()}


def fit_score(tr, va, te, feats, seed):
    """Fit every base model on the training snapshots; return validation/test probabilities."""
    Xtr, ytr = tr[feats].to_numpy(float), tr["inactive_90d"].to_numpy()
    out = {}
    for name, m in ch.base_models(seed).items():
        m.fit(Xtr, ytr)
        out[name] = (m.predict_proba(va[feats].to_numpy(float))[:, 1], m.predict_proba(te[feats].to_numpy(float))[:, 1])
    return out


def calibrate(pva, pte, yva):
    z = lambda p: logit(np.clip(p, CLIP, 1 - CLIP)).reshape(-1, 1)  # noqa: E731
    sig = LogisticRegression(C=1e6, max_iter=1000).fit(z(pva), yva)
    iso = IsotonicRegression(out_of_bounds="clip", y_min=CLIP, y_max=1 - CLIP).fit(pva, yva)
    return {"raw": (pva, pte), "platt": (sig.predict_proba(z(pva))[:, 1], sig.predict_proba(z(pte))[:, 1]), "isotonic": (iso.predict(pva), iso.predict(pte))}


def run_origin(name, spec, d, feats, quick, log):
    last = d["day"].max()
    integ = check_origin(spec, last)
    tr = pd.concat([ch.snapshot(d, c) for c in spec["train"]], ignore_index=True)
    va, te = ch.snapshot(d, spec["validation"]), ch.snapshot(d, spec["test"])
    for nm, f in (("train", tr), ("validation", va), ("test", te)):
        if f["inactive_90d"].nunique() < 2:
            raise ValueError(f"unsupported target: {nm} snapshot has a single class")
    yva, yte = va["inactive_90d"].to_numpy(), te["inactive_90d"].to_numpy()
    log(f"[S2/{name}] rows train={len(tr)} val={len(va)} test={len(te)}; prevalence train={tr['inactive_90d'].mean():.3f} val={yva.mean():.3f} test={yte.mean():.3f}")
    probs = fit_score(tr, va, te, feats, SEED)
    res: dict = {"temporal_integrity": integ, "rows": {"train": len(tr), "validation": len(va), "test": len(te)},
                 "prevalence": {"train": float(tr["inactive_90d"].mean()), "validation": float(yva.mean()), "test": float(yte.mean())},
                 "unique_customers_test": int(te["customer_id"].nunique()), "models": {}, "baselines": {}}
    # selection on validation only
    val_pr = {m: float(average_precision_score(yva, probs[m][0])) for m in probs}
    primary = max(val_pr, key=val_pr.get)
    base_val = {b: float(average_precision_score(yva, va[c].to_numpy(float))) for b, c in BASELINE_COLS.items()}
    best_base = max(base_val, key=base_val.get)
    res["selection"] = {"rule": "highest validation PR-AUC (models and rank baselines separately)", "validation_pr_auc_models": val_pr, "validation_pr_auc_baselines": base_val, "primary_model": primary, "best_baseline": best_base}

    preds = {"test_customer_id": te["customer_id"].to_numpy(), "y_test": yte, "val_customer_id": va["customer_id"].to_numpy(), "y_val": yva}
    maj_acc = float(max(yte.mean(), 1 - yte.mean()))
    res["majority_class_baseline"] = {"predicts": int(round(float(tr["inactive_90d"].mean()))), "test_accuracy": float(yte.mean() if tr["inactive_90d"].mean() >= 0.5 else 1 - yte.mean()), "test_accuracy_if_best_constant": maj_acc,
                                      "pr_auc_constant_score": float(yte.mean()), "roc_auc_constant_score": 0.5}
    for m, (pva, pte) in probs.items():
        variants = calibrate(pva, pte, yva)
        res["models"][m] = {}
        for v, (cva, cte) in variants.items():
            preds[f"test__{m}__{v}"], preds[f"val__{m}__{v}"] = cte, cva
            thr = best_f1_threshold(yva, cva)
            res["models"][m][v] = {"validation": prob_metrics(yva, cva), "test": prob_metrics(yte, cte), "threshold_from_validation_max_f1": thr, "test_at_threshold": at_threshold(yte, cte, thr)}
    for b, c in BASELINE_COLS.items():
        sva, ste = va[c].to_numpy(float), te[c].to_numpy(float)
        preds[f"test__{b}"], preds[f"val__{b}"] = ste, sva
        thr = best_f1_threshold(yva, sva)
        res["baselines"][b] = {"validation": rank_metrics(yva, sva), "test": rank_metrics(yte, ste), "threshold_from_validation_max_f1": thr, "test_at_threshold": at_threshold(yte, ste, thr), "note": "rank score, not a probability: no calibration metrics"}
    B = 100 if quick else B_MAIN
    pri_raw = preds[f"test__{primary}__raw"]
    res["paired_primary_minus_best_baseline"] = paired_bootstrap(yte, pri_raw, preds[f"test__{best_base}"], B, SEED) | {"primary": primary, "baseline": best_base}
    res["primary_test_ci95"] = {"raw": metric_cis(yte, pri_raw, B, SEED + 1), "platt": metric_cis(yte, preds[f"test__{primary}__platt"], B, SEED + 2)}
    return res, preds, (tr, va, te)


def disjoint_sensitivity(name, spec, d, feats, primary, best_base, te_ids, quick, log):
    """Remove every customer present in the test snapshot from the training and validation snapshots, refit, score the test snapshot once."""
    tr = pd.concat([ch.snapshot(d, c) for c in spec["train"]], ignore_index=True)
    va, te = ch.snapshot(d, spec["validation"]), ch.snapshot(d, spec["test"])
    tr, va = tr[~tr["customer_id"].isin(te_ids)], va[~va["customer_id"].isin(te_ids)]
    if tr["inactive_90d"].nunique() < 2 or va["inactive_90d"].nunique() < 2:
        return {"note": "unsupported: a split has one class after removing test customers"}
    probs = fit_score(tr, va, te, feats, SEED)
    yte = te["inactive_90d"].to_numpy()
    paired = paired_bootstrap(yte, probs[primary][1], te[BASELINE_COLS[best_base]].to_numpy(float), 100 if quick else B_SENS, SEED + 3)
    log(f"[S2/{name}] customer-disjoint: train rows {len(tr)}, validation rows {len(va)}")
    return {"rows": {"train": len(tr), "validation": len(va), "test": len(te)}, "primary_model_fixed_from_main_run": primary, "test_metrics": prob_metrics(yte, probs[primary][1]), "paired_vs_best_baseline": paired}


def main(quick=False, log=print) -> Path:
    t0 = time.time()
    d, info = ds.load_online_retail_ii()
    feats = ch.FEATURES
    tag = "s2_online_retail_inactivity" + ("_quick" if quick else "")
    out = RESULTS / tag
    out.mkdir(parents=True, exist_ok=True)
    config = {"study": "forecast_study_v1/S2", "origins": ORIGINS, "window_days": ch.WINDOW_DAYS, "features": feats, "seed": SEED, "baselines": BASELINE_COLS, "bootstrap_B": B_MAIN, "quick": quick,
              "label": "no purchase in the 90 days after the cutoff (PROXY for inactivity, not churn)"}
    chash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:12]
    (out / "config.json").write_text(json.dumps({**config, "config_hash": chash}, indent=2), encoding="utf-8")
    results = {"tag": tag, "origins": {}}
    arrays = {}
    for name, spec in ORIGINS.items():
        r, preds, (tr, va, te) = run_origin(name, spec, d, feats, quick, log)
        r["customer_disjoint_sensitivity"] = disjoint_sensitivity(name, spec, d, feats, r["selection"]["primary_model"], r["selection"]["best_baseline"], set(te["customer_id"]), quick, log)
        results["origins"][name] = r
        arrays.update({f"{name}__{k}": v for k, v in preds.items()})
        log(f"[S2/{name}] primary={r['selection']['primary_model']} baseline={r['selection']['best_baseline']} dAUC={r['paired_primary_minus_best_baseline']['roc_auc']['difference']:.4f} dPR={r['paired_primary_minus_best_baseline']['pr_auc']['difference']:.4f}")
    # Holm over 2 origins x 2 metrics = 4 tests, with the decision rule of the plan
    raw = {f"{o}:{m}": results["origins"][o]["paired_primary_minus_best_baseline"][m]["p_two_sided"] for o in ORIGINS for m in ("roc_auc", "pr_auc")}
    adj = inf.holm(raw)
    dec = {}
    for m in ("roc_auc", "pr_auc"):
        ok = all(adj[f"{o}:{m}"] < 0.05 and results["origins"][o]["paired_primary_minus_best_baseline"][m]["ci95"][0] > 0 for o in ORIGINS)
        worse = all(results["origins"][o]["paired_primary_minus_best_baseline"][m]["ci95"][1] < 0 for o in ORIGINS)
        dec[m] = "SUPPORTED" if ok else "CONTRADICTED" if worse else "INCONCLUSIVE"
    results["confirmatory"] = {"raw_p": raw, "holm_p": adj, "decision_per_metric": dec, "rule": "SUPPORTED if Holm p < 0.05 and CI excludes 0 (above) at both origins"}
    np.savez_compressed(out / "predictions.npz", **arrays)
    (out / "results.json").write_text(json.dumps(results, indent=2, default=lambda o: float(o) if isinstance(o, np.floating) else int(o) if isinstance(o, np.integer) else str(o)), encoding="utf-8")
    meta = {"created_utc": datetime.now(timezone.utc).isoformat(), "git_revision": git("rev-parse", "--short", "HEAD"), "code_sha256": code_fingerprint(), "versions": versions(), "dataset": info, "config_hash": chash,
            "seed": SEED, "runtime_seconds": round(time.time() - t0), "quick": quick}
    (out / "metadata.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    log(f"[S2] done in {round(time.time() - t0)}s -> {out}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    main(ap.parse_args().quick, log=lambda s: print(s, flush=True))
