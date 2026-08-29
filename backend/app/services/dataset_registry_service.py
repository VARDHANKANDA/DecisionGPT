"""Research Console — Dataset Registry (docs/PRD.md §9).

Reads real metadata.json files under data/platform/** — never the raw rows
(the runtime app is barred from touching those at all; this file exists
only behind the research-console gate, app.api.deps.require_research_access,
for the platform administrator). Domains with no dataset yet (most of
data/platform/* only has a .gitkeep so far) are reported as such, not
padded with a placeholder entry.
"""
import csv
import json
from dataclasses import dataclass
from pathlib import Path

from app.services import dataset_category

_DATA_ROOT = Path(__file__).resolve().parents[3] / "data"
PLATFORM_DATA_ROOT = _DATA_ROOT / "platform"
EXTERNAL_DATA_ROOT = _DATA_ROOT / "external"
DOMAINS = ["forecasting", "churn", "marketing", "pricing", "inventory", "causal", "benchmarks"]

# file-based external datasets surfaced in the registry (docs/INDIAN_DATASET_CATALOG.md)
_EXTERNAL_METADATA = [
    "india_agmarknet/metadata.json",
    "india_context/festivals/metadata.json",
    "india_context/macro/metadata.json",
]


@dataclass
class DatasetEntry:
    domain: str
    dataset_id: str
    name: str
    source: str
    license: str
    version: str
    row_count: int
    feature_count: int
    date_range: list[str] | None
    preprocessing: list[str]
    limitations: list[str]
    evidence_level: str
    data_category: str = dataset_category.UNCLASSIFIED


@dataclass
class ExternalDatasetEntry:
    dataset_id: str
    name: str
    display_label: str
    data_category: str
    status: str
    source: str
    license: str
    geography: str
    business_domain: str
    date_range: str | None
    supported_tasks: list[str]
    limitations: list[str]


def _count_rows(csv_path: Path) -> int:
    with open(csv_path, newline="", encoding="utf-8") as f:
        return max(0, sum(1 for _ in csv.reader(f)) - 1)  # exclude header


def list_datasets() -> list[DatasetEntry]:
    entries: list[DatasetEntry] = []
    for domain in DOMAINS:
        domain_dir = PLATFORM_DATA_ROOT / domain
        metadata_path = domain_dir / "metadata.json"
        if not metadata_path.exists():
            continue

        metadata = json.loads(metadata_path.read_text())
        csv_files = [p for p in domain_dir.glob("*.csv")]
        row_count = _count_rows(csv_files[0]) if csv_files else metadata.get("rows", 0)
        dataset_id = metadata.get("dataset_id", f"platform-{domain}")
        version = dataset_id.rsplit("-", 1)[-1] if "-" in dataset_id else "v1"

        evidence_level = metadata.get("evidence_level", "UNKNOWN")
        entries.append(
            DatasetEntry(
                domain=domain,
                dataset_id=dataset_id,
                name=metadata.get("name", domain),
                source=metadata.get("source", "unknown"),
                license=metadata.get("license", "unknown"),
                version=version,
                row_count=row_count,
                feature_count=len(metadata.get("columns", [])),
                date_range=metadata.get("date_range"),
                preprocessing=metadata.get("preprocessing", []),
                limitations=metadata.get("limitations", []),
                evidence_level=evidence_level,
                data_category=dataset_category.classify(
                    source=metadata.get("source"),
                    evidence_level=evidence_level,
                    dataset_id=dataset_id,
                    explicit=metadata.get("registry_category"),
                ),
            )
        )
    return entries


def list_external_datasets() -> list[ExternalDatasetEntry]:
    """File-based Indian external datasets (AGMARKNET price series + public
    context). Read from data/external/**/metadata.json — never the raw rows."""
    out: list[ExternalDatasetEntry] = []
    for rel in _EXTERNAL_METADATA:
        path = EXTERNAL_DATA_ROOT / rel
        if not path.exists():
            continue
        m = json.loads(path.read_text(encoding="utf-8"))
        out.append(
            ExternalDatasetEntry(
                dataset_id=m.get("dataset_id", rel),
                name=m.get("dataset_name", rel),
                display_label=m.get("display_label", m.get("dataset_name", rel)),
                data_category=dataset_category.classify(
                    source=m.get("source"),
                    dataset_id=m.get("dataset_id"),
                    explicit=m.get("registry_category"),
                ),
                status=m.get("status", "UNKNOWN"),
                source=m.get("source", "unknown"),
                license=m.get("license", "unknown"),
                geography=m.get("geography", "India"),
                business_domain=m.get("business_domain", ""),
                date_range=m.get("date_range"),
                supported_tasks=m.get("target_tasks", []),
                limitations=m.get("known_limitations", []),
            )
        )
    return out
