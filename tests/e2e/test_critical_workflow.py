"""Critical end-to-end acceptance test — docs/TESTING_SPECIFICATION.md §4.

Chains the entire business workflow through the real HTTP API, exactly as
a real user session would: create business -> upload data -> validate ->
KPIs -> goal -> forecast -> causal graph -> >=3 simulated strategies ->
agents -> recommendation -> explanation -> save decision -> record outcome.
Every step asserts on real response data — nothing here is mocked.
"""
from app.services import model_registry_service
from tests.integration.test_analytics import _create_business, _seed_rich_business


def test_critical_end_to_end_workflow(client, db_session):
    # Models must be registered before any forecast/simulation/decision step.
    model_registry_service.sync_from_file_registry(db_session)

    # 1. Create business.
    business_id = _create_business(client)
    assert business_id

    # 2. Upload sample data (products, customers, sales, marketing — real CSVs).
    _seed_rich_business(client, business_id)

    # 3. Validate data — the upload itself validated it; confirm it landed.
    summary = client.get(f"/api/v1/businesses/{business_id}/data/summary")
    assert summary.status_code == 200
    assert summary.json()["sales"] == 180

    # 4. Generate KPIs.
    kpis = client.get(f"/api/v1/businesses/{business_id}/analytics/kpis")
    assert kpis.status_code == 200
    assert kpis.json()["revenue"] > 0

    # 5. Create goal.
    goal_response = client.post(
        f"/api/v1/businesses/{business_id}/goals", json={"text": "Increase revenue by 10% in 2 months"}
    )
    assert goal_response.status_code == 201
    goal_id = goal_response.json()["id"]

    # 6. Forecast.
    forecast = client.post(f"/api/v1/businesses/{business_id}/analytics/forecast?horizon_days=7")
    assert forecast.status_code == 200
    assert len(forecast.json()["points"]) == 7

    # 7. Build (causal) graph.
    graph = client.post(f"/api/v1/businesses/{business_id}/causal-graph/build")
    assert graph.status_code == 200
    assert len(graph.json()["edges"]) == 13
    assert all(e["evidence_type"] != "causally_validated" for e in graph.json()["edges"])

    # 8. Simulate at least three strategies (directly, via the Digital Twin endpoint).
    simulated = []
    for actions in (
        [{"type": "marketing_change", "value": 10}],
        [{"type": "marketing_change", "value": -10}],
        [{"type": "price_change", "value": 5}],
    ):
        sim = client.post(
            f"/api/v1/businesses/{business_id}/digital-twin/simulate", json={"actions": actions}
        )
        assert sim.status_code == 200, sim.text
        simulated.append(sim.json())
    assert len(simulated) >= 3

    # 9. Run agents + 10. Generate recommendation — one call, the real
    # multi-agent pipeline (candidate grid -> Digital Twin -> 3 agents -> optimizer).
    decision_response = client.post(
        f"/api/v1/businesses/{business_id}/decisions/analyze", json={"goal_id": goal_id}
    )
    assert decision_response.status_code == 200, decision_response.text
    decision = decision_response.json()
    assert set(decision["agent_reviews"].keys()) == {"business_analyst", "financial_advisor", "risk_manager"}
    assert decision["selected_strategy_name"]
    assert decision["risk_level"] in {"low", "medium", "high"}

    # 11. Display explanation.
    explanation_response = client.get(
        f"/api/v1/businesses/{business_id}/decisions/{decision['id']}/explanation"
    )
    assert explanation_response.status_code == 200
    explanation = explanation_response.json()
    assert explanation["reasoning"] == decision["reasoning"]

    # 12. Save decision — already persisted by step 9/10; confirm it's retrievable.
    saved = client.get(f"/api/v1/businesses/{business_id}/decisions/{decision['id']}")
    assert saved.status_code == 200
    assert saved.json()["id"] == decision["id"]

    # 13. Record outcome.
    outcome_response = client.post(
        f"/api/v1/businesses/{business_id}/decisions/{decision['id']}/outcome",
        json={"actual_outcome": {"revenue": decision["expected_outcome"]["expected_revenue"]}},
    )
    assert outcome_response.status_code == 200, outcome_response.text
    assert outcome_response.json()["decision_id"] == decision["id"]

    # Business Memory should now hold a full trail: goal, decision, outcome.
    memory = client.get(f"/api/v1/businesses/{business_id}/memory")
    assert memory.status_code == 200
    memory_types = {m["memory_type"] for m in memory.json()}
    assert memory_types == {"goal", "decision", "outcome"}


def test_business_a_cannot_access_business_b(client, db_session):
    """docs/TESTING_SPECIFICATION.md §2 Security — the one test every other
    per-feature isolation test in this suite is a specific instance of."""
    model_registry_service.sync_from_file_registry(db_session)

    business_a = _create_business(client)
    _seed_rich_business(client, business_a)
    goal_id = client.post(
        f"/api/v1/businesses/{business_a}/goals", json={"text": "Increase revenue by 10% in 2 months"}
    ).json()["id"]
    decision_id = client.post(
        f"/api/v1/businesses/{business_a}/decisions/analyze", json={"goal_id": goal_id}
    ).json()["id"]

    business_b = _create_business(client)

    # Every read of business A's resources through business B's ID must 404,
    # never leak data.
    assert client.get(f"/api/v1/businesses/{business_b}/goals/{goal_id}").status_code == 404
    assert client.get(f"/api/v1/businesses/{business_b}/decisions/{decision_id}").status_code == 404
    assert (
        client.get(f"/api/v1/businesses/{business_b}/decisions/{decision_id}/explanation").status_code
        == 404
    )
    assert client.get(f"/api/v1/businesses/{business_b}/decisions/{decision_id}/outcome").status_code == 404
    assert client.get(f"/api/v1/businesses/{business_b}/memory").json() == []
    assert client.get(f"/api/v1/businesses/{business_b}/data/summary").json() == {
        "products": 0, "customers": 0, "sales": 0, "marketing_campaigns": 0, "inventory_records": 0,
        "finance_records": 0, "business_profile_set": False,
    }
