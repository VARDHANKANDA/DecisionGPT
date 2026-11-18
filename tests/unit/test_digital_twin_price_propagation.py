"""Digital Twin price propagation: does a changed scenario price actually reach the model input, and what does the plumbing do with it?

These tests establish where the flat/unsigned price response CAN and CANNOT come from. They do not impose an elasticity: a model that
ignores price must stay flat, a model that uses price must move, and the registered production model's response is measured and
reported (its sign is not asserted)."""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.analytics import forecast_service as fs
from ml.features.forecasting_features import FEATURE_COLUMNS

LAST = pd.Timestamp("2025-03-31")
SERIES = [10.0 + (i % 7) for i in range(60)]


class Spy:
    """Records every feature row it is asked to predict and returns a configurable function of it."""

    def __init__(self, fn=lambda X: 5.0):
        self.rows, self.fn = [], fn

    def predict(self, X):
        self.rows.append(X.copy())
        return np.array([self.fn(X)])


def test_scenario_price_is_placed_unchanged_in_the_price_column_for_a_range_of_prices():
    for price in (0.5, 99.0, 100.0, 105.0, 1234.56, 50000.0):
        row = fs.build_feature_row(SERIES, LAST + timedelta(days=1), price, 7.0)
        assert list(row.columns) == FEATURE_COLUMNS
        assert float(row["price"].iloc[0]) == price and float(row["marketing_spend"].iloc[0]) == 7.0


def test_only_price_related_columns_differ_between_baseline_and_scenario_rows():
    a = fs.build_feature_row(SERIES, LAST + timedelta(days=1), 100.0, 5.0)
    b = fs.build_feature_row(SERIES, LAST + timedelta(days=1), 110.0, 5.0)
    differing = [c for c in FEATURE_COLUMNS if float(a[c].iloc[0]) != float(b[c].iloc[0])]
    assert differing == ["price"]


def test_recursive_forecast_feeds_the_scenario_price_to_the_model_on_every_step():
    spy = Spy()
    fs.run_recursive_forecast(spy, SERIES, LAST, price=123.0, marketing_spend=4.0, horizon_days=10)
    assert len(spy.rows) == 10
    assert all(float(r["price"].iloc[0]) == 123.0 for r in spy.rows)
    assert all(float(r["marketing_spend"].iloc[0]) == 4.0 for r in spy.rows)


def test_a_model_that_ignores_price_is_flat_so_flat_output_is_a_model_property_not_plumbing():
    flat = Spy(lambda X: 20.0)
    lo = fs.run_recursive_forecast(flat, SERIES, LAST, 80.0, 0.0, 14)
    hi = fs.run_recursive_forecast(flat, SERIES, LAST, 160.0, 0.0, 14)
    assert [p.predicted_value for p in lo] == [p.predicted_value for p in hi]


def test_a_model_that_uses_price_responds_through_the_same_path_and_the_sign_is_the_models_not_the_pipelines():
    dec = Spy(lambda X: max(0.0, 40.0 - 0.2 * float(X["price"].iloc[0])))
    inc = Spy(lambda X: 5.0 + 0.1 * float(X["price"].iloc[0]))
    base_d = sum(p.predicted_value for p in fs.run_recursive_forecast(dec, SERIES, LAST, 100.0, 0.0, 7))
    up_d = sum(p.predicted_value for p in fs.run_recursive_forecast(dec, SERIES, LAST, 110.0, 0.0, 7))
    base_i = sum(p.predicted_value for p in fs.run_recursive_forecast(inc, SERIES, LAST, 100.0, 0.0, 7))
    up_i = sum(p.predicted_value for p in fs.run_recursive_forecast(inc, SERIES, LAST, 110.0, 0.0, 7))
    assert up_d < base_d  # decreasing model -> decreasing curve
    assert up_i > base_i  # increasing model -> increasing curve: the pipeline neither flips nor forces a sign


def test_promotion_flag_is_not_expressible_in_scenarios_today():
    """Known limitation, pinned: the promotion feature is hard-coded to 0 at inference, so a scenario cannot express a promotion."""
    row = fs.build_feature_row(SERIES, LAST + timedelta(days=1), 100.0, 0.0)
    assert int(row["promotion_flag"].iloc[0]) == 0


def test_price_features_are_the_only_price_pathway():
    """If a future change adds another price-derived column the response curves in docs/ML_BENCHMARK_REPORT.md must be regenerated."""
    assert [c for c in FEATURE_COLUMNS if "price" in c] == ["price"]


def test_the_registered_production_model_responds_to_price_but_the_response_is_reported_not_asserted():
    import joblib
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "models" / "sales_forecast_xgboost" / "v1" / "model.joblib"
    if not path.exists():
        pytest.skip("registered model artifact not present")
    model = joblib.load(path)
    base = fs.run_recursive_forecast(model, SERIES, LAST, 1000.0, 0.0, 14)
    out = {}
    for pct in (-30, -10, 10, 30):
        pts = fs.run_recursive_forecast(model, SERIES, LAST, round(1000.0 * (1 + pct / 100), 2), 0.0, 14)
        out[pct] = sum(p.predicted_value for p in pts) - sum(p.predicted_value for p in base)
    assert all(np.isfinite(v) for v in out.values())  # finite, deterministic; the (unreliable) sign is documented elsewhere
    assert out == {pct: sum(p.predicted_value for p in fs.run_recursive_forecast(model, SERIES, LAST, round(1000.0 * (1 + pct / 100), 2), 0.0, 14))
                   - sum(p.predicted_value for p in base) for pct in (-30, -10, 10, 30)}


# ------------------------------------------------------------------ identification limitation notes (never change a number)
def test_price_sensitivity_check_flags_histories_without_price_variation():
    from app.analytics.digital_twin_service import price_sensitivity_check

    flat = pd.DataFrame({"price": [100.0] * 60})
    two_values = pd.DataFrame({"price": [540.0, 600.0] * 45})
    varied = pd.DataFrame({"price": [100 + 10 * np.sin(i / 3) + (i % 7) for i in range(90)]})
    short = pd.DataFrame({"price": list(range(90, 110))})
    assert price_sensitivity_check(flat)["identified"] is False
    assert price_sensitivity_check(two_values)["identified"] is False      # 2 distinct values, even with 5% spread
    assert price_sensitivity_check(short)["identified"] is False           # fewer than 28 days
    assert price_sensitivity_check(varied)["identified"] is True


def test_notes_state_the_limitation_and_flag_a_same_direction_response():
    from app.analytics.digital_twin_service import price_response_notes, price_sensitivity_check

    flat = price_sensitivity_check(pd.DataFrame({"price": [100.0] * 60}))
    flat_notes = price_response_notes(flat, 10.0, 100.0, 120.0)
    assert any("NOT identified" in n and "no price effect is shown" in n for n in flat_notes)   # nothing is shown, so no projected-effect claim
    assert not any("projected effect" in n for n in flat_notes)
    ok = price_sensitivity_check(pd.DataFrame({"price": [100 + (i % 9) * 3 for i in range(60)]}))
    assert ok["identified"] and any("association" in n for n in price_response_notes(ok, 5.0, 100.0, 99.0))
    assert any("SAME direction" in n for n in price_response_notes(ok, 10.0, 100.0, 120.0))
    assert not any("SAME direction" in n for n in price_response_notes(ok, 10.0, 100.0, 90.0))    # units fell with price: ordinary
    assert not any("SAME direction" in n for n in price_response_notes(ok, -10.0, 100.0, 120.0))  # price fell, units rose: ordinary


def test_the_price_effect_needs_an_eligible_model_even_when_the_history_varies():
    from app.analytics.digital_twin_service import price_effect_check, price_response_status

    varied = pd.DataFrame({"price": [100 + (i % 9) * 3 for i in range(60)]})
    chk = price_effect_check(varied, None)                        # no model recorded as eligible for price scenarios
    assert chk["data_supports_price_effect"] is True and chk["identified"] is False and chk["model_eligible"] is False
    st = price_response_status(chk)
    assert st["withheld"] is True and st["reason"] == "model"
    assert len(st["needed"]) == 1 and "forecasting model" in st["needed"][0]      # only the unmet requirement is listed
    flat = price_response_status(price_effect_check(pd.DataFrame({"price": [100.0] * 60}), None))
    assert flat["reason"] == "history" and not any("at least 28 days" in n for n in flat["needed"])   # 60 days: that criterion is met
    assert any("different average prices" in n for n in flat["needed"]) and any("forecasting model" in n for n in flat["needed"])
