"""Production training/selection alignment: validation-based selection, WAPE, and run-metadata sidecars. All offline; artifacts go to a
temporary registry so the real ``models/`` directory and experiment results are untouched."""
import json

import numpy as np
import pytest

from ml.evaluation.metrics import regression_metrics, wape
from ml.pipeline import registry
from ml.training import train_churn, train_forecasting


def test_wape_is_defined_scale_aware_and_never_a_fake_zero():
    assert wape(np.array([10, 10]), np.array([12, 8])) == pytest.approx(0.2)
    assert wape(np.zeros(3), np.ones(3)) is None
    assert "wape" not in regression_metrics(np.zeros(3), np.ones(3))      # omitted when undefined
    assert regression_metrics(np.array([4.0, 6.0]), np.array([5.0, 5.0]))["wape"] == pytest.approx(0.2)


@pytest.fixture()
def tmp_registry(tmp_path, monkeypatch):
    models = tmp_path / "models"
    models.mkdir()
    monkeypatch.setattr(registry, "MODELS_ROOT", models)
    monkeypatch.setattr(train_forecasting, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(train_churn, "RESULTS_DIR", tmp_path / "results")
    return models


def test_forecasting_run_records_validation_metrics_and_a_metadata_sidecar(tmp_registry):
    out = train_forecasting.run(random_seed=42)
    for k in ("naive", "linear", "xgboost"):
        m = out["results"][k]
        assert {"mae", "rmse", "mape", "val_mae", "val_rmse"} <= set(m)
    sidecar = json.loads((tmp_registry / "sales_forecast_xgboost" / "v1" / "run_metadata.json").read_text())
    assert sidecar["task"] == "forecasting" and len(sidecar["dataset_sha256"]) == 64 and sidecar["random_seed"] == 42
    assert {"train", "validation", "test"} <= set(sidecar["splits"]) and sidecar["git_revision"]
    assert sidecar["splits"]["train"]["last"] < sidecar["splits"]["validation"]["first"] <= sidecar["splits"]["validation"]["last"] < sidecar["splits"]["test"]["first"]
    assert sidecar["feature_contract"]["version"] == "forecasting_v1" and set(sidecar["feature_ranges"]) == set(sidecar["feature_contract"]["columns"])
    assert all(lo <= hi for lo, hi in sidecar["feature_ranges"].values())
    assert {"val_baseline_mae", "baseline_mae"} <= set(out["results"]["xgboost"])
    manifest = json.loads((tmp_registry / "sales_forecast_xgboost" / "v1" / "manifest.json").read_text())
    registry.ModelManifest(**manifest)  # the manifest format readers depend on is unchanged


def test_a_second_training_run_creates_a_new_version_and_leaves_the_first_untouched(tmp_registry):
    train_forecasting.run(random_seed=42)
    first = (tmp_registry / "sales_forecast_xgboost" / "v1" / "model.joblib").read_bytes()
    train_forecasting.run(random_seed=7)
    assert (tmp_registry / "sales_forecast_xgboost" / "v2" / "model.joblib").exists()
    assert (tmp_registry / "sales_forecast_xgboost" / "v1" / "model.joblib").read_bytes() == first
    versions = [json.loads(l)["version"] for l in (tmp_registry / "registry_index.jsonl").read_text().splitlines() if "sales_forecast_xgboost" in l]
    assert versions == ["v1", "v2"]


def test_churn_run_records_a_cv_validation_auc_without_changing_the_train_test_sizes(tmp_registry):
    out = train_churn.run(random_seed=42)
    assert out["train_rows"] == 4800 and out["test_rows"] == 1200  # the 80/20 split of the existing pipeline is preserved
    for k in ("logistic_regression", "random_forest", "xgboost"):
        m = out["results"][k]
        assert 0.5 < m["val_roc_auc"] < 1.0 and 0.5 < m["roc_auc"] < 1.0
        # decision threshold comes from out-of-fold training predictions; the test block is scored at it once
        assert 0.0 < m["val_threshold"] < 1.0 and 0.0 < m["pr_auc"] <= 1.0 and 0.0 <= m["ece"] < 0.5
        assert m["confusion_tp"] + m["confusion_fp"] + m["confusion_fn"] + m["confusion_tn"] == out["test_rows"]
        assert abs(m["prevalence_shift"]) < 0.05           # stratified split: prevalence is stable, so calibration is interpretable


class _M:
    def __init__(self, name, status, metrics):
        self.model_name, self.status, self.metrics_json = name, status, metrics


def test_selection_uses_validation_metrics_when_every_candidate_has_them(monkeypatch):
    from app.services import model_registry_service as svc

    cands = {"a": _M("a", "active", {"mae": 1.0, "val_mae": 5.0}), "b": _M("b", "active", {"mae": 2.0, "val_mae": 3.0})}
    monkeypatch.setattr(svc, "get_active_model", lambda db, name: cands.get(name))
    assert svc.select_best_model(None, ["a", "b"], "mae", True).model_name == "a"                         # legacy: test metric
    assert svc.select_best_model(None, ["a", "b"], "mae", True, validation_metric="val_mae").model_name == "b"  # validation metric
    cands["b"] = _M("b", "active", {"mae": 2.0})  # one candidate lacks a validation metric -> fall back for ALL (no mixed comparison)
    assert svc.select_best_model(None, ["a", "b"], "mae", True, validation_metric="val_mae").model_name == "a"


def test_forecast_and_digital_twin_share_one_selection_function():
    import inspect

    from app.analytics import digital_twin_service, forecast_service

    assert "forecast_service.select_forecast_model" in inspect.getsource(digital_twin_service)
    assert "validation_metric=\"val_mae\"" in inspect.getsource(forecast_service.select_forecast_model)
