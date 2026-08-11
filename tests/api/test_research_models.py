from app.core.config import get_settings


def test_research_models_requires_token(client):
    response = client.get("/api/v1/research/models")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "BUSINESS_ACCESS_DENIED"


def test_research_models_sync_and_list(client):
    token = get_settings().research_console_token
    headers = {"X-Research-Token": token}

    sync_response = client.post("/api/v1/research/models/sync", headers=headers)
    assert sync_response.status_code == 200
    assert len(sync_response.json()) >= 6

    list_response = client.get("/api/v1/research/models", headers=headers)
    assert list_response.status_code == 200
    names = {m["model_name"] for m in list_response.json()}
    assert "sales_forecast_xgboost" in names
