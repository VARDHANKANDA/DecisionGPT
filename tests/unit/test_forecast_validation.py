"""Pure functions of the forecast-validation report: series class, metrics with undefined denominators, chronological evaluation,
dataset identity. No database, no registry, no provider."""
from datetime import date

import numpy as np
import pandas as pd

from app.services import forecast_validation_service as fv

TODAY = date(2026, 6, 30)


def frame(values, end=TODAY):
    n = len(values)
    return pd.DataFrame({"date": pd.date_range(end=pd.Timestamp(end), periods=n, freq="D"), "units_sold": np.asarray(values, dtype=float)})


def weekly(n, base=40.0, amp=25.0, noise=2.0, seed=0):
    rng = np.random.default_rng(seed)
    pattern = np.array([0, 0, 0, 0, 0.5, 1.0, 1.0]) * amp
    d = pd.date_range(end=pd.Timestamp(TODAY), periods=n, freq="D")
    return np.maximum(0, base + pattern[d.weekday] + rng.normal(0, noise, n))


def test_series_class_separates_regular_intermittent_and_sparse():
    assert fv.series_class(weekly(120))["series_class"] == "regular"
    rng = np.random.default_rng(1)
    inter = np.where(rng.random(200) < 0.35, rng.integers(1, 6, 200), 0)            # ~35% of days have demand
    c = fv.series_class(inter)
    assert c["series_class"] in ("intermittent", "sparse") and c["adi"] >= fv.ADI_CUTOFF and "MAE and RMSE are the primary metrics" in c["metric_guidance"]
    sparse = np.zeros(100)
    sparse[::10] = 4
    assert fv.series_class(sparse)["series_class"] == "sparse"
    assert fv.series_class(np.zeros(30))["pattern"] == "no_demand"


def test_metrics_never_report_a_perfect_wape_for_zero_actuals_and_keep_the_bias_sign():
    a, p = np.zeros((3, 4)), np.full((3, 4), 2.0)
    m = fv.point_metrics(a, p)
    assert m["wape"] is None and m["relative_bias"] is None and "undefined" in m["wape_note"]
    assert m["mae"] == 2.0 and m["bias_units_per_day"] == 2.0           # over-forecast
    m2 = fv.point_metrics(np.full((2, 3), 10.0), np.full((2, 3), 7.0))
    assert m2["bias_units_per_day"] == -3.0 and abs(m2["relative_bias"] + 0.3) < 1e-9 and abs(m2["wape"] - 0.3) < 1e-9


def test_dataset_identity_is_reproducible_and_changes_with_the_data():
    a, b = frame(weekly(90)), frame(weekly(90))
    assert fv.dataset_identity(a)["sha256"] == fv.dataset_identity(b)["sha256"]
    c = frame(weekly(90, seed=1))
    assert fv.dataset_identity(c)["sha256"] != fv.dataset_identity(a)["sha256"]
    assert fv.dataset_identity(a)["days"] == 90


def test_horizons_are_evaluated_separately_and_weekly_pattern_beats_the_naive_reference():
    rep = fv.evaluate_series(frame(weekly(220, amp=40, noise=1.5)), [7, 14], TODAY)
    assert [h["horizon_days"] for h in rep["horizons"]] == [7, 14]
    h7 = rep["horizons"][0]
    assert h7["status"] == "evaluated" and h7["holdout_origins"] >= 2 and h7["selection_origins"] >= 3
    assert set(h7["holdout"]) >= {"naive_last", "seasonal_naive_7", "trailing_mean_28", "weekday_mean_4w"}
    assert h7["verdict"] == "beats_references" and h7["comparison_on_holdout"]["selected_vs_naive_last_mae_ratio"] < 1
    iv = h7["interval"]
    assert iv["points_are_independent"] is False and "not a statistical guarantee" in iv["limitation"] and iv["mean_width_units"] > 0
    assert 0.0 <= iv["observed_holdout_coverage"] <= 1.0


def test_a_flat_noisy_series_is_not_claimed_to_beat_the_naive_forecast_by_a_complex_method():
    rng = np.random.default_rng(3)
    rep = fv.evaluate_series(frame(np.maximum(0, rng.normal(30, 4, 200))), [7], TODAY)
    h = rep["horizons"][0]
    assert h["production"]["selected_method"] == "trailing_mean_28"        # the baseline stays
    assert h["verdict"] in ("beats_references", "beats_naive_only", "does_not_beat_naive")   # a verdict is always stated, never implied


def test_short_history_is_reported_as_insufficient_not_as_a_metric():
    rep = fv.evaluate_series(frame(weekly(20)), [14], TODAY)
    h = rep["horizons"][0]
    assert h["status"] == "insufficient_history" and "holdout" not in h and "history" in h["statement"]
    rep2 = fv.evaluate_series(frame(weekly(45)), [7], TODAY)               # origins exist but too few to keep an untouched holdout
    h2 = rep2["horizons"][0]
    assert h2["status"] == "descriptive_only" and "holdout" not in h2 and "no comparison is a validation" in h2["statement"]


def test_evaluation_of_a_prefix_does_not_depend_on_later_days():
    """Chronology: the origins that exist in a truncated series give identical metrics when later days change."""
    y = weekly(150)
    y2 = y.copy()
    y2[130:] = 9999.0                                    # change the most recent days only
    r1 = fv.evaluate_series(frame(y), [7], TODAY)["horizons"][0]["all_origins"]["trailing_mean_28"]
    r2 = fv.evaluate_series(frame(y2), [7], TODAY)["horizons"][0]["all_origins"]["trailing_mean_28"]
    assert r1["mae"] != r2["mae"]                        # later actuals do change the score of the origins that include them ...
    pref = frame(y[:130])
    p1 = fv.evaluate_series(pref, [7], TODAY)["horizons"][0]["all_origins"]["trailing_mean_28"]
    p2 = fv.evaluate_series(frame(np.concatenate([y[:130], np.full(20, 5.0)])).iloc[:130], [7], TODAY)["horizons"][0]["all_origins"]["trailing_mean_28"]
    assert p1["mae"] == p2["mae"]                        # ... but a series cut at the same day is unaffected by anything after it
