"""Validation on a business's own data through the API: tenant scoping, persistence, separation from the model lifecycle, honest limits."""
import io
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.models.ml_model import MLModel
from app.services import model_registry_service
from tests.api.test_platform_api import P, _owner, auth_on  # noqa: F401  (auth_on is a fixture)


def _upload_sales(client, bid, headers, df):
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    r = client.post(f"{P}/{bid}/data/upload?data_type=sales", files={"file": ("sales.csv", buf.getvalue().encode(), "text/csv")}, headers=headers)
    assert r.status_code == 200 and r.json()["status"] == "completed", r.text


def _weekly_rows(n, seed=0, customers=0):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        d = date.today() - timedelta(days=n - 1 - i)
        mult = 1.6 if d.weekday() >= 5 else 1.0
        for p in range(3):
            q = max(1, int(round(7 * mult + rng.normal(0, 1.5))))
            row = {"Order Date": d.isoformat(), "Product Name": f"Item {p}", "Quantity": q, "Unit Price": 100 + 10 * p, "Revenue": q * (100 + 10 * p)}
            if customers:
                row["Customer ID"] = f"C{(i * 3 + p) % customers:03d}"
            out.append(row)
    return pd.DataFrame(out)


@pytest.fixture()
def world(client, db_session, auth_on):  # noqa: F811
    a, ha = _owner(client, "va@example.com", "Alpha")
    b, hb = _owner(client, "vb@example.com", "Beta")
    return client, db_session, (a, ha), (b, hb)


def _model_state(db):
    return sorted((m.model_name, m.version, m.status, str((m.lifecycle_json or {}).get("artifact"))) for m in db.query(MLModel).all())


def test_forecast_validation_is_recorded_reproducible_and_does_not_touch_models(world):
    client, db, (a, ha), _ = world
    model_registry_service.sync_from_file_registry(db)
    before = _model_state(db)
    _upload_sales(client, a, ha, _weekly_rows(150))
    r1 = client.post(f"{P}/{a}/validation/forecast/run", json={"horizons": [7, 14]}, headers=ha)
    assert r1.status_code == 200, r1.text
    rep = r1.json()
    assert rep["kind"] == "forecast_eval" and rep["evidence"]["level"] == "L2_business_own_history_backtest"
    assert "business impact" in " ".join(rep["evidence"]["not_evidence_of"]) and rep["evidence"]["separation"].startswith("this evaluation changed no model")
    assert rep["config"]["horizons"] == [7, 14] and rep["config"]["policy_status"].startswith("provisional")
    assert len(rep["dataset"]["sha256"]) == 64 and rep["data_quality"]["calendar_days_without_rows"] == 0
    assert [h["horizon_days"] for h in rep["horizons"]] == [7, 14] and all(h["status"] == "evaluated" for h in rep["horizons"])
    r2 = client.post(f"{P}/{a}/validation/forecast/run", json={"horizons": [7, 14]}, headers=ha).json()
    assert r2["dataset"]["sha256"] == rep["dataset"]["sha256"]                       # same data -> same identity ...
    assert r2["horizons"][0]["holdout"] == rep["horizons"][0]["holdout"]             # ... and the same numbers
    assert r2["id"] != rep["id"]
    assert _model_state(db) == before                                                # evaluation never changes a model or lifecycle state
    runs = client.get(f"{P}/{a}/validation/runs", headers=ha).json()["runs"]
    assert {r["id"] for r in runs} == {rep["id"], r2["id"]}
    assert client.get(f"{P}/{a}/validation/runs/{rep['id']}", headers=ha).json()["result"]["dataset"]["sha256"] == rep["dataset"]["sha256"]


def test_validation_results_are_tenant_scoped(world):
    client, _, (a, ha), (b, hb) = world
    _upload_sales(client, a, ha, _weekly_rows(100))
    rid = client.post(f"{P}/{a}/validation/forecast/run", json={}, headers=ha).json()["id"]
    assert client.get(f"{P}/{a}/validation/runs/{rid}").status_code == 401                 # no token
    assert client.get(f"{P}/{a}/validation/runs/{rid}", headers=hb).status_code in (403, 404)   # another owner
    assert client.post(f"{P}/{a}/validation/forecast/run", json={}, headers=hb).status_code in (403, 404)
    assert client.get(f"{P}/{b}/validation/runs/{rid}", headers=hb).status_code == 404     # not visible through the other tenant's route
    assert client.get(f"{P}/{b}/validation/runs", headers=hb).json()["runs"] == []


def test_validation_inputs_are_strict_and_missing_data_is_explained(world):
    client, _, (a, ha), _ = world
    assert client.post(f"{P}/{a}/validation/forecast/run", json={"horizons": [7]}, headers=ha).status_code == 422   # no sales yet
    _upload_sales(client, a, ha, _weekly_rows(60))
    for bad in ({"horizons": [0]}, {"horizons": [91]}, {"horizons": [7, 7]}, {"horizons": [1, 2, 3, 4]}, {"horizons": ["x"]}, {"surprise": 1}):
        assert client.post(f"{P}/{a}/validation/forecast/run", json=bad, headers=ha).status_code == 422, bad
    rep = client.post(f"{P}/{a}/validation/forecast/run", json={"horizons": [28]}, headers=ha).json()
    assert rep["horizons"][0]["status"] in ("descriptive_only", "insufficient_history")    # 60 days: no validation is claimed
    assert "no comparison is a validation" in rep["horizons"][0]["statement"] or "history" in rep["horizons"][0]["statement"]


def test_customer_score_validation_is_a_labelled_proxy_ranking_check(world):
    client, db, (a, ha), _ = world
    model_registry_service.sync_from_file_registry(db)
    # 60 customers: the first 30 buy through the whole period, the last 30 stop buying 100 days before the end
    rows = []
    rng = np.random.default_rng(4)
    for i in range(200):
        d = date.today() - timedelta(days=199 - i)
        for c in range(60):
            if c >= 30 and i >= 100:
                continue
            if rng.random() < 0.25:
                rows.append({"Order Date": d.isoformat(), "Product Name": "P", "Quantity": 1, "Unit Price": 100, "Revenue": 100, "Customer ID": f"K{c:03d}"})
    _upload_sales(client, a, ha, pd.DataFrame(rows))
    before = _model_state(db)
    r = client.post(f"{P}/{a}/validation/customer-scores/run", json={"window_days": 60}, headers=ha)
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["kind"] == "customer_eval" and rep["target"]["kind"] == "proxy: inactivity"
    assert rep["calibration"]["evaluated"] is False and "probability" in rep["calibration"]["reason"]
    assert rep["model"]["label_provenance"].startswith("synthetic")
    assert "a probability that any customer will leave" in rep["evidence"]["not_evidence_of"]
    first = rep["cutoffs"][0]
    assert first["status"] == "evaluated" and 0.0 <= first["roc_auc"] <= 1.0 and first["prevalence"] > 0.3
    assert first["roc_auc_recency_only"] > 0.8                                      # the stopped customers are obviously the lapsed ones
    assert _model_state(db) == before


def test_customer_validation_refuses_when_there_are_too_few_customers(world):
    client, db, (a, ha), _ = world
    model_registry_service.sync_from_file_registry(db)
    _upload_sales(client, a, ha, _weekly_rows(120, customers=8))
    rep = client.post(f"{P}/{a}/validation/customer-scores/run", json={}, headers=ha).json()
    assert rep["evidence"]["level"] == "none" and all(c["status"] == "insufficient_evidence" for c in rep["cutoffs"])
    assert "needs at least 30 customers" in rep["cutoffs"][0]["reason"]
    assert client.post(f"{P}/{a}/validation/customer-scores/run", json={"window_days": 5}, headers=ha).status_code == 422
