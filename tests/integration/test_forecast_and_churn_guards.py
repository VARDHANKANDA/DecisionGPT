"""Live forecast and churn endpoints: business-specific forecasting, refusals, labelling, tenant isolation and API compatibility.

The registered models were trained on synthetic data (``model_applicability_service``); the forecast must not use them for a
business's own totals, and must say why."""
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.analytics import forecast_service as fs
from app.core import clock
from app.core.errors import ValidationFailedError
from app.services import model_registry_service
from tests.integration.test_analytics import _create_business, _seed_rich_business, _upload_csv


@pytest.fixture()
def rich(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    bid = _create_business(client)
    _seed_rich_business(client, bid)
    return bid


def _fc(client, bid, h=7):
    return client.post(f"/api/v1/businesses/{bid}/analytics/forecast?horizon_days={h}")


def _sales(client, bid, n_days, per_day=4, end=None, start_offset=0):
    end = end or date.today()
    rows = []
    for i in range(n_days):
        d = end - timedelta(days=n_days - 1 - i)
        for j in range(per_day):
            q = 1 + 2 * j + (i % 2) + (2 if d.weekday() >= 5 else 0)  # distinct per product within a day (no duplicate rows)
            rows.append({"Order Date": d.isoformat(), "Product Name": f"P{j}", "Quantity": q, "Unit Price": 100, "Revenue": 100 * q})
    _upload_csv(client, bid, "sales", pd.DataFrame(rows))


# ------------------------------------------------------------------ horizon bounds
@pytest.mark.parametrize("h", [0, -3, 91, 10_000])
def test_horizon_outside_the_supported_range_is_refused(client, rich, h):
    r = _fc(client, rich, h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_the_service_itself_refuses_an_unsupported_horizon(db_session, rich):
    with pytest.raises(ValidationFailedError, match="horizon_days"):
        fs.forecast_sales(db_session, rich, 0)
    with pytest.raises(ValidationFailedError):
        fs.forecast_sales(db_session, rich, fs.MAX_HORIZON_DAYS + 1)


def test_the_longest_supported_horizon_works(client, rich):
    r = _fc(client, rich, fs.MAX_HORIZON_DAYS)
    assert r.status_code == 200 and len(r.json()["points"]) == fs.MAX_HORIZON_DAYS


# ------------------------------------------------------------------ the forecast is the business's own
def test_forecast_describes_its_target_units_basis_and_excludes_the_synthetic_model(client, rich):
    body = _fc(client, rich, 7).json()
    assert body["target"] == "units_sold" and body["aggregation"] == "business_daily_total"
    assert "per calendar day" in body["target_unit"]
    assert body["model_name"].startswith("business_baseline:") and body["model_version"] == "per-business"
    assert body["forecast_basis"] in {"business_specific_validated", "business_specific_baseline", "limited_estimate"}
    assert body["trained_on"] == "this business's own sales history" and "not a synthetic" in body["metrics_scope"]
    assert "synthetic platform data only" in body["registered_model_note"] and "was not used" in body["registered_model_note"]
    assert body["data_profile"]["days"] >= 60 and body["data_profile"]["aggregation"] == "business_daily_total"
    # scale: the seeded business sells a handful of units a day; the synthetic series average 128
    assert np.mean([p["predicted_value"] for p in body["points"]]) < 30


def test_api_compatibility_the_original_fields_are_still_present(client, rich):
    body = _fc(client, rich, 5).json()
    assert {"model_name", "model_version", "metrics", "points"} <= set(body)
    assert all({"forecast_date", "predicted_value", "lower_bound", "upper_bound"} <= set(p) for p in body["points"])
    assert all(p["lower_bound"] <= p["predicted_value"] <= p["upper_bound"] for p in body["points"])


def test_a_registered_model_does_not_change_the_business_forecast_when_it_is_not_applicable(client, db_session, rich):
    """With and without a registry the forecast is identical: the synthetic models are not inputs."""
    with_registry = _fc(client, rich, 7).json()
    from app.models.ml_model import MLModel

    for m in db_session.query(MLModel).all():
        m.status = "archived"
    db_session.commit()
    without_registry = _fc(client, rich, 7).json()
    assert [p["predicted_value"] for p in with_registry["points"]] == [p["predicted_value"] for p in without_registry["points"]]
    assert "No registered forecasting model" in without_registry["registered_model_note"]


# ------------------------------------------------------------------ insufficient history and labelling
def test_a_business_with_no_sales_is_refused(client):
    bid = _create_business(client)
    r = _fc(client, bid)
    assert r.status_code == 422 and r.json()["error"]["code"] == "INSUFFICIENT_DATA"


def test_under_two_weeks_of_history_is_refused_with_the_reason(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    bid = _create_business(client)
    _sales(client, bid, 9)
    r = _fc(client, bid, 7)
    assert r.status_code == 422 and "at least 14 days" in r.json()["error"]["message"]


def test_a_short_history_is_a_labelled_limited_estimate(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    bid = _create_business(client)
    _sales(client, bid, 25)
    body = _fc(client, bid, 7).json()
    assert body["forecast_basis"] == "limited_estimate" and body["interval_reliable"] is False
    assert body["interval_method"] == "sample_std_heuristic_not_calibrated" and body["validation"]["status"] == "not_validated"
    assert any("limited estimate" in w for w in body["warnings"])


def test_a_long_history_is_validated_on_its_own_chronology(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    bid = _create_business(client)
    _sales(client, bid, 150)
    body = _fc(client, bid, 14).json()
    v = body["validation"]
    assert v["status"] == "validated_on_holdout" and v["holdout_origins"] >= 2 and v["selection_origins"] >= 3
    assert body["interval_method"].startswith("empirical_backtest_")
    assert 0.0 <= v["interval"]["observed_holdout_coverage"] <= 1.0


def test_stale_data_is_flagged_with_its_age(client, rich):
    with clock.reference_date(date.today() + timedelta(days=60)):
        body = _fc(client, rich, 7).json()
    assert any("days ago" in w and "not from today" in w for w in body["warnings"])
    assert not any("not from today" in w for w in _fc(client, rich, 7).json()["warnings"])


# ------------------------------------------------------------------ tenant isolation
def test_a_businesses_forecast_does_not_depend_on_another_businesses_data(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    a = _create_business(client)
    _sales(client, a, 100, per_day=3)
    before = _fc(client, a, 14).json()
    b = _create_business(client)
    _sales(client, b, 100, per_day=25)          # a much larger business next door
    after = _fc(client, a, 14).json()
    assert [p["predicted_value"] for p in before["points"]] == [p["predicted_value"] for p in after["points"]]
    other = _fc(client, b, 14).json()
    assert np.mean([p["predicted_value"] for p in other["points"]]) > 3 * np.mean([p["predicted_value"] for p in after["points"]])


# ------------------------------------------------------------------ churn (unchanged contract from the previous stage)
def test_churn_response_says_what_the_score_is_and_what_it_was_trained_on(client, rich):
    body = client.post(f"/api/v1/businesses/{rich}/analytics/churn").json()
    assert body["label_provenance"].startswith("synthetic")
    assert body["trained_on"] == "platform-churn-v1"
    assert "Not a verified churn probability" in body["score_meaning"]
    assert any("synthetic customers" in w for w in body["warnings"]) and any("calibrated" in w for w in body["warnings"])
    assert all(0.0 <= p["churn_probability"] <= 1.0 for p in body["predictions"])
