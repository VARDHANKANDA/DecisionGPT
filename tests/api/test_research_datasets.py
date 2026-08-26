from app.core.config import get_settings


def _headers():
    return {"X-Research-Token": get_settings().research_console_token}


def test_datasets_requires_token(client):
    response = client.get("/api/v1/research/datasets")
    assert response.status_code == 403


def test_datasets_lists_real_platform_metadata(client):
    response = client.get("/api/v1/research/datasets", headers=_headers())
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"platform", "uploaded"}
    datasets = body["platform"]
    domains = {d["domain"] for d in datasets}
    assert "forecasting" in domains
    assert "churn" in domains

    forecasting = next(d for d in datasets if d["domain"] == "forecasting")
    assert forecasting["row_count"] > 0
    assert forecasting["evidence_level"] == "SYNTHETIC"
    assert len(forecasting["limitations"]) > 0
    # Nothing uploaded yet in a fresh test DB.
    assert body["uploaded"] == []
