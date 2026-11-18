"""Per-business demand forecast: simple methods fitted ONLY on the requesting business's own history.

Why: the registered forecasters were trained on synthetic per-series data (mean 128 units per series-day) and are not applicable to a
business's total daily units (see ``model_applicability_service``). This module produces the product forecast without them.

Target: units sold per calendar day, summed over all products of the business. Missing calendar days between the first and last sale are
zero-sale days (the sales table stores sales only; long runs of zeros are reported as a possible upload gap).

Method (every step uses only data before the forecast origin):
* Candidates, simplest first: ``trailing_mean_28`` (the baseline), ``trailing_median_28``, ``weekday_mean_4w`` (mean of the same weekday
  over the last 4 weeks), ``seasonal_naive_7`` (last week's value for the same weekday). Weekday-aware candidates need >= 8 weeks of
  history and are only chosen when they beat the baseline by >= 5% on the selection origins.
* Rolling-origin backtest, one origin every 7 days, horizon = the requested horizon. The most recent origins are a holdout that is never
  used for selection; earlier ones select the method. Fewer than 5 origins -> no selection (limited estimate).
* Interval: 80% quantile of the selected method's absolute errors per horizon step, from the business's own backtest. Coverage is
  checked on the holdout origins using only the selection origins' errors; the band is labelled reliable only when observed coverage
  is close to nominal on enough points. Otherwise it is labelled indicative.
* An eligible registered model (applicability recorded for this business, never a synthetic-trained one) may enter as one more
  candidate and must beat the baseline on the same origins; none is eligible today.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable

import numpy as np
import pandas as pd

MIN_DAYS_ANY = 14            # below this (or fewer than MIN_SALE_DAYS_ANY days with sales) no forecast is produced
MIN_SALE_DAYS_ANY = 7
MIN_DAYS_SEASONAL = 56       # 8 weeks: weekday-aware candidates are not considered below this
MIN_TRAIN_DAYS = 28          # history before the earliest backtest origin
ORIGIN_STEP_DAYS = 7
MAX_ORIGINS = 12
MIN_ORIGINS_FOR_SELECTION = 5  # >= 3 selection + >= 2 holdout
MIN_IMPROVEMENT = 0.05       # a more complex candidate must beat the baseline's selection WAPE by this relative margin
INTERVAL_COVERAGE = 0.8
COVERAGE_TOLERANCE = 0.15    # observed holdout coverage must be within +-0.15 of nominal ...
MIN_COVERAGE_POINTS = 20    # ... on at least this many holdout points (origins x horizon steps; they are dependent, so this is a floor, not a sample size)
LONG_ZERO_RUN_DAYS = 14
STALE_AFTER_DAYS = 7  # a forecast that starts more than a week before today is flagged: its first days may already have passed

BASELINE = "trailing_mean_28"
ORDER = ["trailing_mean_28", "trailing_median_28", "weekday_mean_4w", "seasonal_naive_7"]
WEEKDAY_AWARE = {"weekday_mean_4w", "seasonal_naive_7"}
DESCRIPTION = {
    "trailing_mean_28": "mean of the last 28 days, held flat",
    "trailing_median_28": "median of the last 28 days, held flat",
    "weekday_mean_4w": "mean of the same weekday over the last 4 weeks",
    "seasonal_naive_7": "the value of the same weekday last week",
}


@dataclass
class BusinessForecast:
    points: list[dict[str, Any]]
    method: str
    basis: str                       # business_specific_validated | business_specific_baseline | limited_estimate
    interval_method: str
    interval_reliable: bool
    warnings: list[str]
    profile: dict[str, Any]
    validation: dict[str, Any]
    data_as_of: date
    registered_model_note: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------------------------------------ data profile
def profile_series(daily: pd.DataFrame) -> dict[str, Any]:
    """Completeness facts about the business's own daily series (target: units sold per calendar day)."""
    units = daily["units_sold"].astype(float).to_numpy()
    dates = pd.to_datetime(daily["date"])
    zero = units == 0
    longest = run = 0
    for z in zero:
        run = run + 1 if z else 0
        longest = max(longest, run)
    return {
        "target": "units_sold", "target_unit": "units per calendar day (all products)", "aggregation": "business_daily_total",
        "first_date": dates.iloc[0].date().isoformat(), "last_date": dates.iloc[-1].date().isoformat(), "days": int(len(units)),
        "sale_days": int((~zero).sum()), "zero_days": int(zero.sum()), "zero_share": float(zero.mean()) if len(units) else 0.0,
        "longest_zero_run_days": int(longest), "units_total": float(units.sum()), "units_mean_per_day": float(units.mean()) if len(units) else 0.0,
        "zero_days_are": "calendar days with no recorded sales (treated as true zeros; the sales table cannot distinguish a gap in the upload)",
    }


# ------------------------------------------------------------------------------------------------ candidate methods
def _predict(method: str, y: np.ndarray, dates: pd.DatetimeIndex, t0: int, h: int) -> np.ndarray:
    hist = y[max(0, t0 - 28): t0]
    if method == "trailing_mean_28":
        return np.full(h, float(hist.mean()))
    if method == "trailing_median_28":
        return np.full(h, float(np.median(hist)))
    wd0 = dates[t0].weekday() if t0 < len(dates) else (dates[-1] + timedelta(days=t0 - len(dates) + 1)).weekday()
    steps = np.arange(h)
    if method == "seasonal_naive_7":
        last_week = y[t0 - 7: t0]
        return np.asarray([last_week[s % 7] for s in steps], dtype=float)
    if method == "weekday_mean_4w":
        window = y[max(0, t0 - 28): t0]
        wdays = np.asarray([(wd0 - (len(window) - i)) % 7 for i in range(len(window))])
        fallback = float(window.mean())
        out = []
        for s in steps:
            w = (wd0 + s) % 7
            vals = window[wdays == w]
            out.append(float(vals.mean()) if len(vals) else fallback)
        return np.asarray(out)
    raise ValueError(f"unknown method {method}")


def wape(actual: np.ndarray, pred: np.ndarray) -> float | None:
    d = float(np.abs(actual).sum())
    return float(np.abs(pred - actual).sum() / d) if d > 0 else None


def origins_for(n: int, h: int) -> list[int]:
    """Backtest origins (index of the first forecast day), oldest first. Each has >= MIN_TRAIN_DAYS of history and h realised days."""
    out = []
    t0 = n - h
    while t0 >= MIN_TRAIN_DAYS and len(out) < MAX_ORIGINS:
        out.append(t0)
        t0 -= ORIGIN_STEP_DAYS
    return sorted(out)


def _backtest(methods: dict[str, Callable[[int, int], np.ndarray]], y: np.ndarray, origins: list[int], h: int):
    preds = {m: np.vstack([fn(t0, h) for t0 in origins]) for m, fn in methods.items()}
    actual = np.vstack([y[t0: t0 + h] for t0 in origins])
    return preds, actual


def _split(origins: list[int]) -> tuple[list[int], list[int]]:
    n_hold = max(2, len(origins) // 3)
    return origins[:-n_hold], origins[-n_hold:]


# ------------------------------------------------------------------------------------------------ main entry
def forecast(daily: pd.DataFrame, horizon: int, today: date, registered_model_note: str | None = None,
             model_candidate: Callable[[int, int], np.ndarray] | None = None) -> BusinessForecast:
    """``daily``: the business's calendar-complete daily series with columns ``date`` and ``units_sold``. Raises ``ValueError`` when no
    forecast can be produced (the caller turns that into an InsufficientDataError with the same message)."""
    profile = profile_series(daily)
    y = daily["units_sold"].astype(float).to_numpy()
    dates = pd.DatetimeIndex(pd.to_datetime(daily["date"]))
    n = len(y)
    if n < MIN_DAYS_ANY or profile["sale_days"] < MIN_SALE_DAYS_ANY:
        raise ValueError(
            f"A forecast needs at least {MIN_DAYS_ANY} days of history with sales on at least {MIN_SALE_DAYS_ANY} of them; "
            f"this business has {n} days of history and {profile['sale_days']} days with sales."
        )
    last_date = dates[-1].date()
    warnings: list[str] = []
    age = (today - last_date).days
    if age > STALE_AFTER_DAYS:
        warnings.append(f"Your latest recorded sales are from {last_date.isoformat()} ({age} days ago). The forecast continues from that "
                        "point, not from today; upload recent sales for a current forecast.")
    if profile["longest_zero_run_days"] >= LONG_ZERO_RUN_DAYS:
        warnings.append(f"There is a run of {profile['longest_zero_run_days']} consecutive days with no recorded sales. They are treated as "
                        "real zero-sale days; if they are a gap in the upload the forecast will be too low.")
    elif profile["zero_share"] > 0.3:
        warnings.append(f"{profile['zero_share'] * 100:.0f}% of days have no recorded sales and are treated as zero-sale days.")

    allowed = [m for m in ORDER if m not in WEEKDAY_AWARE or n >= MIN_DAYS_SEASONAL]
    fns: dict[str, Callable[[int, int], np.ndarray]] = {m: (lambda t0, h, m=m: _predict(m, y, dates, t0, h)) for m in allowed}
    if model_candidate is not None:
        fns["registered_model"] = model_candidate
    origins = origins_for(n, horizon)
    fit_t0 = n  # forecast origin: the day after the last observation

    def build(method: str, basis: str, half: np.ndarray | None, interval_method: str, reliable: bool, validation: dict) -> BusinessForecast:
        base = fns[method](fit_t0, horizon) if method in fns else _predict(method, y, dates, fit_t0, horizon)
        if half is None:  # heuristic band: +-1.28 x the sample std of daily units (assumes roughly normal, independent days)
            half = np.full(horizon, 1.28 * float(np.std(y[-56:], ddof=1)) if n > 2 else 0.0)
        pts = []
        for i in range(horizon):
            v = max(0.0, float(base[i]))
            pts.append({"forecast_date": last_date + timedelta(days=i + 1), "predicted_value": round(v, 2),
                        "lower_bound": round(max(0.0, v - float(half[i])), 2), "upper_bound": round(v + float(half[i]), 2)})
        return BusinessForecast(points=pts, method=method, basis=basis, interval_method=interval_method, interval_reliable=reliable,
                                warnings=warnings, profile=profile, validation=validation, data_as_of=last_date,
                                registered_model_note=registered_model_note)

    # ---- too little history to validate anything: the simplest defensible estimate, labelled as such
    if n < MIN_DAYS_SEASONAL or len(origins) < MIN_ORIGINS_FOR_SELECTION:
        warnings.append(
            f"Only {n} days of history: there is not enough to compare forecasting methods on your own data (at least "
            f"{MIN_TRAIN_DAYS + horizon + ORIGIN_STEP_DAYS * (MIN_ORIGINS_FOR_SELECTION - 1)} days are needed for a {horizon}-day horizon). "
            "This is a limited estimate: the average of your last 28 days, held flat."
        )
        validation = {"status": "not_validated", "reason": "insufficient history for chronological validation", "origins": len(origins),
                      "candidates_considered": [BASELINE], "method_description": DESCRIPTION[BASELINE]}
        return build(BASELINE, "limited_estimate", None, "sample_std_heuristic_not_calibrated", False, validation)

    sel_o, hold_o = _split(origins)
    preds, actual = _backtest(fns, y, origins, horizon)
    idx = {t0: i for i, t0 in enumerate(origins)}
    si, hi = [idx[o] for o in sel_o], [idx[o] for o in hold_o]
    sel_w = {m: wape(actual[si], preds[m][si]) for m in fns}
    hold_w = {m: wape(actual[hi], preds[m][hi]) for m in fns}
    base_sel = sel_w[BASELINE]
    chosen = BASELINE
    if base_sel is not None:
        best, best_w = BASELINE, base_sel
        for m in [*ORDER, "registered_model"]:
            if m not in fns or m == BASELINE or sel_w.get(m) is None:
                continue
            if sel_w[m] < best_w and sel_w[m] <= base_sel * (1 - MIN_IMPROVEMENT):
                best, best_w = m, sel_w[m]
        chosen = best
    # ---- interval from the business's own errors; coverage verified on the holdout using only the selection errors
    err = np.abs(preds[chosen] - actual)
    q_sel = np.maximum.accumulate(np.quantile(err[si], INTERVAL_COVERAGE, axis=0))
    inside = err[hi] <= q_sel[None, :]
    coverage = float(inside.mean())
    n_hold_points = int(inside.size)
    reliable = n_hold_points >= MIN_COVERAGE_POINTS and abs(coverage - INTERVAL_COVERAGE) <= COVERAGE_TOLERANCE
    q_all = np.maximum.accumulate(np.quantile(err, INTERVAL_COVERAGE, axis=0))
    h_chosen, h_base = hold_w.get(chosen), hold_w.get(BASELINE)
    beats = (h_chosen is not None and h_base is not None and h_chosen < h_base)
    validation = {
        "status": "validated_on_holdout", "origins": len(origins), "selection_origins": len(sel_o), "holdout_origins": len(hold_o),
        "horizon_days": horizon, "origin_step_days": ORIGIN_STEP_DAYS,
        "candidates_considered": list(fns), "selected": chosen, "method_description": DESCRIPTION.get(chosen, chosen),
        "selection_wape": {m: v for m, v in sel_w.items()}, "holdout_wape": {m: v for m, v in hold_w.items()},
        "selected_beats_baseline_on_holdout": bool(beats) if chosen != BASELINE else None,
        "holdout_relative_improvement_vs_baseline": (float(1 - h_chosen / h_base) if beats and h_base else None),
        "interval": {"nominal_coverage": INTERVAL_COVERAGE, "observed_holdout_coverage": coverage, "holdout_points": n_hold_points,
                     "reliable": bool(reliable)},
        "note": "origins overlap when the horizon exceeds 7 days, so the backtest errors are dependent; treat the intervals as approximate",
    }
    if chosen != BASELINE and not beats:
        # chosen on selection origins but not confirmed on the untouched holdout: fall back to the baseline
        chosen = BASELINE
        err = np.abs(preds[chosen] - actual)
        q_sel = np.maximum.accumulate(np.quantile(err[si], INTERVAL_COVERAGE, axis=0))
        inside = err[hi] <= q_sel[None, :]
        coverage, n_hold_points = float(inside.mean()), int(inside.size)
        reliable = n_hold_points >= MIN_COVERAGE_POINTS and abs(coverage - INTERVAL_COVERAGE) <= COVERAGE_TOLERANCE
        q_all = np.maximum.accumulate(np.quantile(err, INTERVAL_COVERAGE, axis=0))
        validation.update(selected=BASELINE, method_description=DESCRIPTION[BASELINE],
                          note="a candidate won on the selection origins but did not beat the baseline on the untouched holdout, so the baseline is used",
                          selected_beats_baseline_on_holdout=None,
                          interval={"nominal_coverage": INTERVAL_COVERAGE, "observed_holdout_coverage": coverage, "holdout_points": n_hold_points,
                                    "reliable": bool(reliable)})
    basis = "business_specific_validated" if chosen != BASELINE else "business_specific_baseline"
    if not reliable:
        warnings.append(
            f"The uncertainty band could not be confirmed on your own history: it covered {coverage * 100:.0f}% of held-out days against "
            f"a target of {INTERVAL_COVERAGE * 100:.0f}% ({n_hold_points} held-out points). Treat it as indicative."
        )
    res = build(chosen, basis, q_all, f"empirical_backtest_{len(origins)}_origins_{int(INTERVAL_COVERAGE * 100)}pct" if reliable
                else f"empirical_backtest_{len(origins)}_origins_indicative", bool(reliable), validation)
    res.metrics = {"wape_holdout": validation["holdout_wape"].get(chosen), "wape_holdout_baseline": h_base, "backtest_origins": len(origins),
                   "scope": "this business's own chronological backtest"}
    return res
