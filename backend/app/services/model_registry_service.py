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

from app.models.ml_model import MLModel

REGISTRY_INDEX_PATH = Path(__file__).resolve().parents[3] / "models" / "registry_index.jsonl"


def sync_from_file_registry(db: Session, index_path: Path = REGISTRY_INDEX_PATH) -> list[MLModel]:
    if not index_path.exists():
        return []

    manifests_by_name: dict[str, list[dict]] = {}
    with open(index_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            manifests_by_name.setdefault(entry["model_name"], []).append(entry)

    synced: list[MLModel] = []
    for model_name, entries in manifests_by_name.items():
        # Last line for a given model_name = most recently trained version.
        latest = entries[-1]

        existing = db.execute(
            select(MLModel).where(
                MLModel.model_name == model_name, MLModel.version == latest["version"]
            )
        ).scalar_one_or_none()

        if existing is None:
            existing = MLModel(model_name=model_name, version=latest["version"])
            db.add(existing)

        existing.model_type = latest["model_type"]
        existing.dataset_version = latest["dataset_version"]
        existing.feature_version = latest["feature_version"]
        existing.parameters_json = latest["parameters"]
        existing.metrics_json = latest["metrics"]
        existing.model_path = latest["artifact_path"]
        existing.status = "active"

        # Any other row for this model_name is now superseded.
        others = db.execute(
            select(MLModel).where(
                MLModel.model_name == model_name, MLModel.version != latest["version"]
            )
        ).scalars()
        for other in others:
            other.status = "archived"

        synced.append(existing)

    db.commit()
    for m in synced:
        db.refresh(m)
    return synced


def list_models(db: Session, model_type: str | None = None) -> list[MLModel]:
    stmt = select(MLModel).order_by(MLModel.model_name)
    if model_type:
        stmt = stmt.where(MLModel.model_type == model_type)
    return list(db.execute(stmt).scalars())


def get_active_model(db: Session, model_name: str) -> MLModel | None:
    return db.execute(
        select(MLModel).where(MLModel.model_name == model_name, MLModel.status == "active")
    ).scalar_one_or_none()


def select_best_model(
    db: Session, model_names: list[str], metric: str, minimize: bool
) -> MLModel | None:
    """Pick the deployed model for a task (e.g. "which of the three churn
    models actually runs at inference time?") from real recorded metrics,
    rather than hard-coding an assumption like "XGBoost is always best" —
    see docs/AI_MODULE_SPECIFICATION.md §1 "use the simplest reliable model
    that fits the dataset" and AGENTS.md "no fabrication"."""
    candidates = [get_active_model(db, name) for name in model_names]
    candidates = [c for c in candidates if c is not None and metric in c.metrics_json]
    if not candidates:
        return None
    return min(candidates, key=lambda m: m.metrics_json[metric]) if minimize else max(
        candidates, key=lambda m: m.metrics_json[metric]
    )
