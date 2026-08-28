"""External benchmark datasets flow through the EXISTING Dataset Registry
and Training Center without disturbing production models.

Active benchmark = the real Indian AGMARKNET mandi-price dataset (a
price-forecasting benchmark: the canonical ``units_sold`` slot carries the
daily modal price - the source has no quantity field). The retired non-Indian
datasets must remain clearly labelled if they are ever re-registered.
"""
import io

import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.models.ml_model import MLModel
from app.services import model_registry_service, research_dataset_service, training_service


def _india_style_forecasting_csv(days: int = 240) -> bytes:
    """Mimics ml/preprocessing/india_mandi_adapter.build_forecasting output:
    units_sold = daily modal price, price = trailing median (backward only)."""
    rng = np.random.default_rng(0)
    dates = pd.date_range("2018-01-01", periods=days, freq="D")
    frames = []
    for s in ("MANDI_ONION__LASALGAON", "MANDI_TOMATO__KOLAR"):
        modal = np.maximum(200, 1500 + np.cumsum(rng.normal(0, 25, days)))
        trailing = pd.Series(modal).shift(1).rolling(28, min_periods=5).median()
        trailing = trailing.fillna(pd.Series(modal).iloc[0]).to_numpy()
        frames.append(
            pd.DataFrame(
                {
                    "series_id": s,
                    "date": dates.strftime("%Y-%m-%d"),
                    "units_sold": np.round(modal, 2),
                    "price": np.round(trailing, 2),
                    "marketing_spend": 0.0,
                    "promotion_flag": 0,
                    "modal_price": np.round(modal, 2),
                }
            )
        )
    buf = io.BytesIO()
    pd.concat(frames).to_csv(buf, index=False)
    return buf.getvalue()


def test_external_benchmark_registers_and_trains_experimental_only(client, db_session, isolate_research_artifacts):
    # A production ("active") model must exist first, so we can prove it is untouched.
    model_registry_service.sync_from_file_registry(db_session)
    active_before = {
        (m.model_name, m.version) for m in db_session.query(MLModel).filter(MLModel.status == "active")
    }
    assert active_before, "expected synced baseline models to be active"

    # 1. register the real Indian benchmark through the existing service
    version = research_dataset_service.upload_dataset(
        db_session,
        name="External India Mandi Prices - Forecasting (test)",
        domain="forecasting",
        filename="india_mandi_forecasting.csv",
        content=_india_style_forecasting_csv(),
        description=(
            "INDIAN PRICE-FORECASTING BENCHMARK (AGMARKNET daily mandi modal prices, "
            "data.gov.in, GODL-India). Canonical 'units_sold' carries the daily modal "
            "price (INR/quintal); source has no quantity field."
        ),
        source="External Benchmark - India Agri-Commodity Daily Market Prices (data_type=real)",
        license="Government Open Data License - India (GODL-India)",
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


def test_retired_non_indian_dataset_is_clearly_labelled(client, db_session, isolate_research_artifacts):
    """If a retired benchmark is ever re-registered (scripts/*.py --retired) it
    must carry the RETIRED_NON_INDIAN_BENCHMARK marker so it can never be
    mistaken for the active India-focused evaluation."""
    model_registry_service.sync_from_file_registry(db_session)

    version = research_dataset_service.upload_dataset(
        db_session,
        name="RETIRED_NON_INDIAN_BENCHMARK External M5 Forecasting Benchmark (test)",
        domain="forecasting",
        filename="m5.csv",
        content=b"series_id,date,units_sold,price,marketing_spend,promotion_flag\n"
                b"A,2016-01-01,5,3.5,0,0\nA,2016-01-02,6,3.5,0,0\n",
        description="[RETIRED_NON_INDIAN_BENCHMARK] M5 Forecasting. Geography: USA.",
        source="RETIRED_NON_INDIAN_BENCHMARK - External Benchmark - M5 Forecasting (data_type=real)",
        license="M5 competition data (Walmart).",
    )
    listed = research_dataset_service.list_datasets(db_session)
    entry = next(d for d in listed if d["id"] == version.dataset_id)
    assert "RETIRED_NON_INDIAN_BENCHMARK" in entry["source"]
    assert "RETIRED_NON_INDIAN_BENCHMARK" in entry["description"]
    assert "USA" in entry["description"]


def test_registry_still_separates_platform_from_external(client, db_session, isolate_research_artifacts):
    """The platform (synthetic) datasets and the uploaded external ones are
    reported through distinct surfaces - no duplicate registry."""
    research_dataset_service.upload_dataset(
        db_session, name="External India thing (test)", domain="other",
        filename="x.csv", content=b"a,b\n1,2\n3,4\n",
        source="External Benchmark - India (data_type=real)", license="GODL-India",
    )
    body = client.get(
        "/api/v1/research/datasets",
        headers={"X-Research-Token": get_settings().research_console_token},
    ).json()
    assert set(body.keys()) == {"platform", "uploaded"}
    assert any(d["evidence_level"] == "SYNTHETIC" for d in body["platform"])
    assert any("External Benchmark" in (d["source"] or "") for d in body["uploaded"])
