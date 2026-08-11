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

    # Up to 5 alternatives (6 candidates - 1 selected), each independently scored.
    assert 0 < len(body["alternatives"]) <= 5
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

    # This business never uploaded marketing data, so baseline marketing
    # spend is ₹0 — a percentage change of ₹0 is a no-op either direction
    # (docs/DIGITAL_TWIN_SPECIFICATION.md behavior tested in Phase 10), so
    # these two must simulate identically.
    marketing_up = next(a for a in body["alternatives"] if a["strategy_name"] == "Marketing +10%")
    marketing_down = next(a for a in body["alternatives"] if a["strategy_name"] == "Marketing -10%")
    assert marketing_up["strategy_score"] == marketing_down["strategy_score"]

    # Price is genuinely non-zero and a real model input — a +5% and -5%
    # price scenario must NOT collapse to the same prediction.
    price_scores = {name: s["strategy_score"] for name, s in by_name.items() if name in {"Price +5%", "Price -5%"}}
    assert len(set(price_scores.values())) == 2

    # Not every candidate collapses onto the same score — genuine spread exists.
    distinct_scores = {s["strategy_score"] for s in all_strategies if s["strategy_score"] is not None}
    assert len(distinct_scores) >= 3
