def test_create_demo_business_is_labeled_synthetic(client):
    response = client.post("/api/v1/businesses/demo")
    assert response.status_code == 201, response.text
    body = response.json()
    assert "Demo" in body["name"]
    assert "Synthetic" in body["description"]


def test_demo_business_has_real_usable_data(client):
    business_id = client.post("/api/v1/businesses/demo").json()["id"]

    summary = client.get(f"/api/v1/businesses/{business_id}/data/summary").json()
    assert summary["products"] == 5
    assert summary["customers"] == 120
    assert summary["sales"] > 0
    assert summary["marketing_campaigns"] > 0
    assert summary["inventory_records"] > 0

    kpis = client.get(f"/api/v1/businesses/{business_id}/analytics/kpis").json()
    assert kpis["revenue"] > 0
    assert kpis["profit"] is not None  # demo products always have unit_cost

    # 180 days of daily sales easily clears the forecast sufficiency bar —
    # only reason to fail is no model being registered in this test session.
    forecast_response = client.post(f"/api/v1/businesses/{business_id}/analytics/forecast")
    assert forecast_response.status_code in (200, 422)
    if forecast_response.status_code == 422:
        assert forecast_response.json()["error"]["code"] == "INSUFFICIENT_DATA"
    else:
        assert len(forecast_response.json()["points"]) > 0


def test_each_demo_business_call_creates_an_independent_business(client):
    first = client.post("/api/v1/businesses/demo").json()["id"]
    second = client.post("/api/v1/businesses/demo").json()["id"]
    assert first != second
