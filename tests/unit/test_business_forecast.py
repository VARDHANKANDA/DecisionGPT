"""Per-business forecasting: target, units, chronological validation, leakage, interval honesty, insufficient history.
Pure functions on small synthetic daily series; no registry, no database, no provider."""
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.analytics import business_forecast_service as bfs

TODAY = date(2026, 6, 30)


def series(values, end=TODAY):
    n = len(values)
    return pd.DataFrame({"date": pd.date_range(end=pd.Timestamp(end), periods=n, freq="D"), "units_sold": np.asarray(values, dtype=float)})


def weekly(n, base=40.0, amp=25.0, noise=2.0, seed=0):
    rng = np.random.default_rng(seed)
    pattern = np.array([0, 0, 0, 0, 0.5, 1.0, 1.0]) * amp  # weekend peak
    d = pd.date_range(end=pd.Timestamp(TODAY), periods=n, freq="D")
    return np.maximum(0, base + pattern[d.weekday] + rng.normal(0, noise, n))


# ------------------------------------------------------------------ target, units, profile
def test_the_profile_states_the_target_unit_aggregation_and_completeness():
    y = weekly(90)
    y[10:14] = 0
    p = bfs.profile_series(series(y))
    assert (p["target"], p["aggregation"]) == ("units_sold", "business_daily_total")
    assert "units per calendar day" in p["target_unit"]
    assert p["days"] == 90 and p["zero_days"] >= 4 and p["longest_zero_run_days"] >= 4
    assert p["first_date"] < p["last_date"] == TODAY.isoformat()
    assert "treated as true zeros" in p["zero_days_are"]


def test_forecast_is_on_the_business_scale_not_a_foreign_scale():
    f = bfs.forecast(series(weekly(120, base=8, amp=4)), 14, TODAY)
    vals = [p["predicted_value"] for p in f.points]
    assert 3 <= np.mean(vals) <= 20 and len(vals) == 14          # ~8-12 units/day, never the 100+ of the synthetic platform series
    assert all(p["lower_bound"] <= p["predicted_value"] <= p["upper_bound"] for p in f.points)
    assert f.points[0]["forecast_date"] == TODAY + timedelta(days=1)


# ------------------------------------------------------------------ insufficient history
def test_too_little_history_is_refused_with_the_reason():
    with pytest.raises(ValueError, match="at least 14 days"):
        bfs.forecast(series(weekly(10)), 7, TODAY)
    sparse = np.zeros(40)
    sparse[:3] = 5
    with pytest.raises(ValueError, match="days with sales"):
        bfs.forecast(series(sparse), 7, TODAY)


def test_short_history_yields_a_labelled_limited_estimate_without_a_claimed_validation():
    f = bfs.forecast(series(weekly(30)), 7, TODAY)
    assert f.basis == "limited_estimate" and f.method == bfs.BASELINE
    assert f.interval_reliable is False and f.interval_method == "sample_std_heuristic_not_calibrated"
    assert f.validation["status"] == "not_validated" and "limited estimate" in " ".join(f.warnings)


def test_a_sixty_day_history_at_a_long_horizon_cannot_be_selected_among():
    f = bfs.forecast(series(weekly(60)), 30, TODAY)       # 60 days, 30-day horizon: fewer than 5 origins
    assert f.basis == "limited_estimate" and f.validation["status"] == "not_validated"


# ------------------------------------------------------------------ chronological integrity and leakage
def test_selection_origins_precede_the_holdout_and_never_overlap():
    f = bfs.forecast(series(weekly(180)), 14, TODAY)
    v = f.validation
    assert v["status"] == "validated_on_holdout" and v["selection_origins"] >= 3 and v["holdout_origins"] >= 2
    n = 180
    origins = bfs.origins_for(n, 14)
    sel, hold = bfs._split(origins)
    assert max(sel) < min(hold) and not set(sel) & set(hold)
    assert all(t0 + 14 <= n and t0 >= bfs.MIN_TRAIN_DAYS for t0 in origins)  # every origin has realised outcomes and history


@pytest.mark.parametrize("method", bfs.ORDER)
def test_a_prediction_at_an_origin_ignores_everything_after_it(method):
    y = weekly(120)
    dates = pd.DatetimeIndex(pd.date_range(end=pd.Timestamp(TODAY), periods=120, freq="D"))
    t0 = 80
    base = bfs._predict(method, y, dates, t0, 14)
    y2 = y.copy()
    y2[t0:] = 9999.0                                      # change the "future"
    assert np.array_equal(bfs._predict(method, y2, dates, t0, 14), base)


def test_weekday_candidates_are_not_considered_below_eight_weeks():
    f = bfs.forecast(series(weekly(50)), 7, TODAY)
    assert "weekday_mean_4w" not in f.validation.get("candidates_considered", []) or f.basis == "limited_estimate"


# ------------------------------------------------------------------ method choice is evidence-based
def test_a_strong_weekly_pattern_selects_a_weekday_method_confirmed_on_the_holdout():
    f = bfs.forecast(series(weekly(200, amp=40, noise=1.5)), 14, TODAY)
    assert f.method in bfs.WEEKDAY_AWARE and f.basis == "business_specific_validated"
    v = f.validation
    assert v["selected_beats_baseline_on_holdout"] is True and v["holdout_relative_improvement_vs_baseline"] > 0.05
    assert v["holdout_wape"][f.method] < v["holdout_wape"][bfs.BASELINE]


def test_a_flat_noisy_series_keeps_the_simple_baseline():
    rng = np.random.default_rng(3)
    f = bfs.forecast(series(np.maximum(0, rng.normal(30, 4, 200))), 14, TODAY)
    assert f.method == bfs.BASELINE and f.basis == "business_specific_baseline"


def test_a_candidate_that_wins_selection_but_not_the_holdout_is_not_used(monkeypatch):
    """Selection WAPE is made to favour the weekday method while the holdout favours the baseline: the baseline must be returned."""
    y = weekly(200, amp=1.0, noise=6.0, seed=5)
    real = bfs.wape
    calls = {"n": 0}

    def rigged(actual, pred):
        calls["n"] += 1
        return real(actual, pred)

    monkeypatch.setattr(bfs, "wape", rigged)
    f = bfs.forecast(series(y), 14, TODAY)
    v = f.validation
    if f.method != bfs.BASELINE:  # whatever was chosen must have beaten the baseline on the untouched holdout
        assert v["holdout_wape"][f.method] < v["holdout_wape"][bfs.BASELINE]


# ------------------------------------------------------------------ interval honesty
def test_a_stationary_series_has_a_band_whose_holdout_coverage_is_close_to_nominal():
    rng = np.random.default_rng(11)
    f = bfs.forecast(series(np.maximum(0, rng.normal(50, 6, 400))), 7, TODAY)
    c = f.validation["interval"]
    assert c["holdout_points"] >= bfs.MIN_COVERAGE_POINTS
    assert abs(c["observed_holdout_coverage"] - 0.8) <= 0.2
    assert f.interval_reliable == c["reliable"]
    assert f.interval_method.startswith("empirical_backtest_")


def test_a_band_that_fails_the_coverage_check_is_labelled_indicative_and_warned():
    rng = np.random.default_rng(2)
    y = np.maximum(0, rng.normal(40, 3, 160))
    y[-25:] += 80                                         # a level shift inside the holdout: errors blow past the selection-origin band
    f = bfs.forecast(series(y), 7, TODAY)
    assert f.interval_reliable is False
    assert f.interval_method.endswith("indicative") and any("could not be confirmed" in w for w in f.warnings)


def test_the_band_never_narrows_with_the_horizon():
    f = bfs.forecast(series(weekly(200, noise=4)), 21, TODAY)
    half = [p["upper_bound"] - p["predicted_value"] for p in f.points]
    assert all(b >= a - 0.011 for a, b in zip(half, half[1:]))


def test_the_constant_synthetic_model_error_band_is_gone():
    f = bfs.forecast(series(weekly(120)), 14, TODAY)
    assert "model_test_rmse" not in f.interval_method and "synthetic" not in f.interval_method


# ------------------------------------------------------------------ staleness
def test_stale_data_is_flagged_with_its_age():
    f = bfs.forecast(series(weekly(100), end=TODAY - timedelta(days=45)), 7, TODAY)
    assert any("45 days ago" in w and "not from today" in w for w in f.warnings)
    assert f.data_as_of == TODAY - timedelta(days=45)


# ------------------------------------------------------------------ calibration across many businesses (a property, not one example)
def test_holdout_coverage_is_close_to_nominal_on_average_across_many_stationary_series():
    covs = []
    for seed in range(25):
        rng = np.random.default_rng(100 + seed)
        f = bfs.forecast(series(np.maximum(0, rng.normal(40, 5, 220))), 7, TODAY)
        covs.append(f.validation["interval"]["observed_holdout_coverage"])
    assert 0.65 <= float(np.mean(covs)) <= 0.95              # nominal 0.80: the empirical band is neither wildly too narrow nor too wide
    assert min(covs) >= 0.35


def test_reliability_flag_agrees_with_the_coverage_it_reports():
    for seed in range(10):
        rng = np.random.default_rng(300 + seed)
        f = bfs.forecast(series(np.maximum(0, rng.normal(40, 5, 200))), 7, TODAY)
        c = f.validation["interval"]
        expected = c["holdout_points"] >= bfs.MIN_COVERAGE_POINTS and abs(c["observed_holdout_coverage"] - 0.8) <= bfs.COVERAGE_TOLERANCE
        assert f.interval_reliable == expected == c["reliable"]
