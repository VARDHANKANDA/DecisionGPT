"""Research Console -> Model Performance: the forecast-accuracy summary (WAPE, MAE, RMSE, change vs baseline) and the safe re-evaluation action.

The summary shows only HELD-OUT TEST figures, labels where each came from, and says "not available" - never a made-up number - when a figure was not recorded,
could not be reproduced, or is undefined. The re-evaluation re-scores a stored artifact on its test block and is accepted only if it reproduces the metrics
recorded at training."""
import numpy as np
import pandas as pd
import pytest

from app.core.config import get_settings
from app.models.ml_model import MLModel
from app.services import model_reevaluation_service as R
from tests.admin_support import admin_token
from tests.api.test_platform_api import _owner, auth_on  # noqa: F401  (auth_on is a fixture)

PERF = "/api/v1/research/model-performance"
RUN_ONE = "/api/v1/research/evaluation/models/{}/run"
RUN_PENDING = "/api/v1/research/evaluation/models/run-pending"


def _h():
    return {"X-Research-Token": get_settings().research_console_token}


def _model(db, name, mtype, metrics, version="v1", dataset="platform_v1", path=None):
    m = MLModel(model_name=name, model_type=mtype, version=version, dataset_version=dataset, feature_version="forecasting_v1", metrics_json=metrics,
                model_path=path or f"models/{name}/{version}/model.joblib", status="experimental", task="forecasting" if mtype.startswith("forecasting") else "churn")
    db.add(m)
    db.commit()
    return m


RECORDED = {"mae": 4.0, "rmse": 6.0, "mape": 22.0, "wape": 0.25, "bias": -0.5, "n_eval": 400, "n_zero_actual": 0, "n_invalid": 0, "baseline_mae": 5.0}
OLD = {"mae": 4.0, "rmse": 6.0, "mape": 22.0}


def _rows(client):
    body = client.get(PERF, headers=_h()).json()
    return {f'{r["model_name"]} {r["version"]}': r for r in body["evaluation_summary"]["rows"]}, body


# ---------------------------------------------------------------- a synthetic dataset the real training functions can use (no model is trained on it)
def _frame(days=160):
    d = pd.date_range("2024-01-01", periods=days, freq="D")
    rng = np.random.default_rng(3)
    units = np.maximum(0, 50 + 12 * np.sin(np.arange(days) / 7 * 2 * np.pi) + rng.normal(0, 4, days)).round()
    return pd.DataFrame({"series_id": "S1", "date": d.strftime("%Y-%m-%d"), "units_sold": units, "price": 10.0, "marketing_spend": 5.0, "promotion_flag": 0})


class _Pred:
    """A stand-in stored model: one-step forecast = yesterday's value x 1.05 + 1."""

    def predict(self, X):
        return X["lag_1"].to_numpy() * 1.05 + 1.0


def _truth():
    """What an independent hand computation of the test block gives for the stand-in model and for the baseline (yesterday's value)."""
    from ml.features.forecasting_features import build_forecasting_features
    from ml.pipeline.preprocessing import chronological_split, clean_dataframe

    feat = build_forecasting_features(clean_dataframe(_frame(), date_columns=["date"]))
    _tr, _va, te = chronological_split(feat, "date")
    y, lag = te["units_sold"].to_numpy(float), te["lag_1"].to_numpy(float)
    p = lag * 1.05 + 1.0
    return {"y": y, "p": p, "lag": lag, "n": len(te), "start": str(pd.to_datetime(te["date"]).min().date()), "end": str(pd.to_datetime(te["date"]).max().date()),
            "mae": float(np.mean(np.abs(p - y))), "rmse": float(np.sqrt(np.mean((p - y) ** 2))), "wape": float(np.abs(p - y).sum() / np.abs(y).sum()),
            "base_wape": float(np.abs(lag - y).sum() / np.abs(y).sum()), "base_mae": float(np.mean(np.abs(lag - y)))}


@pytest.fixture()
def synthetic(monkeypatch):
    monkeypatch.setattr(R, "_dataframe", lambda db, m: (_frame(), "synthetic frame (unit test)"))
    monkeypatch.setattr(R, "_predictor", lambda m: None if m.model_type.endswith("naive") else _Pred())
    return _truth()


def _stored_metrics_for(t):
    from ml.evaluation import metrics as M

    return {"mae": M.mae(t["y"], t["p"]), "rmse": M.rmse(t["y"], t["p"]), "mape": M.mape(t["y"], t["p"])}


# ---------------------------------------------------------------- access
def test_the_run_actions_need_research_credentials(client, db_session):
    m = _model(db_session, "sales_forecast_linear", "forecasting_linear", OLD)
    assert client.post(RUN_ONE.format(m.id)).status_code == 403
    assert client.post(RUN_PENDING).status_code == 403


def test_an_sme_account_cannot_run_an_evaluation(client, db_session, auth_on):  # noqa: F811
    _, h = _owner(client, "sme-eval@example.com", "Shop")
    assert client.post(RUN_PENDING, headers=h).status_code == 403
    admin = admin_token(client, db_session, "admin-eval@example.com")
    assert client.post(RUN_PENDING, headers={"Authorization": f"Bearer {admin}"}).status_code == 200


# ---------------------------------------------------------------- the summary: schema, units, provenance
def test_the_summary_returns_every_documented_field_for_a_recorded_model(client, db_session):
    _model(db_session, "sales_forecast_xgboost", "forecasting_xgboost", RECORDED, dataset="platform_v1")
    rows, body = _rows(client)
    r = rows["sales_forecast_xgboost v1"]
    assert set(r) >= {"model_id", "model_name", "version", "model_status", "dataset_version", "evaluation_status", "evaluation_kind", "evaluation_reason", "evaluated_at", "can_run",
                      "test_window", "n_eval", "horizon", "baseline_name", "method", "wape", "mae", "rmse", "baseline_wape", "wape_vs_baseline", "mae_vs_baseline", "verdict_wape"}
    assert r["evaluation_status"] == "evaluated" and r["evaluation_kind"] == "recorded_at_training" and r["can_run"] is False
    assert r["wape"]["display"] == "25.0%" and r["mae"]["display"] == "4.00 units/day" and r["rmse"]["display"] == "6.00 units/day"
    assert r["n_eval"] == 400 and r["dataset_version"] == "platform_v1" and r["horizon"] == "1 day ahead" and r["baseline_name"] == "Yesterday's value (1-day lag)"
    assert body["evaluation_summary"]["basis"] and {d["key"] for d in body["evaluation_summary"]["definitions"]} >= {"wape", "mae", "rmse", "wape_vs_baseline"}


def test_the_relative_wape_change_is_not_invented_when_the_baseline_wape_was_never_recorded(client, db_session):
    _model(db_session, "sales_forecast_xgboost", "forecasting_xgboost", RECORDED)
    r = _rows(client)[0]["sales_forecast_xgboost v1"]
    assert r["wape_vs_baseline"]["status"] != "available" and r["wape_vs_baseline"]["value"] is None and r["wape_vs_baseline"]["reason"]
    assert r["baseline_wape"]["status"] != "available"


def test_an_older_model_is_pending_with_no_wape_and_offers_the_evaluation_action(client, db_session):
    _model(db_session, "sales_forecast_linear", "forecasting_linear", OLD)
    r = _rows(client)[0]["sales_forecast_linear v1"]
    assert r["evaluation_status"] == "pending" and r["can_run"] is True and r["wape"]["status"] != "available" and r["wape"]["value"] is None
    assert r["n_eval"] is None and r["test_window"] is None and r["evaluation_reason"]
    assert r["mae"]["display"] == "4.00 units/day"                          # the recorded test MAE is still shown


def test_validation_or_training_figures_are_never_shown_as_test_figures(client, db_session):
    _model(db_session, "sales_forecast_xgboost", "forecasting_xgboost", {"mae": 4.0, "rmse": 6.0, "mape": 22.0, "val_mae": 3.5, "val_rmse": 5.0, "val_wape": 0.2, "train_mae": 1.0, "train_wape": 0.05})
    r = _rows(client)[0]["sales_forecast_xgboost v1"]
    assert r["wape"]["value"] is None and r["wape"]["status"] != "available"        # val_wape / train_wape never fill the test WAPE
    assert r["mae"]["display"] == "4.00 units/day" and r["rmse"]["display"] == "6.00 units/day"
    assert r["evaluation_status"] == "pending"


def test_the_naive_model_is_not_compared_with_itself(client, db_session):
    _model(db_session, "sales_forecast_naive", "forecasting_naive", RECORDED)
    r = _rows(client)[0]["sales_forecast_naive v1"]
    assert r["is_baseline_model"] is True and r["wape_vs_baseline"]["kind"] == "not_applicable" and r["verdict_wape"] is None


def test_no_models_gives_an_empty_summary_not_fabricated_rows(client, db_session):
    body = client.get(PERF, headers=_h()).json()
    assert body["evaluation_summary"]["rows"] == [] and body["evaluation_summary"]["basis"]


def test_no_model_is_named_best_across_different_datasets(client, db_session):
    _model(db_session, "sales_forecast_linear", "forecasting_linear", RECORDED, dataset="platform_v1")
    _model(db_session, "sales_forecast_xgboost", "forecasting_xgboost", {**RECORDED, "mae": 1.0}, dataset="upload:abc:v1")
    s = client.get(PERF, headers=_h()).json()["summary"]
    assert s["best_forecasting"] is None and "different datasets" in s["best_forecasting_note"]


def test_a_best_model_is_named_only_within_one_dataset(client, db_session):
    _model(db_session, "sales_forecast_linear", "forecasting_linear", RECORDED, dataset="platform_v1")
    _model(db_session, "sales_forecast_xgboost", "forecasting_xgboost", {**RECORDED, "mae": 1.0}, dataset="platform_v1")
    s = client.get(PERF, headers=_h()).json()["summary"]
    assert s["best_forecasting"]["model"] == "sales_forecast_xgboost v1" and s["best_forecasting"]["metric"] == "mae" and s["best_forecasting_note"] is None


# ---------------------------------------------------------------- the safe re-evaluation action
def test_rescoring_a_stored_model_reproduces_the_hand_computed_test_figures(client, db_session, synthetic):
    t = synthetic
    m = _model(db_session, "sales_forecast_linear", "forecasting_linear", _stored_metrics_for(t), dataset="synthetic_v1")
    resp = client.post(RUN_ONE.format(m.id), headers=_h())
    assert resp.status_code == 200 and resp.json()["status"] == "evaluated"
    r = _rows(client)[0]["sales_forecast_linear v1"]
    assert r["evaluation_status"] == "evaluated" and r["evaluation_kind"] == "re_evaluated" and r["can_run"] is False
    assert r["n_eval"] == t["n"] and r["test_window"] == [t["start"], t["end"]]                       # evaluation period and sample size
    assert r["wape"]["value"] == pytest.approx(100 * t["wape"], rel=1e-5) and r["wape"]["display"] == f'{100 * t["wape"]:.1f}%'
    assert r["mae"]["value"] == pytest.approx(t["mae"], rel=1e-5) and r["rmse"]["value"] == pytest.approx(t["rmse"], rel=1e-5)
    assert r["baseline_wape"]["value"] == pytest.approx(100 * t["base_wape"], rel=1e-5)
    assert r["wape_vs_baseline"]["value"] == pytest.approx(100 * (t["base_wape"] - t["wape"]) / t["base_wape"], rel=1e-5)   # 100 x (baseline - model) / baseline
    assert r["baseline_name"] == "Yesterday's value (1-day lag)" and r["horizon"] == "1 day ahead" and r["method"]
    # the recorded training metrics are untouched and the model row only gained a lifecycle record
    db_session.expire_all()
    again = db_session.get(MLModel, m.id)
    assert again.metrics_json == _stored_metrics_for(t) and again.lifecycle_json["reevaluation"]["trusted"] is True


def test_a_rescoring_that_does_not_reproduce_the_recorded_metrics_is_failed_and_shows_no_figure(client, db_session, synthetic):
    stored = _stored_metrics_for(synthetic)
    stored["mae"] *= 1.10                                                                                # the artifact/dataset is not the one that was evaluated
    m = _model(db_session, "sales_forecast_linear", "forecasting_linear", stored, dataset="synthetic_v1")
    out = client.post(RUN_ONE.format(m.id), headers=_h()).json()
    assert out["status"] == "failed" and "Verification failed" in out["reason"] and out["verification"]["stored_metrics_matched"] is False
    r = _rows(client)[0]["sales_forecast_linear v1"]
    assert r["evaluation_status"] == "failed" and r["wape"]["value"] is None and r["wape_vs_baseline"]["value"] is None and r["baseline_wape"]["value"] is None
    db_session.expire_all()
    rec = db_session.get(MLModel, m.id).lifecycle_json["reevaluation"]
    assert rec["trusted"] is False and rec["metrics"] == {} and rec["improvement"] == {}                  # nothing untrusted is kept as a number


def test_a_missing_dataset_or_artifact_is_unavailable_with_the_reason(client, db_session, monkeypatch, synthetic):
    m = _model(db_session, "sales_forecast_linear", "forecasting_linear", _stored_metrics_for(synthetic))
    monkeypatch.setattr(R, "_predictor", lambda mm: (_ for _ in ()).throw(R.Unavailable("The stored artifact file is missing (models/x).")))
    out = client.post(RUN_ONE.format(m.id), headers=_h()).json()
    assert out["status"] == "unavailable" and "artifact" in out["reason"]
    r = _rows(client)[0]["sales_forecast_linear v1"]
    assert r["evaluation_status"] == "unavailable" and r["wape"]["value"] is None and r["can_run"] is True
    monkeypatch.setattr(R, "_dataframe", lambda db, mm: (_ for _ in ()).throw(R.Unavailable("The dataset cannot be rebuilt.")))
    assert client.post(RUN_ONE.format(m.id), headers=_h()).json()["reason"] == "The dataset cannot be rebuilt."


def test_the_naive_model_needs_no_artifact_and_has_no_improvement_over_itself(client, db_session, synthetic):
    t = synthetic
    from ml.evaluation import metrics as M

    stored = {"mae": M.mae(t["y"], t["lag"]), "rmse": M.rmse(t["y"], t["lag"]), "mape": M.mape(t["y"], t["lag"])}
    m = _model(db_session, "sales_forecast_naive", "forecasting_naive", stored, dataset="synthetic_v1")
    assert client.post(RUN_ONE.format(m.id), headers=_h()).json()["status"] == "evaluated"
    r = _rows(client)[0]["sales_forecast_naive v1"]
    assert r["wape"]["value"] == pytest.approx(100 * t["base_wape"], rel=1e-5) and r["wape_vs_baseline"]["kind"] == "not_applicable"


def test_run_pending_evaluates_each_pending_model_once_and_never_retries_silently(client, db_session, synthetic):
    ok = _model(db_session, "sales_forecast_linear", "forecasting_linear", _stored_metrics_for(synthetic), dataset="synthetic_v1")
    bad = _model(db_session, "sales_forecast_xgboost", "forecasting_xgboost", {**_stored_metrics_for(synthetic), "mae": 99.0}, dataset="synthetic_v1")
    _model(db_session, "sales_forecast_naive", "forecasting_naive", RECORDED)                              # already has a recorded WAPE: not pending
    out = client.post(RUN_PENDING, headers=_h()).json()
    assert out["attempted"] == 2 and out["evaluated"] == 1
    by = {r["model_id"]: r["status"] for r in out["results"]}
    assert by[ok.id] == "evaluated" and by[bad.id] == "failed"
    assert client.post(RUN_PENDING, headers=_h()).json()["attempted"] == 0                                 # a failed attempt is shown as failed, not retried behind the scenes


def test_a_classification_model_cannot_be_re_evaluated_here(client, db_session):
    c = _model(db_session, "churn_logistic_regression", "churn_logistic_regression", {"roc_auc": 0.8})
    assert client.post(RUN_ONE.format(c.id), headers=_h()).status_code in (400, 422)
    assert client.post(RUN_ONE.format("00000000-0000-0000-0000-000000000000"), headers=_h()).status_code == 404
