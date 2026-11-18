"""Every business-facing surface that could quote a simulated price effect goes through the same gate: counterfactual 'model prediction' and
the debate's pricing option. (Chat, What-If and decisions are covered in test_assistant / test_digital_twin* / test_decision_price_caution.)"""
from app.services import model_registry_service
from tests.integration.test_analytics import _create_business, _seed_rich_business

BASE = "/api/v1/businesses"


def _biz(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    bid = _create_business(client)
    _seed_rich_business(client, bid)
    return bid


def test_counterfactual_price_prediction_states_no_figure_when_the_effect_is_not_supported(client, db_session):
    bid = _biz(client, db_session)
    r = client.post(f"{BASE}/{bid}/counterfactual/run", json={"mode": "model_prediction", "lever": "price_change_pct", "change_pct": 10}).json()
    assert r["classification"] == "not_available" and r["needed"] and "cannot be estimated" in r["headline"]
    assert "expected_revenue" not in r and "difference" not in r and "₹" not in r["headline"]


def test_counterfactual_marketing_prediction_is_unchanged_and_not_a_price_claim(client, db_session):
    bid = _biz(client, db_session)
    r = client.post(f"{BASE}/{bid}/counterfactual/run", json={"mode": "model_prediction", "lever": "marketing_change_pct", "change_pct": 10}).json()
    assert r["classification"] in ("model_based", "not_enough_data")
    if r["classification"] == "model_based":
        assert r["assumptions"][0].startswith("Baseline: your own")      # same baseline as the Forecast page


def test_debate_pricing_option_carries_no_effect_figure(client, db_session):
    bid = _biz(client, db_session)
    r = client.post(f"{BASE}/{bid}/debate/run", json={"question": "Should I raise prices?", "anchor": "latest"}).json()
    assert r["status"] == "completed"
    opts = r["stages"]["specialist_analyses"]["strategy_optimiser"]["options"]
    price = [o for o in opts if o["id"] == "OPT_PRICE"]
    assert price, "the pricing option is still offered as an idea to test"
    assert price[0]["simulation"] is None and "No effect is shown" in price[0]["summary"]
