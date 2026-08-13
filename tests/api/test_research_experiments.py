from app.core.config import get_settings
from app.services import model_registry_service


def _headers():
    return {"X-Research-Token": get_settings().research_console_token}


def test_experiments_requires_token(client):
    response = client.post("/api/v1/research/experiments/run", json={"experiment_type": "causal"})
    assert response.status_code == 403


def test_unsupported_experiment_type_is_rejected(client):
    response = client.post(
        "/api/v1/research/experiments/run", json={"experiment_type": "nonsense"}, headers=_headers()
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_causal_experiment_run_is_recorded_and_listed(client):
    response = client.post(
        "/api/v1/research/experiments/run",
        json={"experiment_type": "causal", "configuration": {"seed": 5}},
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["experiment_type"] == "causal"
    assert body["random_seed"] == 5
    assert body["dataset_version"] == "synthetic_causal_validation"
    assert "precision" in body["metrics_json"]

    get_response = client.get(f"/api/v1/research/experiments/{body['id']}", headers=_headers())
    assert get_response.status_code == 200
    assert get_response.json()["id"] == body["id"]

    list_response = client.get("/api/v1/research/experiments?experiment_type=causal", headers=_headers())
    assert list_response.status_code == 200
    assert any(r["id"] == body["id"] for r in list_response.json())


def test_ablation_experiment_run(client):
    response = client.post(
        "/api/v1/research/experiments/run",
        json={"experiment_type": "ablation", "configuration": {"seed": 9}},
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    comparisons = response.json()["metrics_json"]["comparisons"]
    assert len(comparisons) == 5


def test_decision_architecture_experiment_run(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    response = client.post(
        "/api/v1/research/experiments/run",
        json={"experiment_type": "decision_architecture", "configuration": {"seed": 11}},
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    results = response.json()["metrics_json"]["results"]
    assert [r["architecture"] for r in results] == ["A", "B", "C", "D"]


def test_multi_agent_experiment_run(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    response = client.post(
        "/api/v1/research/experiments/run",
        json={"experiment_type": "multi_agent", "configuration": {"seed": 12}},
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    metrics = response.json()["metrics_json"]
    assert "single_agent" in metrics and "multi_agent" in metrics


def test_digital_twin_evaluation_experiment_with_no_real_outcomes_is_honest(client):
    response = client.post(
        "/api/v1/research/experiments/run",
        json={"experiment_type": "digital_twin"},
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    metrics = response.json()["metrics_json"]
    assert metrics["sample_size"] == 0
    assert metrics["mae"] is None


def test_forecasting_experiment_run_retrains_and_registers_real_models(client):
    response = client.post(
        "/api/v1/research/experiments/run",
        json={"experiment_type": "forecasting", "configuration": {"seed": 42}},
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dataset_version"] == "platform-forecasting-v1"
    results = body["metrics_json"]
    assert set(results.keys()) == {"naive", "linear", "xgboost"}
    for metrics in results.values():
        assert metrics["mae"] > 0
