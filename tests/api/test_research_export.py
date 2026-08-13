import json

from app.core.config import get_settings
from app.services import model_registry_service


def _headers():
    return {"X-Research-Token": get_settings().research_console_token}


def test_export_requires_token(client):
    response = client.post("/api/v1/research/export", json={"table": "forecasting_performance", "format": "csv"})
    assert response.status_code == 403


def test_export_unknown_table_rejected(client):
    response = client.post(
        "/api/v1/research/export", json={"table": "not_a_real_table", "format": "csv"}, headers=_headers()
    )
    assert response.status_code == 422


def test_export_forecasting_performance_as_csv(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    response = client.post(
        "/api/v1/research/export",
        json={"table": "forecasting_performance", "format": "csv"},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert "sales_forecast_xgboost" in response.text
    assert response.text.splitlines()[0] == "Model,Version,MAE,RMSE,MAPE,Dataset version"


def test_export_forecasting_performance_as_all_formats(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    for fmt in ("csv", "json", "markdown", "latex"):
        response = client.post(
            "/api/v1/research/export",
            json={"table": "forecasting_performance", "format": fmt},
            headers=_headers(),
        )
        assert response.status_code == 200, (fmt, response.text)
        assert len(response.text) > 0

    json_response = client.post(
        "/api/v1/research/export",
        json={"table": "forecasting_performance", "format": "json"},
        headers=_headers(),
    )
    parsed = json.loads(json_response.text)
    assert isinstance(parsed, list)
    assert parsed[0]["Model"].startswith("sales_forecast")


def test_export_ablation_table_references_a_real_experiment(client):
    run_response = client.post(
        "/api/v1/research/experiments/run",
        json={"experiment_type": "ablation", "configuration": {"seed": 3}},
        headers=_headers(),
    )
    experiment_id = run_response.json()["id"]

    export_response = client.post(
        "/api/v1/research/export",
        json={"table": "ablation", "format": "markdown", "experiment_id": experiment_id},
        headers=_headers(),
    )
    assert export_response.status_code == 200
    assert "Digital Twin" in export_response.text
    assert "Component removed" in export_response.text


def test_export_ablation_table_without_experiment_id_is_empty(client):
    response = client.post(
        "/api/v1/research/export", json={"table": "ablation", "format": "csv"}, headers=_headers()
    )
    assert response.status_code == 200
    # No experiment_id was supplied, so there's nothing to reference — empty, not fabricated rows.
    assert response.text.strip() == ""
