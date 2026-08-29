from datetime import date, timedelta

import pandas as pd

from app.services import model_registry_service
from tests.integration.test_analytics import _create_business, _seed_rich_business, _upload_csv


def _create_goal(client, business_id: str, text: str) -> str:
    response = client.post(f"/api/v1/businesses/{business_id}/goals", json={"text": text})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_goal_creation_is_gated_before_a_decision_can_even_be_requested(client, db_session):
    """Goal creation itself requires real revenue on file (goal_service),
    so there's no way to reach decisions/analyze with a goal on a business
    that has no data — this documents/locks in that upstream gate."""
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    response = client.post(f"/api/v1/businesses/{business_id}/goals", json={"text": "Increase revenue by 10%"})
    assert response.status_code == 422


def test_analyze_nonexistent_goal_returns_not_found(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = client.post(
        f"/api/v1/businesses/{business_id}/decisions/analyze",
        json={"goal_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


def test_analyze_produces_a_reasoned_decision(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)
    goal_id = _create_goal(client, business_id, "Increase revenue by 10% in 2 months")

    response = client.post(f"/api/v1/businesses/{business_id}/decisions/analyze", json={"goal_id": goal_id})
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["business_id"] == business_id
    assert body["goal_id"] == goal_id
    assert body["risk_level"] in {"low", "medium", "high"}
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["selected_strategy_name"]
    assert body["reasoning"]

    # Three agents, each with a real narrative built from their own
    # structured evaluation (not a placeholder).
    assert set(body["agent_reviews"].keys()) == {"business_analyst", "financial_advisor", "risk_manager"}
    for narrative in body["agent_reviews"].values():
        assert len(narrative) > 0

    # Alternatives = every generated candidate except the selected one, each
    # independently scored. The revenue goal-template set is 8 candidates after
    # the candidate-space correction (adds the supported Price +5% / +10% levers
    # so Full DecisionGPT sees the same strategy space the Digital Twin sweeps —
    # docs/CANDIDATE_SPACE_CORRECTION_REPORT.md), so up to 7 alternatives.
    assert 0 < len(body["alternatives"]) <= 7
    alt_names = {a["strategy_name"] for a in body["alternatives"]} | {body["selected_strategy_name"]}
    assert "Price +5%" in alt_names  # supported price-increase lever is now generated
    scores = [body["alternatives"][i]["strategy_score"] for i in range(len(body["alternatives"]))]
    assert scores == sorted(scores, reverse=True)  # ranked, best alternative first

    assert "expected_units_sold" in body["expected_outcome"]
    assert "assumptions" in body["expected_outcome"]


def test_analyze_persists_and_appears_in_history(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)
    goal_id = _create_goal(client, business_id, "Increase revenue by 10% in 2 months")

    analyze_response = client.post(f"/api/v1/businesses/{business_id}/decisions/analyze", json={"goal_id": goal_id})
    decision_id = analyze_response.json()["id"]

    list_response = client.get(f"/api/v1/businesses/{business_id}/decisions")
    assert list_response.status_code == 200
    assert any(d["id"] == decision_id for d in list_response.json())

    get_response = client.get(f"/api/v1/businesses/{business_id}/decisions/{decision_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == decision_id
    assert get_response.json()["risk_level"] == analyze_response.json()["risk_level"]


def test_decision_is_isolated_per_business(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_a = _create_business(client)
    _seed_rich_business(client, business_a)
    goal_id = _create_goal(client, business_a, "Increase revenue by 10% in 2 months")
    decision_id = client.post(
        f"/api/v1/businesses/{business_a}/decisions/analyze", json={"goal_id": goal_id}
    ).json()["id"]

    business_b = _create_business(client)
    response = client.get(f"/api/v1/businesses/{business_b}/decisions/{decision_id}")
    assert response.status_code == 404


def test_candidate_strategies_are_genuinely_differentiated_not_arbitrary(client, db_session):
    """Confirm the optimizer's ranking reflects real, different simulated
    outcomes per strategy rather than a fixed/arbitrary order — using two
    provable invariants rather than guessing which strategy "should" win
    (that depends on the registered model's actual learned response, which
    this system deliberately never hardcodes an assumption about)."""
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)

    products = pd.DataFrame([{"Product ID": "P000", "Product Name": "Item", "Selling Price": 500}])
    _upload_csv(client, business_id, "products", products)

    today = date.today()
    start = today - timedelta(days=90)
    sales_rows = []
    for day_offset in range(90):
        sale_date = start + timedelta(days=day_offset)
        high_price_day = day_offset % 4 == 0
        price = 800 if high_price_day else 400
        quantity = 1 if high_price_day else 5
        sales_rows.append(
            {
                "Order Date": sale_date.isoformat(),
                "Customer ID": f"C{day_offset % 20:03d}",
                "Product ID": "P000",
                "Quantity": quantity,
                "Unit Price": price,
                "Discount": 0,
            }
        )
    _upload_csv(client, business_id, "sales", pd.DataFrame(sales_rows))

    goal_id = _create_goal(client, business_id, "Increase revenue by 10% in 2 months")
    response = client.post(f"/api/v1/businesses/{business_id}/decisions/analyze", json={"goal_id": goal_id})
    assert response.status_code == 200, response.text
    body = response.json()

    all_strategies = [
        {"strategy_name": body["selected_strategy_name"], "strategy_score": body["selected_strategy_score"]},
        *body["alternatives"],
    ]
    by_name = {s["strategy_name"]: s for s in all_strategies}

    # Goal-aware generation: this business never uploaded marketing data, so
    # marketing-based candidates must be excluded rather than simulated
    # against a ₹0 baseline (strategy_generation_service).
    assert not any("Marketing" in name for name in by_name), by_name
    assert body["strategy_generation"]["objective"] == "increase_revenue"
    assert any("marketing" in e.lower() for e in body["strategy_generation"]["excluded"])

    # The surviving candidates are all price moves at different magnitudes —
    # price is a real model input, so different magnitudes must NOT collapse
    # onto the same simulated score.
    price_scores = {name: s["strategy_score"] for name, s in by_name.items() if name.startswith("Price ")}
    assert len(price_scores) >= 2
    assert len(set(price_scores.values())) == len(price_scores)

    # Genuine spread exists across the candidate set.
    distinct_scores = {s["strategy_score"] for s in all_strategies if s["strategy_score"] is not None}
    assert len(distinct_scores) >= 2


def test_explain_decision_returns_shap_local_and_global_explanations(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)
    goal_id = _create_goal(client, business_id, "Increase revenue by 10% in 2 months")

    decision = client.post(
        f"/api/v1/businesses/{business_id}/decisions/analyze", json={"goal_id": goal_id}
    ).json()

    response = client.get(f"/api/v1/businesses/{business_id}/decisions/{decision['id']}/explanation")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["decision_id"] == decision["id"]

    explanation = body["explanation"]
    # _seed_rich_business's registered best model is expected to be XGBoost
    # (lowest MAE) in this environment's trained registry — a tree model,
    # so SHAP must actually be available, not gracefully degraded.
    assert explanation["shap_available"] is True
    assert explanation["model_name"] == decision["expected_outcome"]["model_name"]
    assert len(explanation["local_factors"]) > 0
    for factor in explanation["local_factors"]:
        assert factor["direction"] in {"increased", "decreased", "unchanged"}
        assert "label" in factor and factor["label"]

    assert len(explanation["global_importance"]) == 10  # all FEATURE_COLUMNS
    global_by_feature = {g["feature"]: g["contribution"] for g in explanation["global_importance"]}
    assert all(v >= 0 for v in global_by_feature.values())  # mean |SHAP|, never negative
    # Ranked descending.
    values = [g["contribution"] for g in explanation["global_importance"]]
    assert values == sorted(values, reverse=True)

    assert body["reasoning"] == decision["reasoning"]
    assert set(body["agent_reviews"].keys()) == {"business_analyst", "financial_advisor", "risk_manager"}
    assert body["counterfactual"]["expected_revenue"] == decision["expected_outcome"]["expected_revenue"]
    assert body["uncertainty"]["risk_level"] == decision["risk_level"]
    assert len(body["assumptions"]) > 0


def test_explain_decision_is_isolated_per_business(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_a = _create_business(client)
    _seed_rich_business(client, business_a)
    goal_id = _create_goal(client, business_a, "Increase revenue by 10% in 2 months")
    decision_id = client.post(
        f"/api/v1/businesses/{business_a}/decisions/analyze", json={"goal_id": goal_id}
    ).json()["id"]

    business_b = _create_business(client)
    response = client.get(f"/api/v1/businesses/{business_b}/decisions/{decision_id}/explanation")
    assert response.status_code == 404


def test_explain_nonexistent_decision_returns_not_found(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    response = client.get(
        f"/api/v1/businesses/{business_id}/decisions/00000000-0000-0000-0000-000000000000/explanation"
    )
    assert response.status_code == 404
