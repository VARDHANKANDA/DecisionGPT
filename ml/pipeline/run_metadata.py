"""Reproducibility metadata recorded next to every trained model (``run_metadata.json``): dataset checksum, split boundaries, seed,
parameters, feature list, package versions, code revision. Shared by the production trainers and ``ml/benchmark``.

The registry manifest format is unchanged (readers construct ``ModelManifest(**entry)``); this file is a sidecar.
"""
from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_PACKAGES = ("numpy", "pandas", "scipy", "scikit-learn", "xgboost", "lightgbm", "catboost", "joblib")


def git_revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def package_versions() -> dict[str, str]:
    from importlib import metadata

    out = {"python": sys.version.split()[0], "platform": platform.platform()}
    for p in _PACKAGES:
        try:
            out[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            out[p] = "not installed"
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def split_boundaries(train, val, test, date_column: str) -> dict[str, Any]:
    def span(df):
        if df is None or len(df) == 0:
            return {"rows": 0}
        return {"rows": int(len(df)), "first": str(df[date_column].min())[:10], "last": str(df[date_column].max())[:10]}

    return {"train": span(train), "validation": span(val), "test": span(test), "scheme": "chronological, unique-date boundaries"}


def build_run_metadata(*, task: str, dataset_version: str, dataset_path: Path | None, seed: int, parameters: dict, feature_columns: list[str],
                       splits: dict[str, Any] | None = None, selection: str | None = None, extra: dict | None = None) -> dict[str, Any]:
    return {
        "task": task, "dataset_version": dataset_version,
        "dataset_sha256": sha256_file(dataset_path) if dataset_path and Path(dataset_path).exists() else None,
        "random_seed": seed, "parameters": parameters, "feature_columns": list(feature_columns), "splits": splits,
        "selection_rule": selection, "git_revision": git_revision(), "versions": package_versions(),
        "created_utc": datetime.now(timezone.utc).isoformat(), **(extra or {}),
    }
