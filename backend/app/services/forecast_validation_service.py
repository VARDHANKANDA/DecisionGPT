"""Reproducible validation reports on ONE business's own data (evidence level L2: see docs/REAL_WORLD_VALIDATION_PLAN.md).

What this is: a read-only, tenant-scoped evaluation of (a) the business forecast and (b) the customer score, using only that business's
stored sales, with chronological origins, simple reference baselines and an explicit statement of what the result does and does not show.

What this is not: it never touches the model registry, an artifact or a lifecycle state (evaluation is separate from promotion), it does
not train anything, and a good result is not evidence of business impact or production approval.

Every report records the dataset identity (sha256 of the ordered daily series), the configuration and thresholds applied, the code
revision and a timestamp, so the same data and configuration reproduce the same numbers.
"""
from __future__ import annotations

import hashlib
import math
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.analytics import business_forecast_service as bfs
from app.analytics import forecast_service
from app.core import clock
from app.core.errors import InsufficientDataError, ValidationFailedError
from app.models.common import utcnow
from app.models.sale import Sale
from app.services import analysis_run_service as runs
from app.services import training_readiness_service

REPORT_VERSION = 1
FORECAST_KIND = "forecast_eval"
CUSTOMER_KIND = "customer_eval"

DEFAULT_HORIZONS = (7, 14, 28)
MAX_HORIZONS = 3
# Provisional engineering conventions (docs/REAL_WORLD_VALIDATION_PLAN.md section 4), echoed in every report.
ADI_CUTOFF = 1.32          # average inter-demand interval (Syntetos-Boylan convention)
CV2_CUTOFF = 0.49          # squared coefficient of variation of non-zero demand sizes (same convention)
SPARSE_ZERO_SHARE = 0.5
MIN_HOLDOUT_ORIGINS = bfs.MIN_ORIGINS_FOR_SELECTION
MIN_CUSTOMERS = 30
MIN_PER_CLASS = 5
CUSTOMER_WINDOW_DEFAULT = 60
STABILITY_AUC_GAP = 0.10   # provisional: two cutoffs whose AUC differs by more than this are called unstable

NOT_EVIDENCE_OF = [
    "business impact: no recommendation was acted on and no outcome was recorded",
    "accuracy on other businesses or on later periods whose behaviour differs (promotions, festivals, price changes)",
    "production approval: promotion stays an explicit, recorded lifecycle action",
]

REFERENCE_METHODS = ["naive_last", "seasonal_naive_7", "trailing_mean_28", "trailing_median_28", "weekday_mean_4w"]


# ------------------------------------------------------------------------------------------------ series facts
def series_class(y: np.ndarray) -> dict[str, Any]:
    """Demand pattern of a daily series. ``series_class`` follows the plan: sparse (zero share >= 0.5), intermittent (ADI >= 1.32), else
    regular; ``pattern`` is the four-way smooth / erratic / intermittent / lumpy convention (a convention, not a finding)."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    nz = y[y > 0]
    zero_share = float((y == 0).mean()) if n else 0.0
    adi = float(n / len(nz)) if len(nz) else None
    cv2 = float((nz.std(ddof=0) / nz.mean()) ** 2) if len(nz) > 1 and nz.mean() > 0 else (0.0 if len(nz) else None)
    if adi is None:
        pattern = "no_demand"
    elif adi < ADI_CUTOFF:
        pattern = "smooth" if (cv2 or 0) < CV2_CUTOFF else "erratic"
    else:
        pattern = "intermittent" if (cv2 or 0) < CV2_CUTOFF else "lumpy"
    cls = "sparse" if zero_share >= SPARSE_ZERO_SHARE else ("intermittent" if adi is not None and adi >= ADI_CUTOFF else "regular")
    return {"series_class": cls, "pattern": pattern, "adi": adi, "cv2_nonzero": cv2, "zero_share": zero_share,
            "mean_units_per_day": float(y.mean()) if n else 0.0,
            "metric_guidance": ("MAE and RMSE are the primary metrics: WAPE is dominated by the few high-volume days"
                                if cls in ("sparse", "intermittent") else "WAPE and MAE are both meaningful"),
            "conventions": {"adi_cutoff": ADI_CUTOFF, "cv2_cutoff": CV2_CUTOFF, "sparse_zero_share": SPARSE_ZERO_SHARE}}


def dataset_identity(daily: pd.DataFrame) -> dict[str, Any]:
    """sha256 of the ordered (date, units) pairs: the same stored data gives the same identity; nothing tenant-readable is included."""
    h = hashlib.sha256()
    for d, u in zip(pd.to_datetime(daily["date"]).dt.strftime("%Y-%m-%d"), daily["units_sold"].astype(float)):
        h.update(f"{d}|{u:.6f}\n".encode())
    dates = pd.to_datetime(daily["date"])
    return {"sha256": h.hexdigest(), "days": int(len(daily)), "first_date": dates.iloc[0].date().isoformat(),
            "last_date": dates.iloc[-1].date().isoformat(), "series": "business daily units (all products)"}


# ------------------------------------------------------------------------------------------------ metrics
def point_metrics(actual: np.ndarray, pred: np.ndarray) -> dict[str, Any]:
    """MAE, RMSE, WAPE, signed bias on origins x horizon-steps arrays. WAPE and relative bias are None (never 0) when the actual total is 0."""
    a, p = np.asarray(actual, dtype=float), np.asarray(pred, dtype=float)
    e = p - a
    total = float(np.abs(a).sum())
    return {
        "mae": float(np.abs(e).mean()), "rmse": float(np.sqrt((e ** 2).mean())),
        "wape": float(np.abs(e).sum() / total) if total > 0 else None,
        "bias_units_per_day": float(e.mean()),                                  # > 0 over-forecasts, < 0 under-forecasts
        "relative_bias": float(e.sum() / total) if total > 0 else None,
        "wape_note": None if total > 0 else "undefined: the actual units in the evaluation windows sum to 0",
        "n_origins": int(a.shape[0]), "n_points": int(a.size),
    }


def _predictors(y: np.ndarray, dates: pd.DatetimeIndex) -> dict[str, Any]:
    def naive_last(t0: int, h: int) -> np.ndarray:
        return np.full(h, float(y[t0 - 1]))

    fns: dict[str, Any] = {"naive_last": naive_last}
    for m in ("seasonal_naive_7", "trailing_mean_28", "trailing_median_28", "weekday_mean_4w"):
        fns[m] = (lambda t0, h, m=m: bfs._predict(m, y, dates, t0, h))
    return fns


def _horizon_report(y: np.ndarray, dates: pd.DatetimeIndex, daily: pd.DataFrame, h: int, today: date) -> dict[str, Any]:
    out: dict[str, Any] = {"horizon_days": h}
    origins = bfs.origins_for(len(y), h)
    out["origins"] = len(origins)
    if not origins:
        out.update(status="insufficient_history", statement=(f"No backtest is possible for a {h}-day horizon: it needs at least "
                                                          f"{bfs.MIN_TRAIN_DAYS + h} days of history (this business has {len(y)})."))
        return out
    fns = _predictors(y, dates)
    actual = np.vstack([y[t0: t0 + h] for t0 in origins])
    preds = {m: np.vstack([fn(t0, h) for t0 in origins]) for m, fn in fns.items()}
    out["all_origins"] = {m: point_metrics(actual, preds[m]) for m in fns}
    if len(origins) < MIN_HOLDOUT_ORIGINS:
        out.update(status="descriptive_only", statement=(
            f"Only {len(origins)} backtest origins exist for a {h}-day horizon (at least {MIN_HOLDOUT_ORIGINS} are needed to keep an untouched "
            "holdout). The figures describe those origins; no method was selected and no comparison is a validation."))
        return out
    sel_o, hold_o = bfs._split(origins)
    idx = {t0: i for i, t0 in enumerate(origins)}
    si, hi = [idx[o] for o in sel_o], [idx[o] for o in hold_o]
    out["selection_origins"], out["holdout_origins"] = len(si), len(hi)
    out["holdout"] = {m: point_metrics(actual[hi], preds[m][hi]) for m in fns}
    # what the product would use, and how it fares on the same untouched origins
    try:
        prod = bfs.forecast(daily, h, today)
        chosen, basis = prod.method, prod.basis
        interval_flag = prod.interval_reliable
    except ValueError as exc:
        out.update(status="refused", statement=str(exc))
        return out
    out["production"] = {"selected_method": chosen, "basis": basis, "interval_reliable_in_product": bool(interval_flag)}
    m_sel = chosen if chosen in preds else bfs.BASELINE
    err = np.abs(preds[m_sel] - actual)
    q_sel = np.maximum.accumulate(np.quantile(err[si], bfs.INTERVAL_COVERAGE, axis=0))
    inside = err[hi] <= q_sel[None, :]
    out["interval"] = {
        "method": "empirical 80% quantile of the selection origins' absolute errors per horizon step (non-decreasing in the step)",
        "nominal_coverage": bfs.INTERVAL_COVERAGE, "observed_holdout_coverage": float(inside.mean()), "holdout_points": int(inside.size),
        "mean_width_units": float(2 * q_sel.mean()), "width_note": "full width before clipping the lower bound at zero",
        "points_are_independent": False,
        "limitation": ("holdout points come from a handful of overlapping origins and are strongly dependent: the coverage figure is an "
                       "approximate check, not a statistical guarantee"),
        "reliable_by_policy": bool(inside.size >= bfs.MIN_COVERAGE_POINTS and abs(float(inside.mean()) - bfs.INTERVAL_COVERAGE) <= bfs.COVERAGE_TOLERANCE),
    }
    sel, base, naive, snaive = (out["holdout"][m_sel], out["holdout"][bfs.BASELINE], out["holdout"]["naive_last"], out["holdout"]["seasonal_naive_7"])
    out["comparison_on_holdout"] = {
        "selected_vs_naive_last_mae_ratio": (sel["mae"] / naive["mae"]) if naive["mae"] > 0 else None,
        "selected_vs_trailing_mean_mae_ratio": (sel["mae"] / base["mae"]) if base["mae"] > 0 else None,
        "selected_vs_seasonal_naive_mae_ratio": (sel["mae"] / snaive["mae"]) if snaive["mae"] > 0 else None,
        "note": "ratio < 1 means the selected method had a lower holdout MAE than that reference",
    }
    r_naive = out["comparison_on_holdout"]["selected_vs_naive_last_mae_ratio"]
    r_base = out["comparison_on_holdout"]["selected_vs_trailing_mean_mae_ratio"]
    is_baseline = m_sel == bfs.BASELINE
    if r_naive is None:
        verdict = "inconclusive"
        why = "the naive reference was exact on the holdout, so no ratio is defined"
    elif r_naive < 1 and (is_baseline or r_base is None or r_base <= 1.0):
        verdict = "beats_references"
        why = ("is the baseline and had a lower holdout MAE than the naive last-value forecast" if is_baseline else
               "had a lower holdout MAE than the naive last-value forecast and was not worse than the trailing mean")
    elif r_naive < 1:
        verdict, why = "beats_naive_only", "had a lower holdout MAE than the naive forecast but was worse than the trailing mean"
    else:
        verdict, why = "does_not_beat_naive", "did not have a lower holdout MAE than the naive last-value forecast"
    out["verdict"] = verdict
    out["status"] = "evaluated"
    bias = sel["relative_bias"]
    bias_txt = ("bias unavailable (zero actuals)" if bias is None else
                f"{'over' if bias > 0 else 'under'}-forecast by {abs(bias) * 100:.1f}% of actual units on the holdout")
    out["statement"] = (f"{h}-day horizon: '{m_sel}' ({basis.replace('_', ' ')}) {why}; holdout MAE {sel['mae']:.2f} units/day; {bias_txt}; "
                        f"80% band covered {out['interval']['observed_holdout_coverage'] * 100:.0f}% of {out['interval']['holdout_points']} "
                        f"dependent held-out points.")
    return out


def evaluate_series(daily: pd.DataFrame, horizons: tuple[int, ...] | list[int], today: date) -> dict[str, Any]:
    """Pure evaluation of a calendar-complete daily series (columns ``date``, ``units_sold``). No database, no randomness."""
    y = daily["units_sold"].astype(float).to_numpy()
    dates = pd.DatetimeIndex(pd.to_datetime(daily["date"]))
    return {
        "dataset": dataset_identity(daily),
        "series": series_class(y),
        "negative_unit_days": int((y < 0).sum()),
        "horizons": [_horizon_report(y, dates, daily, int(h), today) for h in horizons],
    }


# ------------------------------------------------------------------------------------------------ forecast validation run
def _config(horizons: list[int], today: date) -> dict[str, Any]:
    return {
        "as_of_date": today.isoformat(), "horizons": horizons, "origin_step_days": bfs.ORIGIN_STEP_DAYS, "max_origins": bfs.MAX_ORIGINS,
        "min_train_days": bfs.MIN_TRAIN_DAYS, "min_origins_for_selection": bfs.MIN_ORIGINS_FOR_SELECTION,
        "selection_margin": bfs.MIN_IMPROVEMENT, "interval_nominal_coverage": bfs.INTERVAL_COVERAGE,
        "coverage_tolerance": bfs.COVERAGE_TOLERANCE, "min_coverage_points": bfs.MIN_COVERAGE_POINTS, "reference_methods": REFERENCE_METHODS,
        "policy_status": "provisional engineering policies, not established thresholds",
    }


def _revision() -> str:
    try:
        from ml.pipeline.run_metadata import git_revision

        return str(git_revision())
    except Exception:  # noqa: BLE001 - provenance is best effort; its absence is recorded, not fatal
        return "unknown"


def _validate_horizons(horizons: list[int] | None) -> list[int]:
    hs = list(horizons) if horizons else list(DEFAULT_HORIZONS)
    if len(hs) > MAX_HORIZONS or len(set(hs)) != len(hs):
        raise ValidationFailedError(f"Choose between 1 and {MAX_HORIZONS} different horizons.")
    for h in hs:
        if not isinstance(h, int) or isinstance(h, bool) or not 1 <= h <= forecast_service.MAX_HORIZON_DAYS:
            raise ValidationFailedError(f"Each horizon must be a whole number of days between 1 and {forecast_service.MAX_HORIZON_DAYS}.")
    return sorted(hs)


def run_forecast_validation(db: Session, business_id: str, horizons: list[int] | None = None) -> dict[str, Any]:
    hs = _validate_horizons(horizons)
    today = clock.today()
    daily = forecast_service.build_daily_series(db, business_id)
    if daily.empty:
        raise InsufficientDataError("No sales history on file yet, so there is nothing to validate a forecast against.")
    readiness = training_readiness_service.readiness(db, business_id)
    sale_days = {d for (d,) in db.query(Sale.sale_date).filter(Sale.business_id == business_id).distinct().all()}
    calendar_days = (pd.to_datetime(daily["date"]).iloc[-1] - pd.to_datetime(daily["date"]).iloc[0]).days + 1
    body = evaluate_series(daily[["date", "units_sold"]], hs, today)
    refused = [r for r in body["horizons"] if r.get("status") == "refused"]
    summary = [r["statement"] for r in body["horizons"]]
    report = {
        "report_version": REPORT_VERSION, "kind": FORECAST_KIND, "generated_at": utcnow().isoformat(),
        "business_scope": "this business only", "code_revision": _revision(), "config": _config(hs, today),
        "evidence": {"level": "L2_business_own_history_backtest" if not refused else "none", "not_evidence_of": NOT_EVIDENCE_OF,
                     "separation": "this evaluation changed no model, artifact or lifecycle state"},
        "data_quality": {
            "calendar_days": int(calendar_days), "days_with_sales_rows": len(sale_days), "calendar_days_without_rows": int(calendar_days - len(sale_days)),
            "missing_day_treatment": "zero units (the sales table stores sales only, so a gap in the upload is indistinguishable from a closed day)",
            "price_gap_treatment": "forward-filled for the price feature only; never used by the forecasting methods evaluated here",
            "issues": readiness.get("issues", []), "blockers": readiness.get("blockers", []),
            "currency": "INR assumed", "timezone": "none: calendar dates", "example_data": readiness.get("example_data"),
        },
        **body, "summary": summary,
        "headline": ("Backtested on this business's own history only; " + ("; ".join(summary[:1]) if summary else "no horizon could be evaluated")),
    }
    row = runs.save(db, business_id, FORECAST_KIND, "forecast_validation", None, report["config"], report)
    return {"id": row.id, **report}


# ------------------------------------------------------------------------------------------------ customer score validation
def _customer_cutoff_report(sales: pd.DataFrame, cutoff: date, window: int, model, score_fn) -> dict[str, Any]:
    from sklearn.metrics import roc_auc_score

    end = cutoff + timedelta(days=window)
    known = sales[sales["date"] <= cutoff]
    out: dict[str, Any] = {"cutoff": cutoff.isoformat(), "label_window": [(cutoff + timedelta(days=1)).isoformat(), end.isoformat()]}
    if known.empty:
        out.update(status="insufficient_evidence", reason="no customers had purchased by this cutoff")
        return out
    g = known.groupby("customer_id").agg(first=("date", "min"), last=("date", "max"), orders=("date", "nunique"), monetary=("revenue", "sum"))
    frame = pd.DataFrame({
        "customer_id": g.index,
        "tenure_days": [max(1, (cutoff - f).days) for f in g["first"]],
        "recency_days": [max(0, (cutoff - l).days) for l in g["last"]],
        "frequency": g["orders"].astype(float).to_numpy(),
        "monetary_value": g["monetary"].astype(float).to_numpy(),
    })
    frame["avg_order_value"] = frame["monetary_value"] / frame["frequency"].clip(lower=1)
    later = set(sales[(sales["date"] > cutoff) & (sales["date"] <= end)]["customer_id"])
    label = np.array([0 if c in later else 1 for c in frame["customer_id"]])    # 1 = no purchase in the window (inactive)
    n, pos = len(frame), int(label.sum())
    out.update(customers=n, inactive=pos, prevalence=float(pos / n) if n else None)
    if n < MIN_CUSTOMERS or min(pos, n - pos) < MIN_PER_CLASS:
        out.update(status="insufficient_evidence", reason=(f"needs at least {MIN_CUSTOMERS} customers and {MIN_PER_CLASS} of each class "
                                                           f"(has {n} customers, {pos} inactive, {n - pos} active)"))
        return out
    score = score_fn(frame)
    recency = frame["recency_days"].to_numpy(dtype=float)
    k = max(1, int(math.ceil(0.1 * n)))
    top = np.argsort(-score, kind="mergesort")[:k]
    prevalence = pos / n
    out.update(status="evaluated", roc_auc=float(roc_auc_score(label, score)), roc_auc_recency_only=float(roc_auc_score(label, recency)),
               top_decile_inactive_rate=float(label[top].mean()), top_decile_lift=float(label[top].mean() / prevalence))
    out["adds_value_over_recency"] = out["roc_auc"] > out["roc_auc_recency_only"]
    return out


def run_customer_score_validation(db: Session, business_id: str, window_days: int = CUSTOMER_WINDOW_DEFAULT) -> dict[str, Any]:
    from app.analytics import churn_service
    from ml.features.churn_features import FEATURE_COLUMNS, build_churn_features
    from ml.features.contracts import CHURN_V1

    if not isinstance(window_days, int) or not 14 <= window_days <= 120:
        raise ValidationFailedError("window_days must be a whole number of days between 14 and 120.")
    rows = db.query(Sale.customer_id, Sale.sale_date, Sale.revenue).filter(Sale.business_id == business_id, Sale.customer_id.isnot(None)).all()
    if not rows:
        raise InsufficientDataError("No sales are linked to customers, so a customer score cannot be checked against what customers did.")
    sales = pd.DataFrame([{"customer_id": str(c), "date": d, "revenue": float(r)} for c, d, r in rows])
    last = sales["date"].max()
    model_row = churn_service.select_best_model(db, churn_service.CHURN_MODEL_CANDIDATES, metric="roc_auc", minimize=False,
                                                validation_metric="val_roc_auc")
    if model_row is None:
        raise InsufficientDataError("No customer scoring model is registered, so there is nothing to validate.")
    model = churn_service._load_model(model_row)

    def score_fn(frame: pd.DataFrame) -> np.ndarray:
        featured = build_churn_features(frame)
        return model.predict_proba(CHURN_V1.validate(featured[FEATURE_COLUMNS]))[:, 1]

    cutoffs = [last - timedelta(days=window_days), last - timedelta(days=2 * window_days)]
    per_cutoff = [_customer_cutoff_report(sales, c, window_days, model, score_fn) for c in cutoffs]
    ev = [c for c in per_cutoff if c.get("status") == "evaluated"]
    stable = (len(ev) == 2 and abs(ev[0]["roc_auc"] - ev[1]["roc_auc"]) <= STABILITY_AUC_GAP) if len(ev) == 2 else None
    info = churn_service.describe_scores(model_row)
    if not ev:
        headline = "There is not enough customer behaviour in this business's history to check the score against what customers did."
    else:
        e = ev[0]
        headline = (f"On this business's own customers the score ranked later inactivity with ROC-AUC {e['roc_auc']:.2f} "
                    f"(recency alone: {e['roc_auc_recency_only']:.2f}); inactivity prevalence {e['prevalence'] * 100:.0f}%. "
                    "This is a ranking check against a proxy, not a churn probability.")
    report = {
        "report_version": REPORT_VERSION, "kind": CUSTOMER_KIND, "generated_at": utcnow().isoformat(),
        "business_scope": "this business only", "code_revision": _revision(),
        "config": {"as_of_date": clock.today().isoformat(), "window_days": window_days, "cutoffs": [c.isoformat() for c in cutoffs],
                   "min_customers": MIN_CUSTOMERS, "min_per_class": MIN_PER_CLASS, "stability_auc_gap": STABILITY_AUC_GAP,
                   "policy_status": "provisional engineering policies, not established thresholds"},
        "model": {"name": model_row.model_name, "version": model_row.version, "label_provenance": info["label_provenance"],
                  "score_meaning": info["score_meaning"]},
        "target": {"kind": "proxy: inactivity", "definition": f"no purchase in the {window_days} days after the cutoff, from this business's sales",
                   "limits": "returns, seasonal buyers and customers who buy less often than the window are labelled inactive although they did not churn"},
        "features": "as of each cutoff from sales before it only (tenure, recency, order days, revenue)",
        "cutoffs": per_cutoff, "stable_across_cutoffs": stable,
        "calibration": {"evaluated": False, "reason": "the label is a proxy and the model was trained on synthetic labels: a probability scale would not be meaningful"},
        "evidence": {"level": "L2_proxy_ranking" if ev else "none", "not_evidence_of": NOT_EVIDENCE_OF + [
            "a probability that any customer will leave", "that the model was trained on observed churn"],
                     "separation": "this evaluation changed no model, artifact or lifecycle state"},
        "headline": headline,
    }
    row = runs.save(db, business_id, CUSTOMER_KIND, "customer_score_validation", None, report["config"], report)
    return {"id": row.id, **report}
