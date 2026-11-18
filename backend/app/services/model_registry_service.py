"""Model registry service — the DB-facing half of the registry.

`ml/pipeline/registry.py` (offline training side) writes artifacts + a
manifest per model version to `models/registry_index.jsonl`. This service
reads that file and syncs it into the `models` table, which is what the
runtime application and the Research Console actually query. Keeping the
sync explicit (rather than having training scripts write to Postgres
directly) means the training pipeline never needs a live DB connection to
run, and a human/CI step controls what becomes "the registered model".

Within a model_name, the most recently trained version is marked "active"
and all others "archived" — the runtime inference code always asks for the
active version of a given model_name.
"""
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.models.ml_model import STATUS_CANDIDATE, MLModel
from app.services import model_lifecycle_service as lifecycle_service
from app.models.common import utcnow

REGISTRY_INDEX_PATH = Path(__file__).resolve().parents[3] / "models" / "registry_index.jsonl"


def _read_run_metadata(artifact_path: str) -> dict | None:
    """The training sidecar written next to the artifact (dataset checksum, split boundaries, seed, versions, code revision)."""
    try:
        meta = json.loads((REGISTRY_INDEX_PATH.parent.parent / Path(artifact_path).parent / "run_metadata.json").read_text(encoding="utf-8"))
        return meta if isinstance(meta, dict) else None
    except (OSError, ValueError):
        return None


def _version_key(v: str) -> tuple[int, str]:
    digits = "".join(ch for ch in v if ch.isdigit())
    return (int(digits) if digits else -1, v)


def sync_from_file_registry(db: Session, index_path: Path = REGISTRY_INDEX_PATH) -> list[MLModel]:
    """Register every (model_name, version) found in the file index. **Registering is not deploying**:

    * a version seen for the first time becomes a ``candidate`` (never used for inference until validated and promoted);
    * the only exception is the first version of a model name when nothing is deployed: it is activated once and logged as
      ``bootstrap_activation`` so a fresh installation has something to serve;
    * rows that already exist keep their status (re-running the sync, or training a newer version, never changes what is deployed).
    """
    if not index_path.exists():
        return []

    by_name: dict[str, dict[str, dict]] = {}
    with open(index_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue  # a torn line must not break the sync
            by_name.setdefault(entry["model_name"], {})[entry["version"]] = entry  # a repeated version keeps its LAST line

    touched: list[MLModel] = []
    for model_name, versions in by_name.items():
        has_active = db.execute(
            select(MLModel).where(MLModel.model_name == model_name, MLModel.status == "active")
        ).scalars().first() is not None
        for version in sorted(versions, key=_version_key):
            entry = versions[version]
            row = db.execute(select(MLModel).where(MLModel.model_name == model_name, MLModel.version == version)).scalar_one_or_none()
            created = row is None
            if row is None:
                row = MLModel(model_name=model_name, version=version)
                row.model_type = entry["model_type"]
                row.dataset_version = entry["dataset_version"]
                row.feature_version = entry["feature_version"]
                row.parameters_json = entry["parameters"]
                row.metrics_json = entry["metrics"]
                row.model_path = entry["artifact_path"]
                row.status = STATUS_CANDIDATE
                db.add(row)
                db.flush()
                lifecycle_service.record_artifact(row, "at_registration", "system:sync")
                lifecycle_service._event(db, row, "registered", "system:sync", "found in registry_index.jsonl", None, STATUS_CANDIDATE)
            meta = _read_run_metadata(entry["artifact_path"])
            if meta and not (row.lifecycle_json or {}).get("run_metadata"):
                life = dict(row.lifecycle_json or {})
                life["run_metadata"] = meta
                row.lifecycle_json = life
            touched.append(row)
        if not has_active:
            newest = max(versions, key=_version_key)
            row = db.execute(select(MLModel).where(MLModel.model_name == model_name, MLModel.version == newest)).scalar_one()
            if row.status in (STATUS_CANDIDATE, "registered", "experimental"):
                prev = row.status
                row.status = "active"
                row.promoted_at = utcnow()
                life = dict(row.lifecycle_json or {})
                life["promotion"] = {"by": "system:sync", "reason": "bootstrap: no version of this model was deployed", "at": row.promoted_at.isoformat()}
                row.lifecycle_json = life
                lifecycle_service._event(db, row, "bootstrap_activation", "system:sync", "no version of this model was deployed", prev, "active")

    db.commit()
    for m in touched:
        db.refresh(m)
    return touched


def list_models(
    db: Session, model_type: str | None = None, status: str | None = None
) -> list[MLModel]:
    stmt = select(MLModel).order_by(MLModel.model_name, MLModel.created_at.desc())
    if model_type:
        stmt = stmt.where(MLModel.model_type == model_type)
    if status:
        stmt = stmt.where(MLModel.status == status)
    return list(db.execute(stmt).scalars())


def get_model(db: Session, model_id: str) -> MLModel:
    model = db.get(MLModel, model_id)
    if model is None:
        raise NotFoundError(f"Model {model_id} not found.")
    return model


def promote_model(db: Session, model_id: str, actor: str = "unknown", reason: str | None = None) -> MLModel:
    """Make ``model_id`` the ACTIVE model for its model_name. Only a VALIDATED model can be promoted, with an actor and a reason, and
    the previous active version is archived in the same transaction (see ``model_lifecycle_service.promote``)."""
    return lifecycle_service.promote(db, model_id, actor, reason)


def archive_model(db: Session, model_id: str, actor: str = "unknown", reason: str | None = None) -> MLModel:
    model = get_model(db, model_id)
    if model.status == "active":
        raise ValidationFailedError("The active model cannot be archived directly: promote another version or roll back.")
    prev = model.status
    model.status = "archived"
    lifecycle_service._event(db, model, "archived", actor, reason, prev, "archived")
    db.commit()
    db.refresh(model)
    return model


def get_active_model(db: Session, model_name: str) -> MLModel | None:
    return db.execute(
        select(MLModel).where(MLModel.model_name == model_name, MLModel.status == "active")
    ).scalar_one_or_none()


def select_best_model(
    db: Session, model_names: list[str], metric: str, minimize: bool, validation_metric: str | None = None
) -> MLModel | None:
    """Pick the deployed model for a task (e.g. "which of the three churn
    models actually runs at inference time?") from real recorded metrics,
    rather than hard-coding an assumption like "XGBoost is always best" —
    see docs/AI_MODULE_SPECIFICATION.md §1 "use the simplest reliable model
    that fits the dataset" and AGENTS.md "no fabrication"."""
    candidates = [get_active_model(db, name) for name in model_names]
    candidates = [c for c in candidates if c is not None]
    if validation_metric and candidates and all(validation_metric in c.metrics_json for c in candidates):
        # Select on VALIDATION metrics when every candidate has them: choosing on the test metric would make the reported
        # test score an optimistically biased estimate. Models trained before validation metrics were recorded fall back below.
        metric = validation_metric
    candidates = [c for c in candidates if metric in c.metrics_json]
    if not candidates:
        return None
    return min(candidates, key=lambda m: m.metrics_json[metric]) if minimize else max(
        candidates, key=lambda m: m.metrics_json[metric]
    )
