"""File-based model artifact registry.

Training scripts call `save_model_artifact` after evaluation. It writes the
serialized model plus a manifest (model_name, type, version, dataset
version, feature version, parameters, metrics, path, timestamp — exactly
the fields docs/AI_MODULE_SPECIFICATION.md §9 requires) to `models/`.

This is deliberately a plain file format (joblib + JSON manifest), not a
direct DB write: the training pipeline runs offline/standalone and must not
require a live Postgres connection. `backend/app/services/model_registry_service.py`
(Phase 6) reads these manifests and syncs approved entries into the `models`
DB table that the runtime application actually queries.
"""
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib

MODELS_ROOT = Path(__file__).resolve().parents[2] / "models"


@dataclass
class ModelManifest:
    model_name: str
    model_type: str
    version: str
    dataset_version: str
    feature_version: str
    parameters: dict
    metrics: dict
    artifact_path: str
    trained_at: str
    random_seed: int


def save_model_artifact(
    model,
    model_name: str,
    model_type: str,
    version: str,
    dataset_version: str,
    feature_version: str,
    parameters: dict,
    metrics: dict,
    random_seed: int,
) -> ModelManifest:
    out_dir = MODELS_ROOT / model_name / version
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = out_dir / "model.joblib"
    joblib.dump(model, artifact_path)

    manifest = ModelManifest(
        model_name=model_name,
        model_type=model_type,
        version=version,
        dataset_version=dataset_version,
        feature_version=feature_version,
        parameters=parameters,
        metrics=metrics,
        # .as_posix() (not str()) so the stored path always uses forward
        # slashes — trained-on-Windows registry entries must still resolve
        # correctly when the backend runs in a Linux container.
        artifact_path=artifact_path.relative_to(MODELS_ROOT.parent).as_posix(),
        trained_at=datetime.now(timezone.utc).isoformat(),
        random_seed=random_seed,
    )
    (out_dir / "manifest.json").write_text(json.dumps(asdict(manifest), indent=2))

    # Append to the flat index every registry reader can scan without
    # walking the whole models/ tree.
    index_path = MODELS_ROOT / "registry_index.jsonl"
    with open(index_path, "a") as f:
        f.write(json.dumps(asdict(manifest)) + "\n")

    return manifest


def load_latest_manifest(model_name: str) -> ModelManifest | None:
    index_path = MODELS_ROOT / "registry_index.jsonl"
    if not index_path.exists():
        return None
    latest = None
    with open(index_path) as f:
        for line in f:
            entry = json.loads(line)
            if entry["model_name"] == model_name:
                latest = entry
    return ModelManifest(**latest) if latest else None


def load_model(manifest: ModelManifest):
    return joblib.load(MODELS_ROOT.parent / manifest.artifact_path)
