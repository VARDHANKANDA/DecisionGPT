import io
from datetime import date, timedelta

import pandas as pd

from app.services import model_registry_service


def _create_business(client) -> str:
    response = client.post(
        "/api/v1/businesses",
        json={"name": "Analytics Co", "industry": "apparel", "business_type": "D2C", "business_size": "small"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _upload_csv(client, business_id: str, data_type: str, df: pd.DataFrame):
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    response = client.post(
        f"/api/v1/businesses/{business_id}/data/upload?data_type={data_type}",
        files={"file": (f"{data_type}.csv", buf.getvalue().encode(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed", response.json()
    return response.json()


def _seed_rich_business(client, business_id: str):
    today = date.today()
    start = today - timedelta(days=90)

    products = pd.DataFrame(
        [{"Product ID": f"P{i:03d}", "Product Name": f"Item {i}", "Selling Price": 500 + i * 50} for i in range(5)]
    )
    _upload_csv(client, business_id, "products", products)

    customers = pd.DataFrame(
        [
            {
                "Customer ID": f"C{i:03d}",
                "First Purchase Date": (start + timedelta(days=i % 60)).isoformat(),
                "Last Purchase Date": (today - timedelta(days=i % 20)).isoformat(),
                "Purchase Frequency": 2 + (i % 5),
                "Monetary Value": 1000 + i * 37,
            }
            for i in range(40)
        ]
    )
    _upload_csv(client, business_id, "customers", customers)

    sales_rows = []
    for day_offset in range(90):
        sale_date = start + timedelta(days=day_offset)
        for j in range(2):
            product_idx = (day_offset + j) % 5
            customer_idx = (day_offset * 2 + j) % 40
            sales_rows.append(
                {
                    "Order Date": sale_date.isoformat(),
                    "Customer ID": f"C{customer_idx:03d}",
                    "Product ID": f"P{product_idx:03d}",
                    "Quantity": 1 + (j % 3),
                    "Unit Price": 500 + product_idx * 50,
                    "Discount": 0,
                }
            )
    _upload_csv(client, business_id, "sales", pd.DataFrame(sales_rows))

    marketing_rows = [
        {
            "Date": (start + timedelta(days=i)).isoformat(),
            "Channel": "Instagram",
            "Spend": 1000 + (i % 10) * 20,
            "Impressions": 5000,
            "Clicks": 200,
            "Conversions": 10,
            "Attributed Revenue": 4000,
        }
        for i in range(0, 90, 3)
    ]
    _upload_csv(client, business_id, "marketing_campaigns", pd.DataFrame(marketing_rows))


def test_kpis_reflect_real_uploaded_data(client):
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = client.get(f"/api/v1/businesses/{business_id}/analytics/kpis")
    assert response.status_code == 200
    kpis = response.json()
    assert kpis["orders"] == 180  # 90 days * 2 sales/day
    assert kpis["revenue"] > 0
    assert kpis["average_order_value"] > 0
    assert kpis["marketing_spend"] > 0
    assert kpis["marketing_roi"] is not None
    assert kpis["conversion_rate"] is not None


def test_kpis_insufficient_data_returns_zeros_not_fabrication(client):
    business_id = _create_business(client)
    response = client.get(f"/api/v1/businesses/{business_id}/analytics/kpis")
    assert response.status_code == 200
    kpis = response.json()
    assert kpis["revenue"] == 0
    assert kpis["orders"] == 0
    assert kpis["average_order_value"] is None
    assert kpis["profit"] is None
    assert "No sales" in kpis["notes"][0]


def test_forecast_requires_sufficient_history(client):
    business_id = _create_business(client)
    response = client.post(f"/api/v1/businesses/{business_id}/analytics/forecast")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSUFFICIENT_DATA"


def test_forecast_with_sufficient_history_and_registered_model(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)

    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = client.post(f"/api/v1/businesses/{business_id}/analytics/forecast?horizon_days=7")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["model_name"] in {"sales_forecast_naive", "sales_forecast_linear", "sales_forecast_xgboost"}
    assert len(body["points"]) == 7
    for point in body["points"]:
        assert point["predicted_value"] >= 0
        assert point["lower_bound"] <= point["predicted_value"] <= point["upper_bound"]


def test_churn_requires_sufficient_customers(client):
    business_id = _create_business(client)
    response = client.post(f"/api/v1/businesses/{business_id}/analytics/churn")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INSUFFICIENT_DATA"


def test_churn_with_sufficient_customers_and_registered_model(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)

    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = client.post(f"/api/v1/businesses/{business_id}/analytics/churn")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["model_name"] in {"churn_logistic_regression", "churn_random_forest", "churn_xgboost"}
    assert len(body["predictions"]) == 40
    for pred in body["predictions"]:
        assert 0.0 <= pred["churn_probability"] <= 1.0


def test_period_comparison_reflects_real_recent_vs_prior_revenue(client):
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = client.get(f"/api/v1/businesses/{business_id}/analytics/period-comparison?days=30")
    assert response.status_code == 200
    body = response.json()
    assert body["current_revenue"] >= 0
    assert body["previous_revenue"] >= 0
    assert body["change_absolute"] == round(body["current_revenue"] - body["previous_revenue"], 2)


def test_period_comparison_with_no_data_is_zero_not_fabricated(client):
    business_id = _create_business(client)
    response = client.get(f"/api/v1/businesses/{business_id}/analytics/period-comparison")
    assert response.status_code == 200
    body = response.json()
    assert body["current_revenue"] == 0
    assert body["previous_revenue"] == 0
    assert body["change_pct"] is None


def test_top_products_reflects_real_sales(client):
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = client.get(f"/api/v1/businesses/{business_id}/analytics/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) == 5
    revenues = [p["revenue"] for p in products]
    assert revenues == sorted(revenues, reverse=True)
    assert sum(p["units_sold"] for p in products) > 0


def test_marketing_by_channel_reflects_real_campaigns(client):
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = client.get(f"/api/v1/businesses/{business_id}/analytics/marketing-channels")
    assert response.status_code == 200
    channels = response.json()
    assert len(channels) == 1
    assert channels[0]["channel"] == "Instagram"
    assert channels[0]["spend"] > 0
    assert channels[0]["roi"] is not None


def test_marketing_by_channel_empty_when_no_campaigns(client):
    business_id = _create_business(client)
    response = client.get(f"/api/v1/businesses/{business_id}/analytics/marketing-channels")
    assert response.status_code == 200
    assert response.json() == []


def test_customer_summary_reflects_real_customers(client):
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    response = client.get(f"/api/v1/businesses/{business_id}/analytics/customers")
    assert response.status_code == 200
    body = response.json()
    assert body["total_customers"] == 40
    assert body["customers_with_purchase_history"] == 40
    assert body["avg_monetary_value"] is not None


def test_inventory_status_empty_when_no_inventory_data(client):
    business_id = _create_business(client)
    _seed_rich_business(client, business_id)
    response = client.get(f"/api/v1/businesses/{business_id}/analytics/inventory")
    assert response.status_code == 200
    assert response.json() == []


def test_inventory_status_flags_low_stock_from_real_data(client):
    import pandas as pd
    from datetime import date

    business_id = _create_business(client)
    _seed_rich_business(client, business_id)

    inventory_rows = [
        {"Product ID": "P000", "Date": date.today().isoformat(), "Stock Level": 2, "Reorder Level": 10},
        {"Product ID": "P001", "Date": date.today().isoformat(), "Stock Level": 500, "Reorder Level": 10},
    ]
    _upload_csv(client, business_id, "inventory", pd.DataFrame(inventory_rows))

    response = client.get(f"/api/v1/businesses/{business_id}/analytics/inventory")
    assert response.status_code == 200
    statuses = {s["product_id"]: s for s in response.json()}
    low = [s for s in statuses.values() if s["current_stock"] == 2][0]
    healthy = [s for s in statuses.values() if s["current_stock"] == 500][0]
    assert low["low_stock"] is True
    assert healthy["low_stock"] is False


def test_analytics_breakdowns_are_isolated_per_business(client):
    business_a = _create_business(client)
    _seed_rich_business(client, business_a)
    business_b = _create_business(client)

    response = client.get(f"/api/v1/businesses/{business_b}/analytics/products")
    assert response.status_code == 200
    assert response.json() == []
