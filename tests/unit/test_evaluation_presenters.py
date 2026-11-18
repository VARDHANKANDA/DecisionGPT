"""The presenters that turn a stored validation report into registry cards, on hand-built reports (no database, no model)."""
import json

import pytest

from app.services import evaluation_console_service as svc


def _holdout(mae=3.0):
    return {"mae": mae, "rmse": mae * 1.3, "wape": 0.2, "bias_units_per_day": -0.4, "relative_bias": -0.03, "wape_note": None, "n_origins": 8, "n_points": 56}


def _evaluated(h=7):
    return {
        "horizon_days": h, "status": "evaluated", "origins": 20, "holdout_origins": 8, "statement": "s",
        "production": {"selected_method": "weekday_mean_4w", "basis": "validated"},
        "holdout": {"weekday_mean_4w": _holdout(3.0), "naive_last": _holdout(4.0), "seasonal_naive_7": _holdout(3.5), "trailing_mean_28": _holdout(3.2)},
        "interval": {"nominal_coverage": 0.8, "observed_holdout_coverage": 0.75, "holdout_points": 56, "limitation": "dependent points", "reliable_by_policy": True},
        "comparison_on_holdout": {"selected_vs_naive_last_mae_ratio": 0.75, "selected_vs_trailing_mean_mae_ratio": 0.9375, "selected_vs_seasonal_naive_mae_ratio": None},
        "verdict": "beats_references",
    }


REPORT = {
    "id": "r1", "generated_at": "2026-10-21T00:00:00Z", "code_revision": "abc", "headline": "h",
    "dataset": {"first_date": "2026-01-01", "last_date": "2026-06-01"}, "series": {"series_class": "regular", "pattern": "smooth"},
    "horizons": [
        _evaluated(7),
        {"horizon_days": 14, "status": "descriptive_only", "origins": 3, "statement": "too few", "all_origins": {"naive_last": _holdout(5.0)}},
        {"horizon_days": 28, "status": "insufficient_history", "statement": "needs more days"},
    ],
    "evidence": {"not_evidence_of": ["business impact"]},
}


def _by(cards):
    return {c["key"]: c for c in cards}


def test_an_evaluated_horizon_carries_every_forecast_metric_with_sign_convention_and_units():
    out = svc.present_run(REPORT, "forecast")
    h = out["horizons"][0]
    c = _by(h["cards"])
    assert c["mae"]["value"] == 3.0 and c["mae"]["unit"] == "units/day" and c["rmse"]["value"] == pytest.approx(3.9)
    assert c["wape"]["value"] == pytest.approx(20.0) and c["bias"]["value"] == -0.4 and "Negative" in c["bias"]["sign_note"]
    assert c["relative_bias"]["value"] == pytest.approx(-3.0) and c["n_eval"]["value"] == 56
    assert h["method"] == "weekday_mean_4w" and h["verdict"] == "beats_references"
    assert h["interval_coverage"]["value"] == pytest.approx(75.0) and h["interval_coverage"]["context"]["promised"] == "80%"
    assert h["interval_coverage"]["caveat"].endswith("dependent points")


def test_baseline_ratios_are_passed_through_unchanged_and_a_missing_one_stays_missing():
    comp = {c["reference"]: c["mae_ratio"] for c in svc.present_run(REPORT, "forecast")["horizons"][0]["baseline_comparison"]}
    assert comp == {"naive_last": 0.75, "trailing_mean_28": 0.9375, "seasonal_naive_7": None}


def test_a_descriptive_horizon_is_labelled_descriptive_and_has_no_coverage():
    h = svc.present_run(REPORT, "forecast")["horizons"][1]
    assert h["status"] == "descriptive_only" and h["cards"] == []
    assert h["interval_coverage"]["status"] == "not_evaluated" and h["interval_coverage"]["value"] is None
    assert h["references"][0]["cards"][0]["context"]["block"].startswith("all backtest origins")


def test_a_horizon_with_too_little_history_is_not_evaluated_with_the_reason():
    h = svc.present_run(REPORT, "forecast")["horizons"][2]
    assert h["cards"] == [] and h["interval_coverage"]["status"] == "not_evaluated" and "needs more days" in h["interval_coverage"]["reason"]


def test_undefined_wape_is_not_shown_as_zero():
    rep = json.loads(json.dumps(REPORT))
    rep["horizons"][0]["holdout"]["weekday_mean_4w"].update(wape=None, relative_bias=None, wape_note="undefined: the actual units sum to 0")
    c = _by(svc.present_run(rep, "forecast")["horizons"][0]["cards"])
    assert c["wape"]["status"] == "not_available" and c["wape"]["value"] is None and "sum to 0" in c["wape"]["reason"]
    assert c["relative_bias"]["status"] == "not_available"


CUSTOMER = {
    "id": "c1", "generated_at": "2026-10-21T00:00:00Z", "model": {"name": "churn", "version": "v1"}, "headline": "h",
    "target": {"definition": "no purchase in 60 days", "limits": "proxy"}, "stable_across_cutoffs": True,
    "calibration": {"evaluated": False, "reason": "proxy label"},
    "cutoffs": [
        {"cutoff": "2026-05-01", "status": "evaluated", "customers": 120, "inactive": 40, "prevalence": 40 / 120, "roc_auc": 0.7, "roc_auc_recency_only": 0.65,
         "top_decile_lift": 1.8, "top_decile_inactive_rate": 0.6},
        {"cutoff": "2026-03-01", "status": "insufficient_evidence", "reason": "needs at least 30 customers"},
    ],
}


def test_customer_check_shows_ranking_metrics_only_where_it_was_evaluated():
    out = svc.present_run(CUSTOMER, "customer")
    ev, skipped = out["cutoffs"]
    auc = [c for c in ev["cards"] if c["key"] == "roc_auc"]
    assert [c["value"] for c in auc] == [0.7, 0.65] and auc[1]["context"]["reference"].startswith("ranking by days since last purchase")
    assert auc[0]["context"]["positive_class"].startswith("inactive")
    assert "cards" not in skipped and skipped["status"] == "insufficient_evidence" and skipped["reason"]


def test_customer_check_never_claims_calibration():
    out = svc.present_run(CUSTOMER, "customer")
    assert out["calibration"]["status"] == "not_evaluated" and out["calibration"]["value"] is None and "proxy" in out["calibration"]["reason"]


def test_presented_runs_are_strict_json():
    json.dumps(svc.present_run(REPORT, "forecast"), allow_nan=False)
    json.dumps(svc.present_run(CUSTOMER, "customer"), allow_nan=False)
