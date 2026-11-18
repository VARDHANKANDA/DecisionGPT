"""Model lifecycle: candidate -> validated -> active (production), with a recorded actor and reason, and rollback.

Rules (docs/MODEL_LIFECYCLE.md):
* Training and registry sync never make a model ACTIVE, except the very first version of a model name when nothing is deployed
  (recorded as ``bootstrap_activation``; a deployment needs something to serve).
* A candidate becomes ``validated`` only if every blocking check passes; warnings (for example "trained on synthetic data only") are
  recorded and shown but do not block, because the project has no real-business data from which a stricter bar could be defined.
* Promotion is explicit: it needs a ``validated`` model, an actor and a reason, and it archives the previous active version in the same
  transaction so exactly one version per name is active.
* Rollback re-activates the version that was active before the current one, after checking that its artifact still loads.
* Every transition is appended to ``model_lifecycle_events``; nothing is deleted.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.models.common import utcnow
from app.models.ml_model import (
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    STATUS_CANDIDATE,
    STATUS_EXPERIMENTAL,
    STATUS_REJECTED,
    STATUS_VALIDATED,
    MLModel,
    ModelLifecycleEvent,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]

MIN_CHURN_AUC = 0.60  # a classifier barely above 0.5 is not worth deploying; the bar is deliberately modest and documented
REGRESSION_TOLERANCE = 0.05  # a candidate may be at most 5% worse than the active model on the same validation metric
MIN_TRAIN_ROWS = 200
CURRENT_FEATURE_VERSION = {"forecasting": "forecasting_v1", "churn": "churn_v1"}
CANDIDATE_STATES = {STATUS_CANDIDATE, STATUS_EXPERIMENTAL, STATUS_REJECTED, STATUS_VALIDATED, "registered"}


def task_of(model: MLModel) -> str:
    t = (model.task or model.model_type or "").lower()
    return "forecasting" if t.startswith(("forecast", "sales_forecast")) else "churn" if t.startswith("churn") else t


def _event(db: Session, model: MLModel, event: str, actor: str, reason: str | None, frm: str | None, to: str | None,
           details: dict | None = None) -> ModelLifecycleEvent:
    db.flush()  # make earlier unflushed events visible to the max(seq) read below
    seq = (db.execute(select(func.max(ModelLifecycleEvent.seq))).scalar() or 0) + 1
    row = ModelLifecycleEvent(seq=seq, model_id=str(model.id), model_name=model.model_name, version=model.version, event=event, from_status=frm,
                              to_status=to, actor=actor[:120], reason=(reason or None) and reason[:500], details_json=details or {})
    db.add(row)
    db.flush()
    return row


def history(db: Session, model_name: str | None = None, model_id: str | None = None) -> list[ModelLifecycleEvent]:
    stmt = select(ModelLifecycleEvent).order_by(ModelLifecycleEvent.seq)
    if model_name:
        stmt = stmt.where(ModelLifecycleEvent.model_name == model_name)
    if model_id:
        stmt = stmt.where(ModelLifecycleEvent.model_id == str(model_id))
    return list(db.execute(stmt).scalars())


# ------------------------------------------------------------------------------------------------ checks
def _check(name: str, ok: bool, detail: str, blocking: bool = True) -> dict[str, Any]:
    return {"name": name, "passed": bool(ok), "blocking": blocking, "detail": detail}


def artifact_sha256(model: MLModel) -> str | None:
    """sha256 of the stored artifact file, or None when the file is missing. Streams the file (artifacts can be large)."""
    import hashlib

    path = PROJECT_ROOT / (model.model_path or "")
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def record_artifact(model: MLModel, basis: str, actor: str) -> dict[str, Any] | None:
    """Pin the artifact's current hash on the model record (``lifecycle_json.artifact``). ``basis`` says when and why it was taken, so a
    pin taken after the fact is never presented as proof of what was trained."""
    digest = artifact_sha256(model)
    if digest is None:
        return None
    life = dict(model.lifecycle_json or {})
    life["artifact"] = {"sha256": digest, "basis": basis, "recorded_by": actor, "recorded_at": utcnow().isoformat()}
    model.lifecycle_json = life
    return life["artifact"]


def verify_artifact(model: MLModel) -> tuple[str, str]:
    """('ok' | 'mismatch' | 'missing_file' | 'not_recorded', detail). 'not_recorded' is a legacy model registered before hashes were kept."""
    rec = (model.lifecycle_json or {}).get("artifact") or {}
    current = artifact_sha256(model)
    if current is None:
        return "missing_file", f"artifact file {model.model_path!r} is missing"
    if not rec.get("sha256"):
        return "not_recorded", "no artifact hash was recorded for this version"
    if rec["sha256"] != current:
        return "mismatch", (f"the artifact file changed after it was recorded ({rec.get('basis')}, {rec.get('recorded_at')}): "
                            f"recorded {rec['sha256'][:12]}..., now {current[:12]}...")
    return "ok", f"sha256 {current[:12]}... matches the hash recorded {rec.get('basis')} ({rec.get('recorded_at')})"


def _contract_columns(task: str) -> list[str]:
    if task == "forecasting":
        from ml.features.forecasting_features import FEATURE_COLUMNS
    else:
        from ml.features.churn_features import FEATURE_COLUMNS
    return list(FEATURE_COLUMNS)


def _probe(task: str, cols: list[str]) -> pd.DataFrame:
    """One plausible row per column; used only to prove the artifact accepts the contract's columns in order and returns finite output."""
    plausible = {"lag_1": 10, "lag_7": 10, "rolling_mean_7": 10, "rolling_mean_28": 10, "day_of_week": 2, "is_weekend": 0, "month": 6, "price": 100.0,
                 "marketing_spend": 0.0, "promotion_flag": 0, "tenure_days": 400, "recency_days": 30, "frequency": 5, "avg_order_value": 500.0,
                 "monetary_value": 2500.0, "purchase_rate_per_year": 4.5, "recency_ratio": 0.07}
    return pd.DataFrame([{c: plausible.get(c, 1.0) for c in cols}])[cols]


def _active_peer(db: Session, model: MLModel) -> MLModel | None:
    return db.execute(select(MLModel).where(MLModel.model_name == model.model_name, MLModel.status == STATUS_ACTIVE,
                                            MLModel.id != model.id)).scalars().first()


def run_checks(db: Session, model: MLModel) -> list[dict[str, Any]]:
    task = task_of(model)
    m = model.metrics_json or {}
    life = model.lifecycle_json or {}
    meta = life.get("run_metadata") or {}
    checks: list[dict[str, Any]] = []

    # 1. the artifact loads and accepts the contract's columns
    path = PROJECT_ROOT / (model.model_path or "")
    loaded = None
    try:
        import joblib

        loaded = joblib.load(path)
        checks.append(_check("artifact_loads", True, f"loaded {model.model_path}"))
    except Exception as exc:  # noqa: BLE001 - any failure to load is a blocking result, not a crash
        checks.append(_check("artifact_loads", False, f"cannot load {model.model_path}: {type(exc).__name__}"))
    state, detail = verify_artifact(model)
    if state == "not_recorded":
        checks.append(_check("artifact_integrity", True, detail + "; the current hash is pinned when validation completes, so a later swap is "
                             "detected, but it cannot prove the file equals what training produced", blocking=False))
    else:
        checks.append(_check("artifact_integrity", state == "ok", detail))
    if task not in CURRENT_FEATURE_VERSION:
        checks.append(_check("task_supported", False, f"unsupported task {task!r}"))
        return checks
    cols = _contract_columns(task)
    if loaded is not None:
        try:
            frame = _probe(task, cols)
            out = loaded.predict_proba(frame)[:, 1] if task == "churn" else loaded.predict(frame)
            ok = bool(np.all(np.isfinite(np.asarray(out, dtype=float))))
            checks.append(_check("predicts_on_contract_columns", ok, "finite output on a probe row built from the current feature contract"))
        except Exception as exc:  # noqa: BLE001
            checks.append(_check("predicts_on_contract_columns", False, f"prediction failed: {type(exc).__name__}"))

    # 2. identity and feature version
    checks.append(_check("dataset_version_recorded", bool((model.dataset_version or "").strip()), f"dataset_version={model.dataset_version!r}"))
    checks.append(_check("feature_version_current", model.feature_version == CURRENT_FEATURE_VERSION[task],
                         f"model {model.feature_version!r} vs current {CURRENT_FEATURE_VERSION[task]!r}"))
    if model.features_json:
        checks.append(_check("feature_list_matches_contract", list(model.features_json) == cols, "stored feature list equals the contract (names and order)"))

    # 3. metrics on held-out data
    peer = _active_peer(db, model)
    if task == "forecasting":
        has_val = isinstance(m.get("val_mae"), (int, float))
        checks.append(_check("validation_metrics_present", has_val,
                             "val_mae recorded" if has_val else "no validation metrics: trained before they were recorded; retrain to create a new version"))
        if has_val and isinstance(m.get("val_baseline_mae"), (int, float)):
            checks.append(_check("beats_naive_baseline_on_validation", m["val_mae"] < m["val_baseline_mae"],
                                 f"val_mae {m['val_mae']:.4g} vs naive lag-1 {m['val_baseline_mae']:.4g} on the same validation block"))
        else:
            checks.append(_check("beats_naive_baseline_on_validation", False, "baseline metric missing: cannot show the model beats the naive forecast"))
        primary, lower_is_better = "val_mae", True
    else:
        v = m.get("val_roc_auc")
        checks.append(_check("validation_metrics_present", isinstance(v, (int, float)), "val_roc_auc recorded" if isinstance(v, (int, float))
                             else "no validation metrics: retrain to create a new version"))
        if isinstance(v, (int, float)):
            checks.append(_check("validation_auc_above_floor", v >= MIN_CHURN_AUC, f"val_roc_auc {v:.3f} vs floor {MIN_CHURN_AUC}"))
        if isinstance(m.get("roc_auc"), (int, float)):
            checks.append(_check("test_auc_above_floor", m["roc_auc"] >= MIN_CHURN_AUC, f"test roc_auc {m['roc_auc']:.3f} vs floor {MIN_CHURN_AUC}"))
        primary, lower_is_better = "val_roc_auc", False

    # 4. comparison with what is deployed (only when both were measured on the same data)
    if peer is not None and isinstance(m.get(primary), (int, float)) and isinstance((peer.metrics_json or {}).get(primary), (int, float)):
        same_data = peer.dataset_version == model.dataset_version
        a, b = m[primary], peer.metrics_json[primary]
        ok = a <= b * (1 + REGRESSION_TOLERANCE) if lower_is_better else a >= b * (1 - REGRESSION_TOLERANCE)
        detail = f"{primary}: candidate {a:.4g} vs active {peer.version} {b:.4g} (tolerance {REGRESSION_TOLERANCE:.0%})"
        if same_data:
            checks.append(_check("no_regression_vs_active", ok, detail))
        else:
            checks.append(_check("no_regression_vs_active", True, detail + f"; NOT comparable (datasets differ: {model.dataset_version!r} vs "
                                 f"{peer.dataset_version!r}); a person must judge this", blocking=False))
    elif peer is not None:
        checks.append(_check("no_regression_vs_active", True, f"active {peer.version} has no comparable {primary}; not compared", blocking=False))

    # 4b. applicability: what the model was trained for must be RECORDED (an inferred record is not evidence)
    from app.services import model_applicability_service as applic

    a = applic.describe(model)
    need = ("target", "target_unit", "aggregation", "population", "provenance")
    missing = [k for k in need if not a.get(k) or str(a.get(k)).startswith("not_recorded") or a.get(k) == "not recorded"]
    checks.append(_check("applicability_recorded", a.get("source") == "recorded" and not missing,
                         "target, units, aggregation, population and provenance were recorded at training time"
                         if a.get("source") == "recorded" and not missing
                         else f"applicability not recorded at training time (source={a.get('source')}; missing={missing}): retrain to create a new version"))
    if not a["eligible_for_production_use"]:
        checks.append(_check("eligible_for_production_use", False,
                             "not eligible for business-level production use: " + "; ".join(a["reasons"][:3]) + ". A promotion would make it the "
                             "reference model only; business forecasts do not use it.", blocking=False))

    # 5. data provenance and size
    rows = ((meta.get("splits") or {}).get("train") or {}).get("rows") if isinstance(meta.get("splits"), dict) else None
    if isinstance(rows, int):
        checks.append(_check("minimum_training_rows", rows >= MIN_TRAIN_ROWS, f"{rows} training rows (minimum {MIN_TRAIN_ROWS})"))
    else:
        checks.append(_check("minimum_training_rows", True, "training size not recorded in run metadata", blocking=False))
    synthetic = "platform-" in (model.dataset_version or "") or "synthetic" in str(meta.get("label_provenance", "")).lower()
    if synthetic:
        checks.append(_check("trained_on_real_business_data", False,
                             "trained on synthetic platform data only: the metrics describe the generator, not real businesses", blocking=False))
    if task == "churn":
        checks.append(_check("probability_semantics", False,
                             "output is a model score; calibration against observed outcomes of real businesses is not established", blocking=False))
    return checks


def validate_candidate(db: Session, model_id: str, actor: str) -> dict[str, Any]:
    model = db.get(MLModel, model_id)
    if model is None:
        raise NotFoundError(f"Model {model_id} not found.")
    checks = run_checks(db, model)
    blocking_failed = [c for c in checks if c["blocking"] and not c["passed"]]
    warnings = [c for c in checks if not c["blocking"] and not c["passed"]]
    result = {"passed": not blocking_failed, "checks": checks, "warnings": [w["name"] for w in warnings],
              "validated_at": utcnow().isoformat(), "validated_by": actor}
    if verify_artifact(model)[0] == "not_recorded":
        record_artifact(model, "pinned_at_validation", actor)
    life = dict(model.lifecycle_json or {})
    life["validation"] = result
    model.lifecycle_json = life
    prev = model.status
    if model.status in CANDIDATE_STATES:  # an active or archived model is checked but its state is not changed here
        model.status = STATUS_VALIDATED if result["passed"] else STATUS_REJECTED
        _event(db, model, "validated" if result["passed"] else "validation_failed", actor, None, prev, model.status,
               {"blocking_failed": [c["name"] for c in blocking_failed], "warnings": result["warnings"]})
    db.commit()
    db.refresh(model)
    return {"model_id": str(model.id), "model_name": model.model_name, "version": model.version, "status": model.status, **result}


def promote(db: Session, model_id: str, actor: str, reason: str | None) -> MLModel:
    model = db.get(MLModel, model_id)
    if model is None:
        raise NotFoundError(f"Model {model_id} not found.")
    if not reason or not reason.strip():
        raise ValidationFailedError("A reason is required to promote a model (it is recorded with who promoted it).")
    if model.status == STATUS_ACTIVE:
        raise ValidationFailedError(f"{model.model_name} {model.version} is already the active version.")
    if model.status != STATUS_VALIDATED:
        raise ValidationFailedError(
            f"{model.model_name} {model.version} is '{model.status}'. Only a model that passed validation can be promoted: "
            f"run validation first (POST /research/models/{model.id}/validate)."
        )
    state, detail = verify_artifact(model)
    if state == "mismatch":   # a missing file is reported by the load check
        raise ValidationFailedError(f"{model.model_name} {model.version} cannot be promoted: {detail}. Register and validate the artifact again.")
    if state == "not_recorded":
        record_artifact(model, "pinned_at_promotion", actor)
    previous = db.execute(select(MLModel).where(MLModel.model_name == model.model_name, MLModel.status == STATUS_ACTIVE)).scalars().all()
    prev_versions = []
    for other in previous:  # same transaction: there is never a moment with zero or two active versions
        other.status = STATUS_ARCHIVED
        prev_versions.append(other.version)
        _event(db, other, "archived", actor, f"superseded by {model.version}", STATUS_ACTIVE, STATUS_ARCHIVED, {"superseded_by": model.version})
    model.status = STATUS_ACTIVE
    model.promoted_at = utcnow()
    life = dict(model.lifecycle_json or {})
    life["promotion"] = {"by": actor, "reason": reason.strip(), "at": model.promoted_at.isoformat(), "replaced": prev_versions}
    model.lifecycle_json = life
    val = (life.get("validation") or {})
    _event(db, model, "promoted", actor, reason.strip(), STATUS_VALIDATED, STATUS_ACTIVE,
           {"replaced": prev_versions, "validation_passed": val.get("passed"), "warnings": val.get("warnings", [])})
    db.commit()
    db.refresh(model)
    _invalidate(model.model_name)
    return model


def rollback(db: Session, model_name: str, actor: str, reason: str | None) -> MLModel:
    if not reason or not reason.strip():
        raise ValidationFailedError("A reason is required to roll back a model.")
    current = db.execute(select(MLModel).where(MLModel.model_name == model_name, MLModel.status == STATUS_ACTIVE)).scalars().first()
    if current is None:
        raise ValidationFailedError(f"{model_name} has no active version to roll back from.")
    events = history(db, model_name=model_name)
    # a version that was itself rolled back from (judged bad while active) is never a rollback target
    bad = {e.version for e in events if e.event == "rolled_back" and e.from_status == STATUS_ACTIVE and e.to_status == STATUS_ARCHIVED}
    activations = [e for e in events if e.to_status == STATUS_ACTIVE]
    order: list[str] = []
    for e in activations:  # chronological: the order in which versions became active
        if not order or order[-1] != e.version:
            order.append(e.version)
    if current.version in order:
        order = order[: len(order) - 1 - order[::-1].index(current.version)]
    order = [v for v in order if v not in bad and v != current.version]
    if not order:
        raise ValidationFailedError(f"{model_name} has no earlier active version recorded, so there is nothing to roll back to.")
    target_version = order[-1]
    target = db.execute(select(MLModel).where(MLModel.model_name == model_name, MLModel.version == target_version)).scalars().first()
    if target is None:
        raise ValidationFailedError(f"The previous version {target_version} is no longer in the registry.")
    state, detail = verify_artifact(target)
    if state == "mismatch":   # a missing file falls through to the load check below
        raise ValidationFailedError(f"The previous version {target_version} cannot be restored: {detail}; rollback refused.")
    try:  # never switch to an artifact that cannot be loaded
        import joblib

        joblib.load(PROJECT_ROOT / target.model_path)
    except Exception as exc:  # noqa: BLE001
        raise ValidationFailedError(f"The previous version {target_version} cannot be loaded ({type(exc).__name__}); rollback refused.") from exc
    current.status = STATUS_ARCHIVED
    _event(db, current, "rolled_back", actor, reason.strip(), STATUS_ACTIVE, STATUS_ARCHIVED, {"restored": target_version})
    prev_status = target.status
    target.status = STATUS_ACTIVE
    target.promoted_at = utcnow()
    _event(db, target, "rolled_back", actor, reason.strip(), prev_status, STATUS_ACTIVE, {"replaced": current.version})
    db.commit()
    db.refresh(target)
    _invalidate(model_name)
    return target


def _invalidate(model_name: str) -> None:
    try:  # the loaded-model cache (if present) must never serve a superseded version
        from app.services import model_cache

        model_cache.clear(model_name)
    except ImportError:
        pass
