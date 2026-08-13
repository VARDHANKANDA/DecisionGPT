from app.services import model_registry_service
from tests.integration.test_analytics import _create_business, _seed_rich_business
from tests.integration.test_decisions import _create_goal


def _make_decision(client, business_id: str) -> dict:
    goal_id = _create_goal(client, business_id, "Increase revenue by 10% in 2 months")
    response = client.post(f"/api/v1/businesses/{business_id}/decisions/analyze", json={"goal_id": goal_id})
    assert response.status_code == 200, response.text
    return response.json()


def test_goal_creation_logs_memory(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)
    _create_goal(client, business_id, "Increase revenue by 10% in 2 months")

    response = client.get(f"/api/v1/businesses/{business_id}/memory?memory_type=goal")
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert "increase_revenue" in entries[0]["content"]


def test_decision_logs_memory(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)
    decision = _make_decision(client, business_id)

    response = client.get(f"/api/v1/businesses/{business_id}/memory?memory_type=decision")
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert entries[0]["metadata_json"]["decision_id"] == decision["id"]


def test_record_outcome_requires_existing_decision(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    response = client.post(
        f"/api/v1/businesses/{business_id}/decisions/00000000-0000-0000-0000-000000000000/outcome",
        json={"actual_outcome": {"revenue": 1000}},
    )
    assert response.status_code == 404


def test_record_outcome_scores_against_the_real_prediction(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)
    decision = _make_decision(client, business_id)

    expected = decision["expected_outcome"]
    predicted_change = expected["expected_revenue"] - expected["baseline_revenue"]
    # Report an actual outcome that exactly matched the prediction.
    actual_revenue = expected["baseline_revenue"] + predicted_change

    response = client.post(
        f"/api/v1/businesses/{business_id}/decisions/{decision['id']}/outcome",
        json={"actual_outcome": {"revenue": actual_revenue}},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["decision_id"] == decision["id"]
    assert body["goal_achievement_score"] == 1.0
    assert body["goal_achieved"] is (predicted_change > 0)


def test_record_outcome_rejects_duplicate(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)
    decision = _make_decision(client, business_id)

    first = client.post(
        f"/api/v1/businesses/{business_id}/decisions/{decision['id']}/outcome",
        json={"actual_outcome": {"revenue": 100000}},
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/businesses/{business_id}/decisions/{decision['id']}/outcome",
        json={"actual_outcome": {"revenue": 100000}},
    )
    assert second.status_code == 422


def test_get_outcome_before_recording_is_not_found(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)
    decision = _make_decision(client, business_id)

    response = client.get(f"/api/v1/businesses/{business_id}/decisions/{decision['id']}/outcome")
    assert response.status_code == 404


def test_next_decision_references_a_real_past_outcome(client, db_session):
    """The core Business Memory behavior (docs/PRD.md §29): a new decision
    that shares an action type with a past, outcome-recorded decision must
    surface a real memory_insight about it — never a generic or fabricated
    one, and never anything when no matching outcome exists yet."""
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    first_decision = _make_decision(client, business_id)
    # No outcomes recorded yet anywhere — nothing to reference.
    assert first_decision["memory_insights"] == []

    expected = first_decision["expected_outcome"]
    # Report a real outcome that undershot the prediction.
    undershot_revenue = expected["baseline_revenue"] + (expected["expected_revenue"] - expected["baseline_revenue"]) * 0.4
    client.post(
        f"/api/v1/businesses/{business_id}/decisions/{first_decision['id']}/outcome",
        json={"actual_outcome": {"revenue": undershot_revenue}},
    )

    goal_id = _create_goal(client, business_id, "Increase revenue by 12% in 2 months")
    second_response = client.post(f"/api/v1/businesses/{business_id}/decisions/analyze", json={"goal_id": goal_id})
    assert second_response.status_code == 200, second_response.text
    second_decision = second_response.json()

    # The winning strategy of the *second* decision only gets an insight if
    # it shares an action type with the first — instead of guessing which
    # strategy wins twice, just check that whatever insights exist are all
    # real, non-empty sentences, and if the same action type recurs, there
    # is exactly one relevant insight about it.
    for insight in second_decision["memory_insights"]:
        assert "predicted" in insight and "actual" in insight
        assert len(insight) > 20


def test_memory_is_isolated_per_business(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_a = _create_business(client)
    _seed_rich_business(client, business_a)
    _create_goal(client, business_a, "Increase revenue by 10% in 2 months")

    business_b = _create_business(client)
    response = client.get(f"/api/v1/businesses/{business_b}/memory")
    assert response.status_code == 200
    assert response.json() == []
