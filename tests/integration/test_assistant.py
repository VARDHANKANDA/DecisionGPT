from app.services import model_registry_service
from tests.integration.test_analytics import _create_business, _seed_rich_business
from tests.integration.test_decisions import _create_goal


def _ask(client, business_id: str, message: str):
    return client.post(f"/api/v1/businesses/{business_id}/chat", json={"message": message})


def test_unrecognized_question_is_honestly_refused(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = _ask(client, business_id, "What's the meaning of life?")
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "unrecognized"
    assert body["sufficient_evidence"] is False
    assert "don't have enough data" in body["answer"]


def test_why_revenue_fell_uses_real_period_comparison(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = _ask(client, business_id, "Why did my revenue fall?")
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "why_kpi_fell"
    assert any("Revenue" in s for s in body["sources"])
    # The answer must actually be about revenue moving, not a generic reply.
    assert "%" in body["answer"]


def test_price_advice_runs_a_real_simulation(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = _ask(client, business_id, "Should I increase my price?")
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "price_change_advice"
    assert body["sufficient_evidence"] is True
    assert any("simulation" in s.lower() for s in body["sources"])


def test_price_advice_without_enough_history_is_honest(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)

    response = _ask(client, business_id, "Should I raise prices?")
    assert response.status_code == 200
    body = response.json()
    assert body["sufficient_evidence"] is False
    assert "don't have enough data" in body["answer"]


def test_marketing_advice_runs_a_real_simulation(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = _ask(client, business_id, "What if I increase ads spend?")
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "marketing_change_advice"
    assert body["sufficient_evidence"] is True


def test_why_recommend_without_a_decision_yet_is_honest(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = _ask(client, business_id, "Why did you recommend this?")
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "why_recommend"
    assert body["sufficient_evidence"] is False


def test_why_recommend_references_the_real_latest_decision(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)
    goal_id = _create_goal(client, business_id, "Increase revenue by 10% in 2 months")
    decision = client.post(
        f"/api/v1/businesses/{business_id}/decisions/analyze", json={"goal_id": goal_id}
    ).json()

    response = _ask(client, business_id, "Why did you recommend this strategy?")
    assert response.status_code == 200
    body = response.json()
    assert body["sufficient_evidence"] is True
    assert body["answer"] == decision["reasoning"]
    assert decision["id"] in body["sources"][0]


def test_what_focus_returns_a_real_grounded_answer(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = _ask(client, business_id, "What should I focus on?")
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "what_focus"
    assert len(body["answer"]) > 0


def test_chat_logs_memory(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)
    _ask(client, business_id, "Why did my revenue fall?")

    response = client.get(f"/api/v1/businesses/{business_id}/memory?memory_type=chat")
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert "Why did my revenue fall?" in entries[0]["content"]


def test_chat_is_isolated_per_business(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_a = _create_business(client)
    _seed_rich_business(client, business_a)
    _ask(client, business_a, "Why did my revenue fall?")

    business_b = _create_business(client)
    response = client.get(f"/api/v1/businesses/{business_b}/memory?memory_type=chat")
    assert response.status_code == 200
    assert response.json() == []
