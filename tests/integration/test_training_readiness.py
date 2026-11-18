"""Forecast/training readiness report: facts about stored sales, tenant scoping, and what it refuses to claim."""
from datetime import date, timedelta

import pandas as pd

from tests.integration.test_analytics import _create_business, _upload_csv


def _upload_sales(client, bid, rows):
    _upload_csv(client, bid, "sales", pd.DataFrame(rows))


def _rows(n_days, per_day=3, end=None, skip=()):
    end = end or date.today()
    out = []
    for i in range(n_days):
        if i in skip:
            continue
        d = end - timedelta(days=n_days - 1 - i)
        for j in range(per_day):
            q = 1 + 2 * j + (i % 2)
            out.append({"Order Date": d.isoformat(), "Product Name": f"P{j}", "Quantity": q, "Unit Price": 100, "Revenue": 100 * q})
    return out


def _get(client, bid):
    r = client.get(f"/api/v1/businesses/{bid}/data/forecast-readiness")
    assert r.status_code == 200, r.text
    return r.json()


def test_a_business_without_sales_is_not_ready_and_says_why(client):
    out = _get(client, _create_business(client))
    assert out["ready_for_forecast"] is False and out["ready_for_training"] is False
    assert out["blockers"] == ["No sales are stored for this business."]


def test_target_units_range_and_provenance_are_reported(client):
    bid = _create_business(client)
    _upload_sales(client, bid, _rows(40))
    out = _get(client, bid)
    assert out["target"]["name"] == "units_sold" and out["target"]["unit"].startswith("units per calendar day")
    assert out["sales"]["days"] == 40 and out["sales"]["rows"] == 120
    assert out["ready_for_forecast"] is True and out["ready_for_training"] is False
    assert any("at least 180 days" in b for b in out["training_blockers"])
    p = out["provenance"]
    assert p["uploads"] == 1 and p["sources"][0]["filename"] == "sales.csv"
    assert "cannot verify" in p["statement"] and "assumed" in p["currency"] and "without a time zone" in p["timezone"]


def test_a_gap_is_reported_as_zero_sale_days_that_the_data_cannot_explain(client):
    bid = _create_business(client)
    _upload_sales(client, bid, _rows(60, skip=range(20, 40)))        # 20 consecutive days with no rows
    out = _get(client, bid)
    assert out["sales"]["zero_days"] >= 20 and out["sales"]["longest_zero_run_days"] >= 20
    assert any(i["kind"] == "long_zero_run" for i in out["issues"])
    assert "treated as true zeros" in out["sales"]["zero_days_are"]
    assert out["ready_for_training"] is False


def test_a_long_clean_history_is_ready_for_training_and_still_not_called_real_sme_data(client):
    bid = _create_business(client)
    _upload_sales(client, bid, _rows(220))
    out = _get(client, bid)
    assert out["ready_for_forecast"] is True and out["ready_for_training"] is True and out["training_blockers"] == []
    assert "never on other businesses" in out["evidence_note"] and "cannot verify" in out["provenance"]["statement"]


def test_readiness_is_scoped_to_the_business(client):
    a = _create_business(client)
    b = _create_business(client)
    _upload_sales(client, a, _rows(30, per_day=2))
    _upload_sales(client, b, _rows(200, per_day=3))
    assert _get(client, a)["sales"]["days"] == 30 and _get(client, b)["sales"]["days"] == 200
    assert _get(client, a)["provenance"]["uploads"] == 1


def test_a_file_waiting_for_column_mapping_or_failed_is_named_in_the_blockers(client):
    bid = _create_business(client)
    r = client.post(f"/api/v1/businesses/{bid}/data/upload?data_type=sales",
                    files={"file": ("sales.csv", b"foo,bar\n1,2\n3,4\n", "text/csv")})
    assert r.json()["status"] == "needs_mapping_confirmation"
    r = client.post(f"/api/v1/businesses/{bid}/data/upload?data_type=sales", files={"file": ("empty.csv", b"", "text/csv")})
    assert r.json()["status"] == "failed"
    out = _get(client, bid)
    assert out["ready_for_forecast"] is False
    joined = " ".join(out["blockers"])
    assert "waiting for you to confirm which column is which" in joined and "sales.csv" in joined
    assert "1 upload(s) failed" in joined and "empty.csv" in joined


def test_a_limited_estimate_does_not_claim_a_backtest(client):
    bid = _create_business(client)
    _upload_sales(client, bid, _rows(30))
    j = client.post(f"/api/v1/businesses/{bid}/analytics/forecast?horizon_days=7").json()
    assert j["forecast_basis"] == "limited_estimate"
    assert "too little history to backtest" in j["metrics_scope"] and "own chronological backtest" not in j["metrics_scope"]


def test_built_in_example_rows_are_flagged_in_the_readiness_report_and_the_forecast(client):
    bid = _create_business(client)
    _upload_csv(client, bid, "products", pd.DataFrame([{"Product ID": "EX-P1", "Product Name": "Example: Cotton kurta", "Selling Price": 100}]))
    _upload_sales(client, bid, _rows(40))
    assert "example data" in (_get(client, bid)["example_data"] or "")
    j = client.post(f"/api/v1/businesses/{bid}/analytics/forecast?horizon_days=7").json()
    assert any("example data" in w for w in j["warnings"])
    other = _create_business(client)
    _upload_sales(client, other, _rows(40))
    assert _get(client, other)["example_data"] is None
    assert not any("example data" in w for w in client.post(f"/api/v1/businesses/{other}/analytics/forecast?horizon_days=7").json()["warnings"])


def test_a_forecast_from_data_more_than_a_week_old_says_where_it_starts(client):
    bid = _create_business(client)
    _upload_sales(client, bid, _rows(60, end=date.today() - timedelta(days=9)))
    j = client.post(f"/api/v1/businesses/{bid}/analytics/forecast?horizon_days=7").json()
    assert any("9 days ago" in w and "not from today" in w for w in j["warnings"])


def test_unreadable_files_are_explained_in_plain_language(client):
    bid = _create_business(client)
    r = client.post(f"/api/v1/businesses/{bid}/data/upload?data_type=sales", files={"file": ("x.csv", bytes(range(256)) * 4, "text/csv")}).json()
    assert r["status"] == "failed" and "does not look like a CSV file" in r["error_message"] and "codec" not in r["error_message"]
    r = client.post(f"/api/v1/businesses/{bid}/data/upload?data_type=sales", files={"file": ("e.csv", b"", "text/csv")}).json()
    assert r["status"] == "failed" and "the file is empty" in r["error_message"]


def test_stale_customer_records_are_flagged_before_scores_are_trusted(client, db_session):
    from app.analytics import churn_service
    from app.services import model_registry_service

    model_registry_service.sync_from_file_registry(db_session)
    bid = _create_business(client)
    old = date.today() - timedelta(days=200)
    cust = pd.DataFrame([{"Customer ID": f"C{i:03d}", "First Purchase Date": (old - timedelta(days=100)).isoformat(),
                          "Last Purchase Date": (old + timedelta(days=i % 5)).isoformat(), "Purchase Frequency": 3 + i % 4,
                          "Monetary Value": 1000 + 10 * i} for i in range(40)])
    _upload_csv(client, bid, "customers", cust)
    assert "days old" in churn_service.data_age_warning(db_session, bid)
    j = client.post(f"/api/v1/businesses/{bid}/analytics/churn").json()
    assert any("not necessarily because they stopped buying" in w for w in j["warnings"])
    fresh = _create_business(client)
    cust2 = cust.copy()
    cust2["Last Purchase Date"] = [(date.today() - timedelta(days=i % 10)).isoformat() for i in range(40)]
    _upload_csv(client, fresh, "customers", cust2)
    assert churn_service.data_age_warning(db_session, fresh) is None
