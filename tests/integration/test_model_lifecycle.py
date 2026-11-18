"""Model lifecycle: versioned immutable artifacts, candidate -> validated -> active, recorded promotion, rollback.

Small real artifacts (a tiny scikit-learn model fitted on the feature contract's columns) in a temporary directory; nothing touches the
real ``models/`` registry or any production artifact."""
import json
from pathlib import Path

import joblib
import numpy as np
import pytest
from sklearn.linear_model import LinearRegression, LogisticRegression

from app.core.errors import ValidationFailedError
from app.models.ml_model import MLModel
from app.services import model_lifecycle_service as life
from app.services import model_registry_service as reg
from ml.features.churn_features import FEATURE_COLUMNS as CHURN_COLS
from ml.features.forecasting_features import FEATURE_COLUMNS as FC_COLS
from ml.pipeline import registry as file_registry

GOOD_FC = {"mae": 10.0, "rmse": 14.0, "mape": 8.0, "val_mae": 11.0, "val_baseline_mae": 20.0, "baseline_mae": 21.0}


def _fc_model(tmp_path: Path, name: str) -> str:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(60, len(FC_COLS)))
    path = tmp_path / f"{name}.joblib"
    joblib.dump(LinearRegression().fit(X, X[:, 0] * 3 + 5), path)
    return str(path)


def _churn_model(tmp_path: Path, name: str) -> str:
    rng = np.random.default_rng(1)
    X = rng.normal(size=(120, len(CHURN_COLS)))
    path = tmp_path / f"{name}.joblib"
    joblib.dump(LogisticRegression().fit(X, (X[:, 0] > 0).astype(int)), path)
    return str(path)


def _applicability(task, dataset):
    prov = "synthetic_platform" if dataset.startswith("platform-") else "uploaded_dataset"
    return {"source": "recorded", "provenance": prov, "target": "units_sold" if task == "forecasting" else "churned",
            "target_unit": "units per series per day" if task == "forecasting" else "binary label",
            "aggregation": "per_series_daily" if task == "forecasting" else "per_customer_snapshot", "population": f"test population {dataset}",
            "business_id": None, "label_provenance_observed": False}


def _row(db, tmp_path, name="sales_forecast_linear", version="v1", status="candidate", metrics=None, dataset="upload:abc:v1",
         feature_version="forecasting_v1", task="forecasting", make=_fc_model, path=None, meta=None, applicability="recorded"):
    life = {"run_metadata": meta} if meta else {}
    if applicability == "recorded":
        life["applicability"] = _applicability(task, dataset)
    row = MLModel(model_name=name, model_type=f"{task}_linear", version=version, dataset_version=dataset, feature_version=feature_version,
                  parameters_json={}, metrics_json=metrics if metrics is not None else dict(GOOD_FC), model_path=path or make(tmp_path, f"{name}_{version}"),
                  status=status, task=task, lifecycle_json=life or None)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ------------------------------------------------------------------ registry: immutable, atomic, new version per run
def test_a_version_is_never_overwritten_and_the_next_version_is_allocated(tmp_path, monkeypatch):
    monkeypatch.setattr(file_registry, "MODELS_ROOT", tmp_path)
    kw = dict(model_name="m", model_type="t", dataset_version="d", feature_version="f", parameters={}, metrics={}, random_seed=1)
    file_registry.save_model_artifact(model={"a": 1}, version="v1", **kw)
    assert file_registry.next_version("m") == "v2"
    with pytest.raises(file_registry.ArtifactExistsError):
        file_registry.save_model_artifact(model={"a": 2}, version="v1", **kw)
    assert joblib.load(tmp_path / "m" / "v1" / "model.joblib") == {"a": 1}  # the original artifact is intact
    file_registry.save_model_artifact(model={"a": 3}, version=file_registry.next_version("m"), **kw)
    assert file_registry.next_version("m") == "v3"
    assert [json.loads(line)["version"] for line in (tmp_path / "registry_index.jsonl").read_text().splitlines()] == ["v1", "v2"]


def test_an_interrupted_write_leaves_no_artifact_and_no_index_line(tmp_path, monkeypatch):
    monkeypatch.setattr(file_registry, "MODELS_ROOT", tmp_path)

    def boom(obj, f):
        f.write(b"partial")
        raise RuntimeError("disk full")

    monkeypatch.setattr(file_registry.joblib, "dump", boom)
    with pytest.raises(RuntimeError):
        file_registry.save_model_artifact(model=object(), model_name="m", model_type="t", version="v1", dataset_version="d",
                                          feature_version="f", parameters={}, metrics={}, random_seed=1)
    assert not (tmp_path / "m" / "v1" / "model.joblib").exists()
    assert not list((tmp_path / "m" / "v1").glob("*.tmp"))
    assert not (tmp_path / "registry_index.jsonl").exists()


# ------------------------------------------------------------------ sync: registering is not deploying
def _write_index(tmp_path, entries):
    p = tmp_path / "registry_index.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return p


def _entry(tmp_path, version, name="sales_forecast_linear", metrics=None):
    return {"model_name": name, "model_type": "forecasting_linear", "version": version, "dataset_version": "platform-forecasting-v1",
            "feature_version": "forecasting_v1", "parameters": {}, "metrics": metrics or dict(GOOD_FC),
            "artifact_path": _fc_model(tmp_path, f"{name}_{version}"), "trained_at": "2026-10-15T00:00:00+00:00", "random_seed": 42}


def test_first_version_is_bootstrapped_and_a_newer_version_is_only_a_candidate(db_session, tmp_path):
    idx = _write_index(tmp_path, [_entry(tmp_path, "v1")])
    rows = reg.sync_from_file_registry(db_session, idx)
    assert [(r.version, r.status) for r in rows] == [("v1", "active")]
    ev = life.history(db_session, model_name="sales_forecast_linear")
    assert [e.event for e in ev] == ["registered", "bootstrap_activation"] and ev[-1].actor == "system:sync"

    idx = _write_index(tmp_path, [_entry(tmp_path, "v1"), _entry(tmp_path, "v2")])
    reg.sync_from_file_registry(db_session, idx)
    status = {m.version: m.status for m in reg.list_models(db_session)}
    assert status == {"v1": "active", "v2": "candidate"}            # training a newer version did NOT deploy it
    events_after = len(life.history(db_session, model_name="sales_forecast_linear"))
    reg.sync_from_file_registry(db_session, idx)                       # idempotent: nothing changes, nothing is logged twice
    assert {m.version: m.status for m in reg.list_models(db_session)} == status
    assert len(life.history(db_session, model_name="sales_forecast_linear")) == events_after


def test_a_torn_index_line_does_not_break_the_sync(db_session, tmp_path):
    p = _write_index(tmp_path, [_entry(tmp_path, "v1")])
    with open(p, "a") as f:
        f.write('{"model_name": "sales_forecast_linear", "vers')
    assert [r.version for r in reg.sync_from_file_registry(db_session, p)] == ["v1"]


# ------------------------------------------------------------------ validation
def test_a_good_candidate_validates_with_its_warnings_recorded(db_session, tmp_path):
    row = _row(db_session, tmp_path, dataset="platform-forecasting-v1", meta={"splits": {"train": {"rows": 5000}}})
    res = life.validate_candidate(db_session, str(row.id), actor="admin@x")
    assert res["passed"] is True and res["status"] == "validated"
    assert "trained_on_real_business_data" in res["warnings"]               # synthetic training data: shown, not blocking
    assert db_session.get(MLModel, row.id).lifecycle_json["validation"]["validated_by"] == "admin@x"


@pytest.mark.parametrize("mutate,failing", [
    ({"metrics": {"mae": 10.0, "rmse": 14.0}}, "validation_metrics_present"),                                   # no validation metrics
    ({"metrics": {**GOOD_FC, "val_mae": 25.0}}, "beats_naive_baseline_on_validation"),                          # worse than naive
    ({"metrics": {k: v for k, v in GOOD_FC.items() if k != "val_baseline_mae"}}, "beats_naive_baseline_on_validation"),
    ({"feature_version": "forecasting_v0"}, "feature_version_current"),
    ({"dataset": ""}, "dataset_version_recorded"),
    ({"meta": {"splits": {"train": {"rows": 40}}}}, "minimum_training_rows"),
])
def test_blocking_checks_reject_a_candidate(db_session, tmp_path, mutate, failing):
    row = _row(db_session, tmp_path, **mutate)
    res = life.validate_candidate(db_session, str(row.id), actor="admin@x")
    assert res["passed"] is False and res["status"] == "rejected"
    assert failing in [c["name"] for c in res["checks"] if c["blocking"] and not c["passed"]]
    with pytest.raises(ValidationFailedError, match="validation"):
        life.promote(db_session, str(row.id), "admin@x", "because")      # a rejected model can never be promoted


def test_a_candidate_without_a_recorded_applicability_cannot_be_validated(db_session, tmp_path):
    """Loading and predicting is not proof of applicability: target, units, aggregation, population and provenance must have been recorded."""
    row = _row(db_session, tmp_path, applicability=None)            # an inferred record is not evidence
    res = life.validate_candidate(db_session, str(row.id), actor="a")
    assert res["passed"] is False and res["status"] == "rejected"
    failed = {c["name"]: c for c in res["checks"] if not c["passed"] and c["blocking"]}
    assert "applicability_recorded" in failed and "retrain" in failed["applicability_recorded"]["detail"]


def test_a_synthetic_trained_model_may_validate_but_is_never_eligible_for_business_use(db_session, tmp_path):
    from app.services import model_applicability_service as applic

    row = _row(db_session, tmp_path, dataset="platform-forecasting-v1", meta={"splits": {"train": {"rows": 5000}}})
    res = life.validate_candidate(db_session, str(row.id), actor="a")
    assert res["passed"] is True
    a = applic.describe(row)
    assert a["eligible_for"] == {"business_level_forecast": False, "price_scenarios": False, "customer_scoring": False}
    assert a["eligible_for_production_use"] is False and any("synthetic" in r for r in a["reasons"])
    assert any(c["name"] == "eligible_for_production_use" and not c["passed"] and not c["blocking"] for c in res["checks"])


def test_a_bootstrap_activated_model_is_never_labelled_validated(db_session, tmp_path):
    idx = _write_index(tmp_path, [_entry(tmp_path, "v1")])
    (row,) = reg.sync_from_file_registry(db_session, idx)
    assert row.status == "active" and row.validation_status == "not_validated_bootstrap"
    life.validate_candidate(db_session, str(row.id), actor="a")          # checks run, but the legacy artifact has no recorded applicability
    db_session.refresh(row)
    assert row.status == "active" and row.validation_status == "rejected"   # state untouched; the verdict is honest


def test_a_corrupt_or_missing_artifact_is_rejected(db_session, tmp_path):
    bad = tmp_path / "bad.joblib"
    bad.write_bytes(b"not a model")
    row = _row(db_session, tmp_path, path=str(bad))
    res = life.validate_candidate(db_session, str(row.id), actor="a")
    assert res["status"] == "rejected" and "artifact_loads" in [c["name"] for c in res["checks"] if not c["passed"]]
    gone = _row(db_session, tmp_path, version="v2", path=str(tmp_path / "missing.joblib"))
    assert life.validate_candidate(db_session, str(gone.id), actor="a")["status"] == "rejected"


def test_churn_candidates_need_a_validation_auc_and_carry_the_label_warning(db_session, tmp_path):
    ok = _row(db_session, tmp_path, name="churn_logistic_regression", task="churn", feature_version="churn_v1", make=_churn_model,
              metrics={"roc_auc": 0.78, "val_roc_auc": 0.77}, dataset="platform-churn-v1", meta={"label_provenance": "synthetic"})
    res = life.validate_candidate(db_session, str(ok.id), actor="a")
    assert res["passed"] and {"trained_on_real_business_data", "probability_semantics"} <= set(res["warnings"])
    weak = _row(db_session, tmp_path, name="churn_random_forest", task="churn", feature_version="churn_v1", make=_churn_model,
                metrics={"roc_auc": 0.78, "val_roc_auc": 0.55})
    assert life.validate_candidate(db_session, str(weak.id), actor="a")["status"] == "rejected"


def test_regression_against_the_active_model_blocks_only_when_the_data_is_comparable(db_session, tmp_path):
    _row(db_session, tmp_path, version="v1", status="active", dataset="upload:A:v1", metrics={**GOOD_FC, "val_mae": 10.0})
    worse_same = _row(db_session, tmp_path, version="v2", dataset="upload:A:v1", metrics={**GOOD_FC, "val_mae": 12.0})   # 20% worse, same data
    assert life.validate_candidate(db_session, str(worse_same.id), actor="a")["status"] == "rejected"
    worse_other = _row(db_session, tmp_path, version="v3", dataset="upload:B:v1", metrics={**GOOD_FC, "val_mae": 12.0})  # different data
    res = life.validate_candidate(db_session, str(worse_other.id), actor="a")
    assert res["passed"] is True
    assert any(c["name"] == "no_regression_vs_active" and "NOT comparable" in c["detail"] for c in res["checks"])


# ------------------------------------------------------------------ promotion and rollback
def test_promotion_is_explicit_recorded_and_atomic(db_session, tmp_path):
    v1 = _row(db_session, tmp_path, version="v1", status="active")
    v2 = _row(db_session, tmp_path, version="v2")
    with pytest.raises(ValidationFailedError, match="validation"):
        life.promote(db_session, str(v2.id), "admin@x", "go")                     # not validated yet
    life.validate_candidate(db_session, str(v2.id), actor="admin@x")
    with pytest.raises(ValidationFailedError, match="reason"):
        life.promote(db_session, str(v2.id), "admin@x", "  ")
    promoted = life.promote(db_session, str(v2.id), "admin@x", "beats v1 on the new upload")
    assert promoted.status == "active" and promoted.promoted_at
    statuses = {m.version: m.status for m in reg.list_models(db_session)}
    assert statuses == {"v1": "archived", "v2": "active"}                     # exactly one active
    ev = [e for e in life.history(db_session, model_name="sales_forecast_linear") if e.event == "promoted"][0]
    assert ev.actor == "admin@x" and ev.reason == "beats v1 on the new upload" and ev.details_json["replaced"] == ["v1"]
    assert db_session.get(MLModel, v1.id).status == "archived"


def test_rollback_restores_the_previous_version_and_refuses_unsafe_cases(db_session, tmp_path):
    v1 = _row(db_session, tmp_path, version="v1")
    life._event(db_session, v1, "bootstrap_activation", "system:sync", "first", "candidate", "active")
    v1.status = "active"
    db_session.commit()
    v2 = _row(db_session, tmp_path, version="v2")
    life.validate_candidate(db_session, str(v2.id), actor="a")
    life.promote(db_session, str(v2.id), "a", "newer data")
    with pytest.raises(ValidationFailedError, match="reason"):
        life.rollback(db_session, "sales_forecast_linear", "a", "")
    restored = life.rollback(db_session, "sales_forecast_linear", "ops@x", "v2 forecasts look wrong in production")
    assert restored.version == "v1" and restored.status == "active"
    assert {m.version: m.status for m in reg.list_models(db_session)} == {"v1": "active", "v2": "archived"}
    assert [e.event for e in life.history(db_session, model_name="sales_forecast_linear")][-2:] == ["rolled_back", "rolled_back"]
    # nothing earlier than v1 exists -> refused, state unchanged
    with pytest.raises(ValidationFailedError, match="nothing to roll back"):
        life.rollback(db_session, "sales_forecast_linear", "ops@x", "again")
    assert {m.version: m.status for m in reg.list_models(db_session)} == {"v1": "active", "v2": "archived"}


def test_rollback_refuses_a_previous_artifact_that_no_longer_loads(db_session, tmp_path):
    v1 = _row(db_session, tmp_path, version="v1")
    life._event(db_session, v1, "bootstrap_activation", "system:sync", "first", "candidate", "active")
    v1.status = "active"
    db_session.commit()
    v2 = _row(db_session, tmp_path, version="v2")
    life.validate_candidate(db_session, str(v2.id), actor="a")
    life.promote(db_session, str(v2.id), "a", "newer")
    Path(v1.model_path).unlink()
    with pytest.raises(ValidationFailedError, match="cannot be loaded"):
        life.rollback(db_session, "sales_forecast_linear", "ops@x", "undo")
    assert db_session.get(MLModel, v2.id).status == "active"


# ------------------------------------------------------------------ API access
def test_lifecycle_endpoints_are_admin_only(client):
    for method, path, body in (("post", "/api/v1/research/models/x/validate", None), ("post", "/api/v1/research/models/x/promote", {"reason": "r"}),
                               ("post", "/api/v1/research/models/rollback", {"model_name": "m", "reason": "r"}),
                               ("get", "/api/v1/research/models/x/history", None)):
        r = getattr(client, method)(path, json=body) if body is not None else getattr(client, method)(path)
        assert r.status_code in (401, 403), (path, r.status_code)


# ------------------------------------------------------------------ artifact integrity
def test_validation_pins_the_artifact_hash_and_labels_a_late_pin(db_session, tmp_path):
    from app.services import model_lifecycle_service as svc

    row = _row(db_session, tmp_path)                                  # a legacy row: no hash recorded at registration
    out = svc.validate_candidate(db_session, row.id, "admin")
    chk = next(c for c in out["checks"] if c["name"] == "artifact_integrity")
    assert chk["passed"] and chk["blocking"] is False and "cannot prove" in chk["detail"]
    art = db_session.get(MLModel, row.id).lifecycle_json["artifact"]
    assert art["basis"] == "pinned_at_validation" and len(art["sha256"]) == 64


def test_a_swapped_artifact_blocks_validation_and_promotion(db_session, tmp_path):
    from app.services import model_lifecycle_service as svc

    row = _row(db_session, tmp_path)
    svc.record_artifact(row, "at_registration", "system:test")
    db_session.commit()
    assert svc.validate_candidate(db_session, row.id, "admin")["passed"] is True
    path = Path(row.model_path)
    joblib.dump({"swapped": True}, path)                              # same path, different bytes, after validation
    with pytest.raises(Exception, match="cannot be promoted: the artifact file changed"):
        svc.promote(db_session, row.id, "admin", "ship it")
    assert db_session.get(MLModel, row.id).status == "validated"      # not activated
    again = svc.validate_candidate(db_session, row.id, "admin")
    assert again["passed"] is False and any(c["name"] == "artifact_integrity" and not c["passed"] for c in again["checks"])


def test_rollback_refuses_a_target_whose_artifact_changed(db_session, tmp_path):
    from app.services import model_lifecycle_service as svc

    v1 = _row(db_session, tmp_path, version="v1")
    life._event(db_session, v1, "bootstrap_activation", "system:sync", "first", "candidate", "active")
    v1.status = "active"
    svc.record_artifact(v1, "at_registration", "system:test")
    db_session.commit()
    v2 = _row(db_session, tmp_path, version="v2")
    svc.validate_candidate(db_session, str(v2.id), actor="a")
    svc.promote(db_session, v2.id, "admin", "newer")
    joblib.dump({"swapped": True}, Path(v1.model_path))
    with pytest.raises(Exception, match="cannot be restored"):
        svc.rollback(db_session, v1.model_name, "admin", "back")
    assert db_session.get(MLModel, v2.id).status == "active"
