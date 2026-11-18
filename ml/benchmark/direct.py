"""Generic rolling-origin evaluation of global direct-horizon forecasters (shared by the M5 and Online Retail II tasks).

Protocol (identical for every dataset): per-family variant and ensemble method are chosen on validation windows that precede the
final window; the final window is refit-and-scored once. See docs/ML_IMPROVEMENT_PLAN.md section 3.
"""
from __future__ import annotations

import time
from typing import Any

import numpy as np

from ml.benchmark import ensembles as ens
from ml.benchmark import evaluate as ev
from ml.benchmark import features as ft
from ml.benchmark import models as zoo

PRICE_FEATURES = ("sell_price", "rel_price_91", "price_change_7", "days_since_price_change")


def rows(F: np.ndarray, valid: np.ndarray, y: np.ndarray, t_lo: int, t_hi: int):
    """Flat (X, y, series_idx, day_idx) for target days in [t_lo, t_hi] that are valid (complete features, item on sale)."""
    V = valid[:, t_lo: t_hi + 1]
    s_idx, d_off = np.nonzero(V)
    d_idx = d_off + t_lo
    return F[s_idx, d_idx], y[s_idx, d_idx].astype(np.float64), s_idx, d_idx


def run_direct(y: np.ndarray, price: np.ndarray, cal, static: dict[str, np.ndarray], *, H: int, test_lo: int, val_origins: list[int],
               train_span: int, families: dict[str, list[str]], seed: int, drop_features: tuple[str, ...] = (), min_history: int = 84,
               log=print) -> dict[str, Any]:
    """Returns ``{"results": ..., "predictions": ..., "runtimes": ...}`` (no file I/O)."""
    t_start = time.time()
    test_hi = test_lo + H - 1
    F, names = ft.build_direct_features(y, price, cal, static, H)
    valid = ft.valid_mask(y, price, H, min_history)
    if drop_features:
        keep = [i for i, n in enumerate(names) if n not in drop_features]
        F = F[:, :, keep]
        names = [names[i] for i in keep]
        valid = np.ones_like(valid, dtype=bool)
        valid[:, : H + min_history] = False  # price is not a usable availability signal when its columns are dropped
    lag_idx, sw_idx = names.index(f"lag_{H}"), names.index("same_weekday_mean4")

    val_store: dict[str, dict[int, np.ndarray]] = {}
    val_truth: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    val_scores: dict[str, dict[int, float]] = {}
    runtimes: dict[str, float] = {}
    baseline_val: dict[str, dict[int, float]] = {"seasonal_naive": {}, "same_weekday_mean4": {}}

    for o in val_origins:
        Xtr, ytr, _, _ = rows(F, valid, y, max(0, o - train_span), o - 1)
        Xva, yva, sva, _ = rows(F, valid, y, o, o + H - 1)
        val_truth[o] = (yva, sva)
        baseline_val["seasonal_naive"][o] = ev.wape(yva, np.nan_to_num(Xva[:, lag_idx]))
        baseline_val["same_weekday_mean4"][o] = ev.wape(yva, np.nan_to_num(Xva[:, sw_idx]))
        for fam, variants in families.items():
            for var in variants:
                cid = f"{fam}:{var}"
                t0 = time.time()
                pr = zoo.build(fam, var, names, seed).fit(Xtr, ytr)
                runtimes[f"{cid}@{o}"] = round(time.time() - t0, 1)
                p = pr.predict(Xva)
                val_store.setdefault(cid, {})[o] = p
                val_scores.setdefault(cid, {})[o] = ev.wape(yva, p)
        log(f"validation origin {o} done; elapsed {round(time.time() - t_start)}s")

    chosen: dict[str, str] = {}
    for fam, variants in families.items():
        best = min(variants, key=lambda v: np.mean([val_scores[f"{fam}:{v}"][o] for o in val_origins]))
        chosen[fam] = f"{fam}:{best}"
    fam_names = list(chosen)

    P_val = np.vstack([np.column_stack([val_store[chosen[f]][o] for f in fam_names]) for o in val_origins])
    Y_val = np.concatenate([val_truth[o][0] for o in val_origins])
    w_all = ens.nnls_weights(P_val, Y_val)
    rank = sorted(fam_names, key=lambda f: np.mean([val_scores[chosen[f]][o] for o in val_origins]))
    top3 = rank[:3]
    mean_val = {o: ev.wape(val_truth[o][0], ens.mean_ensemble([val_store[chosen[f]][o] for f in fam_names])) for o in val_origins}
    top3_val = {o: ev.wape(val_truth[o][0], ens.mean_ensemble([val_store[chosen[f]][o] for f in top3])) for o in val_origins}
    loo: dict[int, float] = {}
    if len(val_origins) > 1:
        for o in val_origins:
            others = [x for x in val_origins if x != o]
            Pp = np.vstack([np.column_stack([val_store[chosen[f]][x] for f in fam_names]) for x in others])
            Yp = np.concatenate([val_truth[x][0] for x in others])
            w = ens.nnls_weights(Pp, Yp)
            loo[o] = ev.wape(val_truth[o][0], np.column_stack([val_store[chosen[f]][o] for f in fam_names]) @ w)

    Xtr, ytr, _, _ = rows(F, valid, y, max(0, test_lo - train_span), test_lo - 1)
    Xte, yte, ste, dte = rows(F, valid, y, test_lo, test_hi)
    scale = ev.series_scale(y[:, :test_lo])
    test_pred: dict[str, np.ndarray] = {}
    infer_ms: dict[str, float] = {}
    for fam in fam_names:
        cid = chosen[fam]
        f, v = cid.split(":")
        t0 = time.time()
        pr = zoo.build(f, v, names, seed).fit(Xtr, ytr)
        runtimes[f"{cid}@final_fit"] = round(time.time() - t0, 1)
        t0 = time.time()
        test_pred[cid] = pr.predict(Xte)
        infer_ms[cid] = round((time.time() - t0) / max(len(Xte), 1) * 1000, 4)
    test_pred["baseline:seasonal_naive"] = np.nan_to_num(Xte[:, lag_idx])
    test_pred["baseline:same_weekday_mean4"] = np.nan_to_num(Xte[:, sw_idx])
    test_pred["ensemble:mean_all"] = ens.mean_ensemble([test_pred[chosen[f]] for f in fam_names])
    test_pred["ensemble:mean_top3"] = ens.mean_ensemble([test_pred[chosen[f]] for f in top3])
    test_pred["ensemble:nnls_weighted"] = np.column_stack([test_pred[chosen[f]] for f in fam_names]) @ w_all

    results_test: dict[str, Any] = {}
    days = np.unique(dte)
    for k, p in test_pred.items():
        m = ev.metrics(yte, p, ste, scale)
        ya = np.array([yte[dte == d].sum() for d in days])
        pa = np.array([p[dte == d].sum() for d in days])
        m["aggregate_daily_wape"] = ev.wape(ya, pa)
        m["aggregate_daily_mae"] = float(np.mean(np.abs(pa - ya)))
        m["inference_ms_per_row"] = infer_ms.get(k)
        results_test[k] = m

    singles = [chosen[f] for f in fam_names]
    best_single = min(singles, key=lambda c: np.mean([val_scores[c][o] for o in val_origins]))
    paired: dict[str, Any] = {}
    for a in ("ensemble:mean_all", "ensemble:mean_top3", "ensemble:nnls_weighted", best_single):
        for b in (("baseline:seasonal_naive",) if a == best_single else ("baseline:seasonal_naive", best_single)):
            paired[f"{a} vs {b}"] = ev.paired_cluster_bootstrap(yte, test_pred[a], test_pred[b], ste)
    for c in singles:
        if c != best_single:
            paired[f"{c} vs {best_single}"] = ev.paired_cluster_bootstrap(yte, test_pred[c], test_pred[best_single], ste)

    mean_ = lambda d: float(np.mean(list(d.values())))  # noqa: E731
    method_val = {
        f"single:{best_single}": float(np.mean([val_scores[best_single][o] for o in val_origins])),
        "ensemble:mean_all": mean_(mean_val), "ensemble:mean_top3": mean_(top3_val),
        "ensemble:nnls_weighted(LOO)": mean_(loo) if loo else None,
        "baseline:seasonal_naive": mean_(baseline_val["seasonal_naive"]),
        "baseline:same_weekday_mean4": mean_(baseline_val["same_weekday_mean4"]),
    }
    selectable = {k: v for k, v in method_val.items() if v is not None and not k.startswith("baseline")}
    selected = min(selectable, key=selectable.get)
    results = {
        "n_series": int(y.shape[0]), "n_features": len(names), "features": names, "n_test_points": int(len(yte)),
        "n_train_rows_final": int(len(ytr)), "validation_origins_index": val_origins, "test_window_index": [test_lo, test_hi],
        "chosen_variant_per_family": chosen,
        "validation": {c: {"wape_by_origin": {str(o): val_scores[c][o] for o in val_origins},
                           "mean_wape": float(np.mean([val_scores[c][o] for o in val_origins]))} for c in val_scores},
        "baseline_validation_wape": {k: {str(o): v for o, v in d.items()} for k, d in baseline_val.items()},
        "method_selection_validation_wape": method_val, "validation_selected_method": selected,
        "best_single_by_validation": best_single,
        "ensemble_weights_nnls": dict(zip(singles, [float(x) for x in w_all])),
        "test": results_test, "paired_test_comparisons": paired, "runtimes_seconds": runtimes,
        "not_run": ["learned stacking meta-model: few, overlapping validation origins are not enough independent data"],
    }
    return {"results": results, "predictions": {"y": yte, "series": ste, "day": dte, **test_pred}, "elapsed_s": round(time.time() - t_start)}
