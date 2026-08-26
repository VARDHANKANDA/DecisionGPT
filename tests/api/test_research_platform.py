"""Phase 2/3 — Dataset Registry (upload/validate/version), Training Center,
Model Registry lifecycle, Experiment Runner lifecycle, Research Overview.
"""
import io

import numpy as np
import pandas as pd

from app.core.config import get_settings


def _headers():
    return {"X-Research-Token": get_settings().research_console_token}


def _csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def _forecasting_df(days: int = 140) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    dates = pd.date_range("2025-01-01", periods=days, freq="D")
    return pd.DataFrame(
        {
            "series_id": "s1",
            "date": dates.strftime("%Y-%m-%d"),
            "units_sold": rng.integers(20, 60, days),
            "price": 500.0,
            "marketing_spend": rng.integers(0, 2000, days).astype(float),
            "promotion_flag": 0,
        }
    )


def _churn_df(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    tenure = rng.integers(30, 900, n)
    recency = rng.integers(0, 400, n)
    freq = rng.integers(1, 12, n)
    aov = rng.uniform(200, 4000, n)
    churned = (recency > 200).astype(int)
    return pd.DataFrame(
        {
            "customer_id": [f"c{i}" for i in range(n)],
            "tenure_days": tenure,
            "recency_days": recency,
            "frequency": freq,
            "avg_order_value": aov,
            "monetary_value": aov * freq,
            "churned": churned,
        }
    )


def _upload(client, df, name, domain):
    return client.post(
        "/api/v1/research/datasets/upload",
        files={"file": (f"{name}.csv", _csv_bytes(df), "text/csv")},
        data={"name": name, "domain": domain, "source": "unit-test"},
        headers=_headers(),
    )


# --- Dataset registry -------------------------------------------------


def test_dataset_upload_validation_and_versioning(client):
    resp = _upload(client, _forecasting_df(), "Sales History", "forecasting")
    assert resp.status_code == 201, resp.text
    v1 = resp.json()
    assert v1["version"] == 1
    assert v1["row_count"] == 140
    assert v1["column_count"] == 6
    assert {c["name"] for c in v1["columns"]} == {
        "series_id", "date", "units_sold", "price", "marketing_spend", "promotion_flag"
    }
    assert v1["validation_ok"] is True
    assert "missing_value_counts" in v1["quality_report"]

    # Re-uploading the same dataset name creates v2.
    resp2 = _upload(client, _forecasting_df(150), "Sales History", "forecasting")
    assert resp2.status_code == 201
    assert resp2.json()["version"] == 2

    listing = client.get("/api/v1/research/datasets", headers=_headers()).json()
    uploaded = listing["uploaded"]
    assert len(uploaded) == 1
    assert uploaded[0]["version_count"] == 2
    assert uploaded[0]["latest_version"] == 2


def test_dataset_upload_reports_quality_issues(client):
    df = _forecasting_df(60)
    df.loc[0:5, "units_sold"] = np.nan  # inject missing values
    df = pd.concat([df, df.iloc[[10]]], ignore_index=True)  # inject a duplicate row
    resp = _upload(client, df, "Messy Data", "forecasting")
    assert resp.status_code == 201
    body = resp.json()
    assert body["missing_summary"].get("units_sold", 0) >= 6
    assert body["duplicates_summary"]["duplicate_row_count"] >= 1


def test_dataset_upload_rejects_unsupported_file_type(client):
    resp = client.post(
        "/api/v1/research/datasets/upload",
        files={"file": ("data.txt", b"nope", "text/plain")},
        data={"name": "bad", "domain": "forecasting"},
        headers=_headers(),
    )
    assert resp.status_code == 422


def test_research_routes_require_token(client):
    for path in ("/api/v1/research/overview", "/api/v1/research/training/runs", "/api/v1/research/datasets"):
        assert client.get(path).status_code == 403


# --- Training Center -------------------------------------------------


def test_training_tasks_only_lists_implemented_tasks(client):
    tasks = client.get("/api/v1/research/training/tasks", headers=_headers()).json()
    assert set(tasks.keys()) == {"forecasting", "churn"}
    assert "xgboost" in tasks["forecasting"]["model_types"]


def test_train_forecasting_on_uploaded_dataset_registers_experimental_model(client, db_session):
    version_id = _upload(client, _forecasting_df(160), "Fc Data", "forecasting").json()["id"]

    resp = client.post(
        "/api/v1/research/training/run",
        json={"task": "forecasting", "model_type": "xgboost", "dataset_version_id": version_id, "seed": 1},
        headers=_headers(),
    )
    assert resp.status_code == 200, resp.text
    run = resp.json()
    assert run["status"] == "completed"
    assert run["started_at"] and run["completed_at"]
    assert set(["mae", "rmse", "mape"]).issubset(run["metrics_json"].keys())
    assert run["model_id"]

    model = client.get(f"/api/v1/research/models/{run['model_id']}", headers=_headers()).json()
    assert model["status"] == "experimental"
    assert model["task"] == "forecasting"
    assert model["source"] == "training_center"


def test_train_churn_on_uploaded_dataset(client):
    version_id = _upload(client, _churn_df(), "Churn Data", "churn").json()["id"]
    resp = client.post(
        "/api/v1/research/training/run",
        json={"task": "churn", "model_type": "random_forest", "dataset_version_id": version_id, "seed": 3},
        headers=_headers(),
    )
    assert resp.status_code == 200, resp.text
    run = resp.json()
    assert run["status"] == "completed"
    assert set(["precision", "recall", "f1", "roc_auc"]).issubset(run["metrics_json"].keys())


def test_training_failure_is_recorded_not_swallowed(client):
    # A churn dataset handed to the forecasting trainer -> missing columns.
    version_id = _upload(client, _churn_df(120), "Wrong Shape", "other").json()["id"]
    resp = client.post(
        "/api/v1/research/training/run",
        json={"task": "forecasting", "model_type": "linear", "dataset_version_id": version_id},
        headers=_headers(),
    )
    assert resp.status_code == 422
    runs = client.get("/api/v1/research/training/runs?task=forecasting", headers=_headers()).json()
    assert any(r["status"] == "failed" and r["error_message"] for r in runs)


def test_train_unsupported_model_type_is_rejected(client):
    version_id = _upload(client, _forecasting_df(120), "X", "forecasting").json()["id"]
    resp = client.post(
        "/api/v1/research/training/run",
        json={"task": "forecasting", "model_type": "transformer", "dataset_version_id": version_id},
        headers=_headers(),
    )
    assert resp.status_code == 422


# --- Model Registry lifecycle -------------------------------------


def test_promote_makes_model_active_and_archives_siblings(client, db_session):
    from app.services import model_registry_service

    model_registry_service.sync_from_file_registry(db_session)  # CLI-trained "active" models

    version_id = _upload(client, _forecasting_df(160), "Promo Data", "forecasting").json()["id"]
    run = client.post(
        "/api/v1/research/training/run",
        json={"task": "forecasting", "model_type": "xgboost", "dataset_version_id": version_id},
        headers=_headers(),
    ).json()
    model_id = run["model_id"]

    promoted = client.post(f"/api/v1/research/models/{model_id}/promote", headers=_headers()).json()
    assert promoted["status"] == "active"
    assert promoted["promoted_at"]

    actives = client.get(
        "/api/v1/research/models?model_type=forecasting_xgboost&status=active", headers=_headers()
    ).json()
    assert [m["id"] for m in actives] == [model_id]  # exactly one active for that name


# --- Experiment Runner lifecycle -------------------------------


def test_experiment_records_lifecycle_timestamps(client, db_session):
    from app.services import model_registry_service

    model_registry_service.sync_from_file_registry(db_session)
    resp = client.post(
        "/api/v1/research/experiments/run",
        json={"experiment_type": "causal", "configuration": {"seed": 5}},
        headers=_headers(),
    )
    assert resp.status_code == 200, resp.text
    run = resp.json()
    assert run["status"] == "completed"
    assert run["started_at"] and run["completed_at"]


# --- Overview -----------------------------------------------------


def test_overview_counts_are_live(client, db_session):
    from app.services import model_registry_service

    model_registry_service.sync_from_file_registry(db_session)
    _upload(client, _forecasting_df(160), "Ov Data", "forecasting")

    overview = client.get("/api/v1/research/overview", headers=_headers()).json()
    assert overview["uploaded_dataset_count"] == 1
    assert overview["platform_dataset_count"] >= 2
    assert overview["active_model_count"] >= 1
    assert "best_metrics" in overview
