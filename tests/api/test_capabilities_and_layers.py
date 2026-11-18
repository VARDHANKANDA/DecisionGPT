"""Data-aware capability detection + the new finance / business-profile
upload layers (docs/INDIAN_SME_DATA_ARCHITECTURE.md).
"""
import io

import pandas as pd


def _business(client, **profile) -> str:
    body = {"name": "Layer Co", "industry": "apparel", "business_type": "D2C", "business_size": "micro"}
    body.update(profile)
    r = client.post("/api/v1/businesses", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _csv(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def _upload(client, bid: str, df: pd.DataFrame, data_type: str, name: str):
    r = client.post(
        f"/api/v1/businesses/{bid}/data/upload?data_type={data_type}",
        files={"file": (name, _csv(df), "text/csv")},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _caps(client, bid: str) -> dict:
    r = client.get(f"/api/v1/businesses/{bid}/data/capabilities")
    assert r.status_code == 200, r.text
    return {c["feature"]: c for c in r.json()["capabilities"]}


def test_capabilities_reflect_available_data_not_fabrication(client):
    bid = _business(client)
    caps = _caps(client, bid)
    # nothing uploaded -> forecasting / marketing / inventory / finance all disabled with a reason
    assert caps["Demand / sales forecasting"]["enabled"] is False
    assert "sales" in caps["Demand / sales forecasting"]["reason"].lower()
    assert caps["Marketing optimization"]["enabled"] is False
    assert caps["Financial health analysis"]["enabled"] is False
    assert caps["Inventory optimization"]["enabled"] is False

    # upload 40 days of sales -> sales analysis + forecasting + pricing unlock
    days = pd.date_range("2024-01-01", periods=40, freq="D")
    sales = pd.DataFrame({
        "date": days.strftime("%Y-%m-%d"),
        "quantity": range(1, 41),
        "unit_price": 500.0,
    })
    _upload(client, bid, sales, "sales", "sales.csv")
    caps = _caps(client, bid)
    assert caps["Sales analysis"]["enabled"] is True
    assert caps["Demand / sales forecasting"]["enabled"] is True
    assert caps["Pricing simulation"]["enabled"] is True
    # still no marketing / finance
    assert caps["Marketing optimization"]["enabled"] is False
    assert caps["Financial health analysis"]["enabled"] is False


def test_finance_upload_layer(client):
    bid = _business(client)
    fin = pd.DataFrame([
        {"date": "2024-01-31", "revenue": 500000, "cogs": 300000, "operating_expenses": 120000,
         "net_profit": 80000, "cash_balance": 250000},
        {"date": "2024-02-29", "revenue": 540000, "cogs": 315000, "operating_expenses": 125000,
         "net_profit": 100000, "cash_balance": 300000},
    ])
    job = _upload(client, bid, fin, "finance", "finance.csv")
    assert job["status"] == "completed", job
    assert job["summary_json"]["rows_ingested"]["finance"] == 2

    summary = client.get(f"/api/v1/businesses/{bid}/data/summary").json()
    assert summary["finance_records"] == 2

    caps = _caps(client, bid)
    assert caps["Financial health analysis"]["enabled"] is True


def test_business_profile_layer_conditions_recommendations(client):
    # profile set at create time
    bid = _business(client, state="Telangana", city="Hyderabad", enterprise_type="Micro",
                    nic_code="47711", registration_date="2020-06-01")
    out = client.get(f"/api/v1/businesses/{bid}").json()
    assert out["state"] == "Telangana"
    assert out["enterprise_type"] == "Micro"
    assert out["business_age_years"] is not None and out["business_age_years"] >= 4

    summary = client.get(f"/api/v1/businesses/{bid}/data/summary").json()
    assert summary["business_profile_set"] is True

    caps = _caps(client, bid)
    assert caps["Region / industry context conditioning"]["enabled"] is True

    # and a profile can also arrive as an upload sheet
    bid2 = _business(client)
    prof = pd.DataFrame([{"state": "Maharashtra", "district": "Pune", "city": "Pune",
                          "enterprise_type": "Small", "nic_code": "14101"}])
    job = _upload(client, bid2, prof, "business_profile", "profile.csv")
    assert job["status"] == "completed", job
    assert client.get(f"/api/v1/businesses/{bid2}").json()["state"] == "Maharashtra"
