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
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib

MODELS_ROOT = Path(__file__).resolve().parents[2] / "models"


class ArtifactExistsError(FileExistsError):
    """A model version is immutable: training never overwrites an existing artifact (create a new version instead)."""


_VERSION = re.compile(r"^v(\d+)$")


def next_version(model_name: str, used: set[str] | None = None) -> str:
    """The next unused ``vN`` for ``model_name``, looking at the artifact directory, the index and any versions the caller knows about
    (for example rows in the models table that were registered without a file index entry)."""
    taken: set[str] = set(used or ())
    root = MODELS_ROOT / model_name
    if root.exists():
        taken.update(p.name for p in root.iterdir() if p.is_dir())
    index_path = MODELS_ROOT / "registry_index.jsonl"
    if index_path.exists():
        with open(index_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if e.get("model_name") == model_name:
                        taken.add(str(e.get("version")))
    nums = [int(m.group(1)) for v in taken if (m := _VERSION.match(v))]
    return f"v{max(nums, default=0) + 1}"


def _atomic_write_bytes(path: Path, writer) -> None:
    """Write via a temp file in the same directory, flush to disk, then ``os.replace``: an interrupted run leaves either the old file
    or the complete new one, never a partial file."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            writer(f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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
    write_index: bool = True,
    run_metadata: dict | None = None,
) -> ModelManifest:
    """Persist a model artifact + manifest under ``models/``.

    ``write_index`` appends the manifest to the flat ``registry_index.jsonl``
    that ``model_registry_service.sync_from_file_registry`` scans to decide
    the *active* model. The Research Console's Training Center passes
    ``write_index=False`` — its models are registered directly in the DB as
    ``experimental`` and must not be auto-activated by a later sync.
    """
    out_dir = MODELS_ROOT / model_name / version
    artifact_path = out_dir / "model.joblib"
    if artifact_path.exists() or (out_dir / "manifest.json").exists():
        raise ArtifactExistsError(
            f"{model_name} {version} already exists; versions are immutable. Use ml.pipeline.registry.next_version(...) for a new version."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_bytes(artifact_path, lambda f: joblib.dump(model, f))

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
    if run_metadata is not None:  # sidecar: the manifest/index format that readers construct ModelManifest(**entry) from is unchanged
        _atomic_write_bytes(out_dir / "run_metadata.json", lambda f: f.write(json.dumps(run_metadata, indent=2, default=str).encode("utf-8")))
    _atomic_write_bytes(out_dir / "manifest.json", lambda f: f.write(json.dumps(asdict(manifest), indent=2).encode("utf-8")))

    if write_index:
        # Append to the flat index every registry reader can scan without
        # walking the whole models/ tree.
        index_path = MODELS_ROOT / "registry_index.jsonl"
        line = (json.dumps(asdict(manifest)) + "\n").encode("utf-8")
        with open(index_path, "ab") as f:  # one write call per record, flushed and fsynced: a crash cannot leave half a line mid-file
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

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
