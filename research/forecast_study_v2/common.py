"""Shared utilities for forecast_study_v2: paths, hashing, atomic JSON/NPZ writes, version fingerprint."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import tempfile
from pathlib import Path

import numpy as np

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
RESULTS = STUDY / "results"
SEED = 42


def sha256_file(p: Path, buf: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(buf):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def atomic_write_json(path: Path, obj) -> None:
    atomic_write_text(path, json.dumps(obj, indent=1, default=_default, sort_keys=False))


def atomic_save_npz(path: Path, **arrays) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            np.savez_compressed(f, **arrays)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def atomic_save_npy(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npy")
    np.save(tmp, arr)
    os.replace(tmp, path)


def _default(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return o.as_posix()
    return str(o)


def versions() -> dict:
    import catboost
    import lightgbm
    import pandas
    import scipy
    import sklearn
    import xgboost

    return {"python": sys.version.split()[0], "platform": platform.platform(), "numpy": np.__version__, "pandas": pandas.__version__, "scipy": scipy.__version__, "scikit-learn": sklearn.__version__,
            "xgboost": xgboost.__version__, "lightgbm": lightgbm.__version__, "catboost": catboost.__version__, "cpu_count": os.cpu_count()}


def code_fingerprint() -> dict:
    return {p.name: sha256_file(p) for p in sorted(STUDY.glob("*.py"))}
