import io
from datetime import date, timedelta

import pandas as pd


def _create_business(client) -> str:
    response = client.post(
        "/api/v1/businesses",
        json={"name": "Goals Co", "industry": "apparel", "business_type": "D2C", "business_size": "small"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _upload_csv(client, business_id, data_type, df):
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    response = client.post(
        f"/api/v1/businesses/{business_id}/data/upload?data_type={data_type}",
        files={"file": (f"{data_type}.csv", buf.getvalue().encode(), "text/csv")},
    )
    assert response.status_code == 200
    return response.json()


def test_goal_rejected_when_kpi_unavailable(client):
    business_id = _create_business(client)
    response = client.post(
        f"/api/v1/businesses/{business_id}/goals", json={"text": "Increase profit by 15% in 3 months."}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_goal_created_when_kpi_available(client):
    business_id = _create_business(client)
    today = date.today()
    sales = pd.DataFrame(
        [
            {
                "Order Date": (today - timedelta(days=i)).isoformat(),
                "Quantity": 2,
                "Unit Price": 500,
                "Total Amount": 1000,
            }
            for i in range(10)
        ]
    )
    _upload_csv(client, business_id, "sales", sales)

    response = client.post(
        f"/api/v1/businesses/{business_id}/goals", json={"text": "Increase revenue by 20% in 2 months."}
    )
    assert response.status_code == 201, response.text
    goal = response.json()
    assert goal["objective"] == "increase_revenue"
    assert goal["target_value"] == 20.0
    assert goal["primary_kpi"] == "revenue"
    assert goal["time_horizon"] == 2
    assert goal["status"] == "active"

    list_response = client.get(f"/api/v1/businesses/{business_id}/goals")
    assert len(list_response.json()) == 1

    get_response = client.get(f"/api/v1/businesses/{business_id}/goals/{goal['id']}")
    assert get_response.status_code == 200


def test_goal_rejected_when_unparseable(client):
    business_id = _create_business(client)
    response = client.post(f"/api/v1/businesses/{business_id}/goals", json={"text": "Do something good."})
    assert response.status_code == 422
