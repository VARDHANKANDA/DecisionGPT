"""The shared metric definitions and the single card presenter: formulas on known data, units and sign conventions, and the rule that a
missing, non-finite or undefined value is never shown as a number."""
import json
import math

import numpy as np
import pytest

from app.services import metric_registry as mr
from ml.evaluation.metrics import mae, regression_diagnostics, regression_metrics, rmse, wape


# ------------------------------------------------------------------ formulas on data small enough to check by hand
def test_mae_rmse_wape_match_hand_computation():
    y, p = np.array([10.0, 20.0, 30.0]), np.array([12.0, 18.0, 33.0])
    assert mae(y, p) == pytest.approx((2 + 2 + 3) / 3)
    assert rmse(y, p) == pytest.approx(math.sqrt((4 + 4 + 9) / 3))
    assert wape(y, p) == pytest.approx(7 / 60)


def test_wape_is_left_out_not_zero_when_actuals_sum_to_zero():
    assert wape(np.zeros(3), np.array([1.0, 2.0, 3.0])) is None
    assert "wape" not in regression_metrics(np.zeros(3), np.array([1.0, 2.0, 3.0]))


def test_diagnostics_bias_sign_convention_and_counts():
    d = regression_diagnostics(np.array([0.0, 2.0, 4.0]), np.array([1.0, 2.0, 2.0]))
    assert d["n_eval"] == 3 and d["n_zero_actual"] == 1 and d["n_invalid"] == 0
    assert d["bias"] == pytest.approx((1 + 0 - 2) / 3)               # forecast - actual: negative means the forecast is too low
    over = regression_diagnostics(np.array([10.0, 10.0]), np.array([13.0, 12.0]))
    assert over["bias"] > 0


def test_diagnostics_leave_out_non_finite_pairs_and_count_them():
    d = regression_diagnostics(np.array([1.0, np.nan, 3.0, 4.0]), np.array([1.0, 2.0, np.inf, 5.0]))
    assert d["n_eval"] == 2 and d["n_invalid"] == 2 and d["bias"] == pytest.approx(0.5)
    empty = regression_diagnostics(np.array([np.nan]), np.array([1.0]))
    assert empty["n_eval"] == 0 and "bias" not in empty               # no number is invented from nothing


def test_diagnostics_do_not_change_the_existing_metric_values():
    y, p = np.array([5.0, 7.0, 9.0]), np.array([6.0, 5.0, 9.5])
    before = regression_metrics(y, p)
    regression_diagnostics(y, p)
    assert regression_metrics(y, p) == before


# ------------------------------------------------------------------ the registry itself
def test_every_metric_has_a_plain_definition_a_direction_and_a_task():
    assert mr.REGISTRY
    for key, d in mr.REGISTRY.items():
        assert d.key == key and d.name and d.abbr and len(d.definition) > 20
        assert d.direction in (mr.LOWER, mr.HIGHER, mr.ZERO, mr.NOMINAL, mr.INFO)
        assert d.task in ("regression", "classification", "calibration", "data")


def test_signed_metrics_state_what_positive_means():
    assert "over-forecast" in mr.REGISTRY["bias"].sign_note.lower()
    assert "under-forecast" in mr.REGISTRY["bias"].sign_note.lower()
    assert mr.REGISTRY["bias"].direction == mr.ZERO


def test_the_glossary_is_json_serialisable_and_complete():
    g = mr.metric_definitions()
    assert {m["key"] for m in g} == set(mr.REGISTRY)
    json.dumps(g)


# ------------------------------------------------------------------ card: no fabrication
@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), float("-inf"), "0.5", True, [], {}])
def test_a_missing_or_non_finite_value_is_never_a_number(bad):
    c = mr.card("mae", bad, target_unit="units/day")
    assert c["status"] == mr.NOT_AVAILABLE and c["value"] is None and c["display"] == "Not available" and c["reason"]
    text = json.dumps(c).lower()
    assert "nan" not in text.replace("name", "").replace("nominal", "") and "infinity" not in text


def test_not_evaluated_and_unreliable_carry_a_reason_and_no_value():
    a = mr.card("coverage", 0.8, status=mr.NOT_EVALUATED, reason="no intervals")
    assert a["status"] == mr.NOT_EVALUATED and a["value"] is None and a["display"] == "Not evaluated" and a["reason"] == "no intervals"
    b = mr.card("mape", 12.0, status=mr.UNRELIABLE)
    assert b["status"] == mr.UNRELIABLE and b["value"] is None and b["display"] == "Not reliable" and b["reason"]


def test_units_precision_and_percent_conversion():
    assert mr.card("mae", 1.2345, target_unit="units/day")["display"] == "1.23 units/day"
    assert mr.card("wape", 0.2345, as_percent_of_fraction=True)["display"] == "23.4%"
    assert mr.card("bias", 0.5, target_unit="units/day")["display"].startswith("+0.50")
    assert mr.card("bias", -0.5, target_unit="units/day")["display"].startswith("-0.50")
    assert mr.card("n_eval", 12345)["display"] == "12,345"
    assert mr.card("roc_auc", 0.81234)["display"] == "0.812"


def test_card_carries_direction_explanation_and_caveat():
    c = mr.card("mae", 2.0, target_unit="units/day", context={"n": 5})
    assert c["direction"] == mr.LOWER and c["direction_text"] == "Lower is better"
    assert c["explanation"] and c["caveat"] and c["context"] == {"n": 5} and c["abbr"] == "MAE"


# ------------------------------------------------------------------ MAPE validity policy
def test_mape_is_unreliable_when_zero_actuals_were_recorded():
    c = mr.mape_card(55.0, n_zero_actual=4, n_eval=100)
    assert c["status"] == mr.UNRELIABLE and "4" in c["reason"] and "WAPE" in c["reason"] and c["value"] is None


def test_mape_from_an_older_run_with_an_absurd_value_is_not_shown():
    c = mr.mape_card(8.7e8, n_zero_actual=None, n_eval=None)
    assert c["status"] == mr.UNRELIABLE and c["value"] is None


def test_mape_with_no_zero_actuals_is_shown():
    c = mr.mape_card(18.4, n_zero_actual=0, n_eval=300)
    assert c["status"] == mr.AVAILABLE and c["value"] == pytest.approx(18.4)
    assert "did not record" not in c["caveat"]


def test_mape_with_unknown_zero_count_is_shown_with_a_note_when_plausible():
    c = mr.mape_card(18.4, n_zero_actual=None, n_eval=None)
    assert c["status"] == mr.AVAILABLE and "did not record" in c["caveat"]


def test_mape_missing_is_not_available():
    assert mr.mape_card(None, n_zero_actual=None, n_eval=None)["status"] == mr.NOT_AVAILABLE


# ------------------------------------------------------------------ baseline comparison
def test_improvement_vs_baseline_is_percent_below_the_baseline():
    assert mr.improvement_vs_baseline(8.0, 10.0) == pytest.approx(20.0)
    assert mr.improvement_vs_baseline(12.0, 10.0) == pytest.approx(-20.0)


@pytest.mark.parametrize("m,b", [(None, 10.0), (8.0, None), (8.0, 0.0), (float("nan"), 10.0), (8.0, float("inf"))])
def test_improvement_vs_baseline_is_none_when_not_defined(m, b):
    assert mr.improvement_vs_baseline(m, b) is None


# ------------------------------------------------------------------ the finer state behind a missing value
@pytest.mark.parametrize("status,kind,display", [
    (None, "not_recorded", "Not available"), (mr.NOT_EVALUATED, "not_evaluated", "Not evaluated"), (mr.UNRELIABLE, "unreliable", "Not reliable")])
def test_a_missing_value_has_a_default_kind_that_matches_its_status(status, kind, display):
    c = mr.card("mae", None, status=status)
    assert c["kind"] == kind and c["display"] == display and c["value"] is None


@pytest.mark.parametrize("kind,display", [("not_applicable", "Not applicable"), ("insufficient_data", "Insufficient data"), ("failed", "Failed"),
                                          ("not_recorded", "Not available"), ("not_evaluated", "Not evaluated"), ("unreliable", "Not reliable")])
def test_an_explicit_kind_names_the_reason_in_words_and_still_carries_no_number(kind, display):
    c = mr.card("coverage", None, kind=kind, reason="why")
    assert c["kind"] == kind and c["display"] == display and c["value"] is None and c["reason"] == "why"


def test_an_available_value_is_kind_available_and_an_unknown_kind_is_refused():
    assert mr.card("mae", 2.0)["kind"] == "available"
    assert mr.card("mae", 2.0, kind="not_applicable")["kind"] == "available"       # a recorded value is never relabelled
    with pytest.raises(ValueError):
        mr.card("mae", None, kind="made_up")
