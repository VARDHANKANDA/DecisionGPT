"""Production decisions never rank or recommend a price change the business's own history cannot support. Research runs (default options)
keep the earlier behaviour: the selected option is annotated instead."""
import pytest

from app.analytics import digital_twin_service as dts
from app.models.decision import Decision
from app.models.strategy import Strategy
from app.services import decision_service, model_registry_service
from tests.integration.test_analytics import _create_business, _seed_rich_business
from tests.integration.test_decisions import _create_goal

FLAT = {"identified": False, "days": 90, "distinct_prices": 1, "price_cv": 0.0, "thresholds": {"min_days": 28, "min_distinct_prices": 5, "min_cv": 0.05}}
OK = {"identified": True, "days": 90, "distinct_prices": 40, "price_cv": 0.12, "thresholds": {"min_days": 28, "min_distinct_prices": 5, "min_cv": 0.05}}


@pytest.fixture()
def eligible_model(monkeypatch):
    """Make the registered model count as recorded-eligible for price scenarios (it is not, in reality: see the next test)."""
    from app.services import model_applicability_service as applic

    real = applic.describe

    def fake(model):
        d = real(model)
        return {**d, "eligible_for": {**d["eligible_for"], "price_scenarios": True, "business_level_forecast": True}}

    monkeypatch.setattr(applic, "describe", fake)


@pytest.fixture()
def ready(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    bid = _create_business(client)
    _seed_rich_business(client, bid)
    return bid, _create_goal(client, bid, "Increase revenue by 10% in 2 months")


def _actions(db_session, decision_id):
    row = db_session.get(Decision, decision_id)
    return (db_session.get(Strategy, row.selected_strategy_id).actions_json or []), row


def test_unidentified_price_response_withholds_price_options_and_keeps_other_recommendations(client, db_session, ready, monkeypatch):
    bid, goal = ready
    monkeypatch.setattr(dts, "price_sensitivity_check", lambda history: FLAT)
    r = client.post(f"/api/v1/businesses/{bid}/decisions/analyze", json={"goal_id": goal})
    assert r.status_code == 200, r.text
    d = r.json()
    actions, row = _actions(db_session, d["id"])
    assert actions and all(a["type"] != "price_change" for a in actions)       # a non-price option was recommended instead
    assert d["selected_strategy_name"].startswith("Marketing")
    assert "Price options were withheld" in d["reasoning"] and "Needed to evaluate price changes" in d["reasoning"]
    assert any(s.startswith("Price ") and "withheld" in s for s in d["skipped_strategies"])
    assert all(not a["strategy_name"].startswith("Price ") for a in d["alternatives"])    # never ranked among the alternatives
    assert row.debate_json["pipeline_options"]["price_response_gate"] is True


def test_price_variation_alone_does_not_unlock_price_options_for_a_synthetic_model(client, db_session, ready, monkeypatch):
    """The history varies in price, but the registered model is a synthetic-platform model that never learned a price response."""
    bid, goal = ready
    monkeypatch.setattr(dts, "price_sensitivity_check", lambda history: OK)
    d = client.post(f"/api/v1/businesses/{bid}/decisions/analyze", json={"goal_id": goal}).json()
    assert "Price options were withheld" in d["reasoning"] and "no forecasting model checked against your own price changes" in d["reasoning"]
    assert all(not a["strategy_name"].startswith("Price ") for a in d["alternatives"])
    assert not d["selected_strategy_name"].startswith("Price ")


def test_identified_price_variation_lets_price_options_be_ranked_and_labels_them_association_only(client, db_session, ready, monkeypatch, eligible_model):
    bid, goal = ready
    monkeypatch.setattr(dts, "price_sensitivity_check", lambda history: OK)
    d = client.post(f"/api/v1/businesses/{bid}/decisions/analyze", json={"goal_id": goal}).json()
    assert "Price options were withheld" not in d["reasoning"]
    names = [d["selected_strategy_name"]] + [a["strategy_name"] for a in d["alternatives"]]
    assert any(n.startswith("Price ") for n in names)
    actions, row = _actions(db_session, d["id"])
    if any(a["type"] == "price_change" for a in actions):
        assert row.uncertainty_json["price_response"]["status"] == "association_only"


def test_the_research_path_is_unchanged_and_only_annotates(client, db_session, ready, monkeypatch):
    """Default PipelineOptions (frozen research evaluations) must not withhold anything: same candidates, same ranking."""
    bid, goal = ready
    monkeypatch.setattr(dts, "price_sensitivity_check", lambda history: FLAT)
    res = decision_service.analyze_goal(db_session, bid, goal)
    assert decision_service.PipelineOptions().label() == "full"
    assert not any("withheld" in s for s in res.skipped_strategies)
    assert any(a["strategy_name"].startswith("Price ") for a in res.alternatives) or res.selected_strategy_name.startswith("Price ")


def test_the_gate_never_changes_scores_of_the_options_that_remain(client, db_session, ready, monkeypatch):
    bid, goal = ready
    monkeypatch.setattr(dts, "price_sensitivity_check", lambda history: FLAT)
    gated = client.post(f"/api/v1/businesses/{bid}/decisions/analyze", json={"goal_id": goal}).json()
    ungated = decision_service.analyze_goal(db_session, bid, goal)
    ungated_scores = {a["strategy_name"]: a["strategy_score"] for a in ungated.alternatives}
    ungated_scores[ungated.selected_strategy_name] = ungated.selected_strategy_score
    remaining = [(gated["selected_strategy_name"], gated["selected_strategy_score"]),
                 *[(a["strategy_name"], a["strategy_score"]) for a in gated["alternatives"]]]
    assert remaining
    for name, score in remaining:
        assert score == pytest.approx(ungated_scores[name])
