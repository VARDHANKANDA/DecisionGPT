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

PLATFORM_DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "platform"
DOMAINS = ["forecasting", "churn", "marketing", "pricing", "inventory", "causal", "benchmarks"]


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
                evidence_level=metadata.get("evidence_level", "UNKNOWN"),
            )
        )
    return entries
