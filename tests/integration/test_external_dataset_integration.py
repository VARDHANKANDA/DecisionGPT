"""External benchmark datasets flow through the EXISTING Dataset Registry
and Training Center without disturbing production models.
"""
import io

import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.models.ml_model import MLModel
from app.services import model_registry_service, research_dataset_service, training_service


def _forecasting_csv(days: int = 140) -> bytes:
    rng = np.random.default_rng(0)
    dates = pd.date_range("2024-01-01", periods=days, freq="D")
    frames = []
    for s in ("EXT_A", "EXT_B"):
        frames.append(
            pd.DataFrame(
                {
                    "series_id": s,
                    "date": dates.strftime("%Y-%m-%d"),
                    "units_sold": rng.integers(20, 60, days),
                    "price": 100.0,
                    "marketing_spend": 0.0,
                    "promotion_flag": 0,
                }
            )
        )
    buf = io.BytesIO()
    pd.concat(frames).to_csv(buf, index=False)
    return buf.getvalue()


def _derived_churn_csv(n: int = 400) -> bytes:
    rng = np.random.default_rng(1)
    recency = rng.integers(0, 260, n)
    df = pd.DataFrame(
        {
            "tenure_days": rng.integers(40, 900, n),
            "recency_days": recency,
            "frequency": rng.integers(1, 15, n),
            "avg_order_value": rng.uniform(200, 3000, n).round(2),
            "monetary_value": rng.uniform(400, 40000, n).round(2),
            "churned": (recency > 150).astype(int),
        }
    )
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def test_external_benchmark_registers_and_trains_experimental_only(client, db_session, isolate_research_artifacts):
    # A production ("active") model must exist first, so we can prove it is untouched.
    model_registry_service.sync_from_file_registry(db_session)
    active_before = {
        (m.model_name, m.version) for m in db_session.query(MLModel).filter(MLModel.status == "active")
    }
    assert active_before, "expected synced baseline models to be active"

    # 1. register a "real" external forecasting benchmark through the existing service
    version = research_dataset_service.upload_dataset(
        db_session,
        name="External M5-style Forecasting Benchmark (test)",
        domain="forecasting",
        filename="ext_forecasting.csv",
        content=_forecasting_csv(),
        description="External Benchmark - synthetic stand-in for the M5 adapter output.",
        source="External Benchmark - M5-style (data_type=real)",
        license="CC BY 4.0 (test)",
    )
    assert version.validation_ok
    assert {c["name"] for c in version.schema_json} >= {
        "series_id", "date", "units_sold", "price", "marketing_spend", "promotion_flag"
    }

    # 2. train through the Training Center on that dataset version
    run = training_service.start_training(
        db_session, task="forecasting", model_type="xgboost",
        dataset_version_id=version.id, random_seed=42,
    )
    assert run.status == "completed"
    assert run.dataset_version_label.startswith("upload:")
    assert set(["mae", "rmse", "mape"]).issubset(run.metrics_json)

    model = db_session.get(MLModel, run.model_id)
    assert model.status == "experimental"          # never active
    assert model.source == "training_center"

    # 3. production selection + active set are unchanged
    active_after = {
        (m.model_name, m.version) for m in db_session.query(MLModel).filter(MLModel.status == "active")
    }
    assert active_after == active_before
    best = model_registry_service.select_best_model(
        db_session, ["sales_forecast_naive", "sales_forecast_linear", "sales_forecast_xgboost"],
        metric="mae", minimize=True,
    )
    assert best is not None and best.status == "active" and best.id != model.id


def test_external_derived_churn_dataset_labelled_and_trains(client, db_session, isolate_research_artifacts):
    model_registry_service.sync_from_file_registry(db_session)

    version = research_dataset_service.upload_dataset(
        db_session,
        name="External UCI-style Derived Churn (test)",
        domain="churn",
        filename="ext_churn.csv",
        content=_derived_churn_csv(),
        description="DERIVED CHURN LABEL (inactivity-based, time-aware split). Does NOT replace platform-churn-v1.",
        source="External Benchmark - UCI-style (data_type=real)",
        license="CC BY 4.0 (test)",
    )
    ds = version  # ResearchDatasetVersion
    listed = research_dataset_service.list_datasets(db_session)
    entry = next(d for d in listed if d["id"] == ds.dataset_id)
    assert "External Benchmark" in entry["source"]
    assert "DERIVED CHURN LABEL" in entry["description"]

    run = training_service.start_training(
        db_session, task="churn", model_type="random_forest",
        dataset_version_id=version.id, random_seed=42,
    )
    assert run.status == "completed"
    assert set(["precision", "recall", "f1", "roc_auc"]).issubset(run.metrics_json)
    assert db_session.get(MLModel, run.model_id).status == "experimental"


def test_registry_still_separates_platform_from_external(client, db_session, isolate_research_artifacts):
    """The platform (synthetic) datasets and the uploaded external ones are
    reported through distinct surfaces - no duplicate registry."""
    research_dataset_service.upload_dataset(
        db_session, name="External thing (test)", domain="other",
        filename="x.csv", content=b"a,b\n1,2\n3,4\n",
        source="External Benchmark - x", license="MIT",
    )
    body = client.get(
        "/api/v1/research/datasets",
        headers={"X-Research-Token": get_settings().research_console_token},
    ).json()
    assert set(body.keys()) == {"platform", "uploaded"}
    assert any(d["evidence_level"] == "SYNTHETIC" for d in body["platform"])
    assert any("External Benchmark" in (d["source"] or "") for d in body["uploaded"])
