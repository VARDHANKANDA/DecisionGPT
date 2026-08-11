"""Load platform/research datasets from data/platform/**.

This is the only place the training pipeline touches raw platform data —
the runtime application never imports from here (see AGENTS.md "Data
isolation": platform training data must never be reachable from SME-facing
code paths).
"""
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

PLATFORM_DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "platform"


@dataclass
class PlatformDataset:
    domain: str
    dataframe: pd.DataFrame
    metadata: dict


def _dataset_dir(domain: str) -> Path:
    path = PLATFORM_DATA_ROOT / domain
    if not path.exists():
        raise FileNotFoundError(
            f"No platform dataset directory for domain={domain!r} at {path}. "
            "Run scripts/generate_platform_data.py or place a real dataset there."
        )
    return path


def load_platform_dataset(domain: str, filename: str) -> PlatformDataset:
    directory = _dataset_dir(domain)
    csv_path = directory / filename
    metadata_path = directory / "metadata.json"

    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {csv_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Missing metadata.json for domain={domain!r} — every platform "
            "dataset must be documented (source/license/limitations)."
        )

    df = pd.read_csv(csv_path)
    metadata = json.loads(metadata_path.read_text())
    return PlatformDataset(domain=domain, dataframe=df, metadata=metadata)
