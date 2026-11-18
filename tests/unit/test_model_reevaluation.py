"""Forecast metric arithmetic used by the Research Console's accuracy summary: hand-computed values, zero denominators, empty and invalid data,
the relative-improvement formula, the verification gate and the percentage formatting."""
import math

import numpy as np
import pytest

from app.services import model_reevaluation_service as R
from app.services.metric_registry import card


# ---------------------------------------------------------------- score_pairs: hand arithmetic
def test_wape_mae_rmse_bias_match_hand_arithmetic():
    y = [10, 0, 20]
    p = [12, 1, 18]
    s = R.score_pairs(y, p)
    assert s["n_eval"] == 3 and s["n_invalid"] == 0 and s["n_zero_actual"] == 1
    assert s["mae"] == pytest.approx((2 + 1 + 2) / 3)                         # 1.6667
    assert s["rmse"] == pytest.approx(math.sqrt((4 + 1 + 4) / 3))             # 1.7321
    assert s["wape"] == pytest.approx(5 / 30)                                  # sum|e| / sum|y| = 0.16667 (a fraction; the card shows 16.7%)
    assert s["bias"] == pytest.approx((2 + 1 - 2) / 3)                         # forecast minus actual: positive = over-forecast


def test_wape_is_a_ratio_of_sums_not_a_mean_of_ratios():
    s = R.score_pairs([100, 1], [90, 2])                                       # errors 10 and 1 on actuals 100 and 1
    assert s["wape"] == pytest.approx(11 / 101)                                # the mean of per-row ratios would be (0.1 + 1.0) / 2 = 0.55


# ---------------------------------------------------------------- zero denominators, empty and invalid data
def test_all_zero_actuals_give_no_wape_never_zero_and_never_infinity():
    s = R.score_pairs([0, 0, 0], [1, 2, 3])
    assert s["wape"] is None and s["n_zero_actual"] == 3
    assert s["mae"] == pytest.approx(2.0)                                      # MAE is still defined


def test_perfect_forecast_has_wape_zero_which_is_a_real_zero_not_a_missing_value():
    s = R.score_pairs([5, 10], [5, 10])
    assert s["wape"] == 0.0 and s["mae"] == 0.0


def test_empty_evaluation_set_computes_nothing():
    s = R.score_pairs([], [])
    assert s["n_eval"] == 0 and all(s[k] is None for k in ("mae", "rmse", "mape", "wape", "bias"))


def test_non_finite_pairs_are_left_out_and_counted():
    s = R.score_pairs([10, 20, np.nan, 30], [11, np.inf, 5, 27])
    assert s["n_eval"] == 2 and s["n_invalid"] == 2
    assert s["mae"] == pytest.approx((1 + 3) / 2) and s["wape"] == pytest.approx(4 / 40)


def test_only_invalid_pairs_means_no_metrics():
    s = R.score_pairs([np.nan], [1.0])
    assert s["n_eval"] == 0 and s["n_invalid"] == 1 and s["wape"] is None


def test_mismatched_lengths_are_rejected_not_silently_truncated():
    with pytest.raises(ValueError):
        R.score_pairs([1, 2, 3], [1, 2])


# ---------------------------------------------------------------- relative improvement over the baseline
def test_relative_improvement_formula():
    assert R.relative_improvement_pct(0.20, 0.10) == pytest.approx(50.0)       # 100 x (baseline - model) / baseline
    assert R.relative_improvement_pct(0.10, 0.12) == pytest.approx(-20.0)      # worse than the baseline is negative
    assert R.relative_improvement_pct(0.156483, 0.096067) == pytest.approx(100 * (0.156483 - 0.096067) / 0.156483)


@pytest.mark.parametrize("baseline,model", [(None, 0.1), (0.1, None), (0.0, 0.1), (-0.1, 0.1), (float("nan"), 0.1), (0.1, float("inf")), ("x", 0.1)])
def test_relative_improvement_is_undefined_never_zero_when_an_input_is_missing_or_the_baseline_is_not_positive(baseline, model):
    assert R.relative_improvement_pct(baseline, model) is None


# ---------------------------------------------------------------- the verification gate (training-time metrics must be reproduced)
def test_a_rescoring_that_reproduces_the_recorded_metrics_is_accepted():
    recomputed = {"mae": 4.0, "rmse": 6.0, "mape": 22.0}
    v = R.verify_against_stored(recomputed, {"mae": 4.0000001, "rmse": 6.0, "mape": 22.0})
    assert v["stored_metrics_matched"] is True and set(v["compared"]) == {"mae", "rmse", "mape"}


def test_a_rescoring_that_does_not_reproduce_the_recorded_metrics_is_rejected():
    v = R.verify_against_stored({"mae": 5.0, "rmse": 6.0, "mape": 22.0}, {"mae": 4.0, "rmse": 6.0, "mape": 22.0})
    assert v["stored_metrics_matched"] is False and v["compared"]["mae"]["match"] is False and v["reason"]


def test_without_any_recorded_metric_nothing_can_be_verified():
    assert R.verify_against_stored({"mae": 1.0, "rmse": 1.0, "mape": 1.0}, {})["stored_metrics_matched"] is False


# ---------------------------------------------------------------- units and formatting of the cards
def test_wape_is_shown_as_a_percentage_of_the_stored_fraction():
    c = card("wape", 0.123456, as_percent_of_fraction=True)
    assert c["status"] == "available" and c["display"] == "12.3%" and c["unit"] == "percent" and c["value"] == pytest.approx(12.3456)


def test_relative_wape_change_is_signed_and_a_missing_one_is_not_available_not_zero():
    assert card("wape_vs_baseline", 29.94)["display"] == "+29.9%"
    assert card("wape_vs_baseline", -12.0)["display"] == "-12.0%"
    gone = card("wape_vs_baseline", None, reason="needs a positive baseline WAPE")
    assert gone["status"] != "available" and gone["value"] is None and gone["display"] != "0.0%"


def test_mae_and_rmse_carry_the_target_unit():
    assert card("mae", 17.2913, target_unit="units/day")["display"] == "17.29 units/day"
    assert card("rmse", 25.5112, target_unit="units/day")["display"] == "25.51 units/day"


def test_non_finite_values_never_become_numbers():
    for bad in (float("nan"), float("inf"), None, "12"):
        assert card("wape", bad, as_percent_of_fraction=True)["value"] is None
