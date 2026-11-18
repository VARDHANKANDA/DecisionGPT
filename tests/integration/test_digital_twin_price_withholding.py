"""What-If simulation endpoint: an unidentified price response is withheld, not shown as an estimate. Other scenarios are unaffected."""
import pytest

from app.analytics import digital_twin_service as dts
from app.services import model_registry_service
from tests.integration.test_analytics import _create_business, _seed_rich_business

FLAT = {"identified": False, "days": 90, "distinct_prices": 1, "price_cv": 0.0, "thresholds": {"min_days": 28, "min_distinct_prices": 5, "min_cv": 0.05}}
OK = {"identified": True, "days": 90, "distinct_prices": 40, "price_cv": 0.12, "thresholds": {"min_days": 28, "min_distinct_prices": 5, "min_cv": 0.05}}
EFFECT_FIELDS = ("expected_units_sold", "expected_revenue", "expected_profit", "customer_impact", "revenue_lower_bound", "revenue_upper_bound")


@pytest.fixture()
def biz(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    bid = _create_business(client)
    _seed_rich_business(client, bid)
    return bid


def _sim(client, bid, actions):
    r = client.post(f"/api/v1/businesses/{bid}/digital-twin/simulate", json={"actions": actions, "horizon_days": 14})
    assert r.status_code == 200, r.text
    return r.json()


def test_an_unidentified_price_effect_is_withheld_with_what_is_needed(client, biz, monkeypatch):
    monkeypatch.setattr(dts, "price_sensitivity_check", lambda h: FLAT)
    out = _sim(client, biz, [{"type": "price_change", "value": 10}])["output"]
    assert all(out[f] is None for f in EFFECT_FIELDS)                     # no number that could be read as a price effect
    pr = out["price_response"]
    assert pr["status"] == "not_identified" and pr["withheld"] is True and pr["reliable"] is False
    assert len(pr["needed"]) >= 3 and "no price effect is shown" in pr["message"]
    assert out["baseline_units_sold"] > 0 and out["risk_level"]            # baseline and risk indication are kept


def test_the_withheld_effect_cannot_be_recovered_from_a_later_read(client, biz, monkeypatch):
    monkeypatch.setattr(dts, "price_sensitivity_check", lambda h: FLAT)
    sim = _sim(client, biz, [{"type": "price_change", "value": -10}])
    again = client.get(f"/api/v1/businesses/{biz}/digital-twin/simulations/{sim['id']}").json()
    assert again["output"]["expected_revenue"] is None and again["output"]["price_response"]["withheld"] is True


def test_a_combined_scenario_that_includes_price_is_withheld_too(client, biz, monkeypatch):
    monkeypatch.setattr(dts, "price_sensitivity_check", lambda h: FLAT)
    out = _sim(client, biz, [{"type": "price_change", "value": 5}, {"type": "marketing_change", "value": 10}])["output"]
    assert out["expected_revenue"] is None and out["price_response"]["withheld"] is True   # the two effects cannot be separated


def test_a_marketing_only_scenario_is_not_withheld_but_carries_the_applicability_caveat(client, biz, monkeypatch):
    monkeypatch.setattr(dts, "price_sensitivity_check", lambda h: FLAT)
    out = _sim(client, biz, [{"type": "marketing_change", "value": 10}])["output"]
    assert out["price_response"] is None and out["expected_revenue"] is not None
    assert any("was not trained for this business's daily totals" in a for a in out["assumptions"])


def test_price_variation_alone_does_not_unlock_a_price_effect_for_the_synthetic_model(client, biz, monkeypatch):
    """With enough price variation in the history the registered model is still not eligible: units would equal the baseline exactly."""
    monkeypatch.setattr(dts, "price_sensitivity_check", lambda h: OK)
    out = _sim(client, biz, [{"type": "price_change", "value": 10}])["output"]
    pr = out["price_response"]
    assert out["expected_revenue"] is None and out["expected_units_sold"] is None
    assert pr["withheld"] is True and pr["reason"] == "model" and len(pr["needed"]) == 1 and "forecasting model" in pr["needed"][0]
    assert not any("shows how the model treats an input" in a for a in out["assumptions"])


def test_an_identified_price_response_is_shown_but_labelled_an_association(client, biz, monkeypatch):
    from app.services import model_applicability_service as applic

    real = applic.describe
    monkeypatch.setattr(applic, "describe", lambda m: {**real(m), "eligible_for": {**real(m)["eligible_for"], "price_scenarios": True}})
    monkeypatch.setattr(dts, "price_sensitivity_check", lambda h: OK)
    out = _sim(client, biz, [{"type": "price_change", "value": 10}])["output"]
    assert out["expected_revenue"] is not None
    pr = out["price_response"]
    assert pr["status"] == "association_only" and pr["withheld"] is False and pr["reliable"] is False
    assert "association" in pr["message"]


def test_another_business_cannot_read_the_simulation(client, db_session, biz, monkeypatch):
    monkeypatch.setattr(dts, "price_sensitivity_check", lambda h: FLAT)
    sim = _sim(client, biz, [{"type": "price_change", "value": 10}])
    other = _create_business(client)
    assert client.get(f"/api/v1/businesses/{other}/digital-twin/simulations/{sim['id']}").status_code == 404
