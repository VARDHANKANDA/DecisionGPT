from app.services import model_registry_service
from tests.integration.test_analytics import _create_business, _seed_rich_business, _upload_csv
import pandas as pd
from datetime import date, timedelta


def test_simulate_requires_sufficient_history(client):
    business_id = _create_business(client)
    response = client.post(
        f"/api/v1/businesses/{business_id}/digital-twin/simulate",
        json={"actions": [{"type": "marketing_change", "value": 10}]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSUFFICIENT_DATA"


def test_simulate_requires_registered_model(client, db_session):
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = client.post(
        f"/api/v1/businesses/{business_id}/digital-twin/simulate",
        json={"actions": [{"type": "marketing_change", "value": 10}]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSUFFICIENT_DATA"


def test_simulate_marketing_change_with_registered_model(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = client.post(
        f"/api/v1/businesses/{business_id}/digital-twin/simulate",
        json={"actions": [{"type": "marketing_change", "value": 10}], "horizon_days": 7},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    output = body["output"]
    assert output["model_name"] in {"sales_forecast_naive", "sales_forecast_linear", "sales_forecast_xgboost"}
    assert output["expected_units_sold"] >= 0
    assert output["baseline_units_sold"] >= 0
    assert output["revenue_lower_bound"] <= output["expected_revenue"] <= output["revenue_upper_bound"]
    assert output["risk_level"] in {"LOW", "MODERATE", "HIGH"}
    assert 0.0 <= output["risk_score"] <= 1.0
    assert len(output["assumptions"]) > 0
    # marketing_change alone shouldn't trigger an inventory cap
    assert output["inventory_constrained"] is False
    assert body["actions"] == [{"type": "marketing_change", "value": 10}]
    assert body["input_state"]["revenue"] > 0
    # _seed_rich_business uploads real marketing spend, so the requested
    # change should be applied, not silently no-opped.
    assert not any("₹0" in a for a in output["assumptions"])


def test_simulate_marketing_change_with_zero_spend_on_file_is_flagged(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)

    today = date.today()
    start = today - timedelta(days=60)
    sales_rows = [
        {
            "Order Date": (start + timedelta(days=i)).isoformat(),
            "Customer ID": f"C{i % 20:03d}",
            "Product ID": f"P{i % 5:03d}",
            "Quantity": 2,
            "Unit Price": 999,
            "Discount": 0,
        }
        for i in range(60)
    ]
    _upload_csv(client, business_id, "sales", pd.DataFrame(sales_rows))

    response = client.post(
        f"/api/v1/businesses/{business_id}/digital-twin/simulate",
        json={"actions": [{"type": "marketing_change", "value": 10}], "horizon_days": 7},
    )
    assert response.status_code == 200, response.text
    output = response.json()["output"]
    # No marketing data was ever uploaded -> baseline spend is 0 -> a percent
    # change is a no-op; this must be surfaced, not silently returned as if
    # the model found "no effect".
    assert output["expected_units_sold"] == output["baseline_units_sold"]
    assert any("₹0" in a for a in output["assumptions"])


def test_simulate_persists_and_is_retrievable(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    post_response = client.post(
        f"/api/v1/businesses/{business_id}/digital-twin/simulate",
        json={"actions": [{"type": "price_change", "value": 5}]},
    )
    assert post_response.status_code == 200, post_response.text
    simulation_id = post_response.json()["id"]

    get_response = client.get(f"/api/v1/businesses/{business_id}/digital-twin/simulations/{simulation_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == simulation_id
    assert get_response.json()["output"] == post_response.json()["output"]


def test_simulate_rejects_unsupported_action_type(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = client.post(
        f"/api/v1/businesses/{business_id}/digital-twin/simulate",
        json={"actions": [{"type": "hire_more_staff", "value": 10}]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_simulate_rejects_duplicate_action_types(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = client.post(
        f"/api/v1/businesses/{business_id}/digital-twin/simulate",
        json={
            "actions": [
                {"type": "marketing_change", "value": 10},
                {"type": "marketing_change", "value": 20},
            ]
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_simulate_rejects_out_of_range_action_value(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = client.post(
        f"/api/v1/businesses/{business_id}/digital-twin/simulate",
        json={"actions": [{"type": "price_change", "value": 500}]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_simulate_inventory_change_without_inventory_data_is_refused(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = client.post(
        f"/api/v1/businesses/{business_id}/digital-twin/simulate",
        json={"actions": [{"type": "inventory_change", "value": -20}]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert "inventory" in response.json()["error"]["message"].lower()


def test_simulate_inventory_change_can_cap_projected_sales(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    today = date.today()
    start = today - timedelta(days=90)
    inventory_rows = [
        {
            "Product ID": f"P{i:03d}",
            "Date": start.isoformat(),
            "Stock Level": 1,
            "Reorder Level": 0,
        }
        for i in range(5)
    ]
    _upload_csv(client, business_id, "inventory", pd.DataFrame(inventory_rows))

    response = client.post(
        f"/api/v1/businesses/{business_id}/digital-twin/simulate",
        json={"actions": [{"type": "inventory_change", "value": 0}], "horizon_days": 14},
    )
    assert response.status_code == 200, response.text
    output = response.json()["output"]
    # 5 units of total stock can't cover 14 days of projected demand for this
    # seeded business (2 sales/day historically) — the cap must engage.
    assert output["inventory_constrained"] is True
    assert output["expected_units_sold"] <= 5.0001


def test_simulate_is_isolated_per_business(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    business_a = _create_business(client)
    _seed_rich_business(client, business_a)
    response = client.post(
        f"/api/v1/businesses/{business_a}/digital-twin/simulate",
        json={"actions": [{"type": "marketing_change", "value": 10}]},
    )
    simulation_id = response.json()["id"]

    business_b = _create_business(client)
    cross_response = client.get(
        f"/api/v1/businesses/{business_b}/digital-twin/simulations/{simulation_id}"
    )
    assert cross_response.status_code == 404
