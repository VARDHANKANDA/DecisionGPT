"""Register the processed external benchmark CSVs into the EXISTING
Dataset Registry (research_dataset_service.upload_dataset) — no new dataset
system, no schema change.

Each dataset is labelled with an "External Benchmark" source and its real
licence + citation, so the Research Console clearly distinguishes it from
the bundled synthetic platform datasets.

    python scripts/register_external_datasets.py [--force] [--only uci|m5|regional]

Requires DATABASE_URL (defaults to the app's configured DB). Run
scripts/build_external_datasets.py first.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import app.models  # noqa: E402,F401
from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.models.research import ResearchDataset, ResearchDatasetVersion  # noqa: E402
from app.services import research_dataset_service  # noqa: E402

EXT = ROOT / "data" / "external"

# (metadata_dir, processed_csv, registry_name, domain, extra_description)
SPECS = {
    "uci": [
        ("uci_online_retail", "processed/uci_forecasting.csv",
         "External UCI Online Retail - Forecasting", "forecasting", ""),
        ("uci_online_retail", "processed/uci_churn_derived.csv",
         "External UCI Online Retail - Derived Churn", "churn",
         "DERIVED CHURN LABEL (inactivity-based, time-aware split). Does NOT replace platform-churn-v1."),
        ("uci_online_retail", "processed/uci_customer_rfm.csv",
         "External UCI Online Retail - Customer RFM", "other",
         "Descriptive RFM table; not consumed by any training task."),
    ],
    "m5": [
        ("m5_forecasting", "processed/m5_forecasting.csv",
         "External M5 Forecasting Benchmark", "forecasting",
         "40-series deterministic subsample; marketing_spend/promotion_flag held at 0 (M5 has no such signal)."),
    ],
    "regional": [
        ("regional_retail", "processed/regional_retail_forecasting.csv",
         "External Regional Retail (Myanmar) - Forecasting", "forecasting",
         "Myanmar, NOT India. Small (~89 days); illustrative regional benchmark only."),
        ("regional_retail", "processed/regional_retail_analytics.csv",
         "External Regional Retail (Myanmar) - Analytics", "other",
         "Margin/analytics table; not consumed by any training task."),
    ],
}


def _provenance(meta: dict, extra: str) -> tuple[str, str, str]:
    dt = meta.get("data_type", "unknown")
    source = f"External Benchmark - {meta.get('dataset_name', '?')} (data_type={dt})"
    lic = meta.get("license", "see metadata")
    desc = (
        f"{meta.get('dataset_name')}. Source: {meta.get('source')} "
        f"({meta.get('source_url')}). Downloaded {meta.get('download_date')}. "
        f"Citation: {meta.get('citation')}. Country: {meta.get('country_context')}. "
        f"{extra}".strip()
    )
    return source, lic, desc[:2000]


def _already_registered(db, slug: str) -> bool:
    ds = db.query(ResearchDataset).filter(ResearchDataset.dataset_id == slug).one_or_none()
    if ds is None:
        return False
    return (
        db.query(ResearchDatasetVersion)
        .filter(ResearchDatasetVersion.dataset_id == ds.id)
        .count()
        > 0
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="upload a new version even if already registered")
    ap.add_argument("--only", choices=list(SPECS), default=None)
    args = ap.parse_args()

    Base.metadata.create_all(engine)  # harmless if already migrated
    db = SessionLocal()
    keys = [args.only] if args.only else list(SPECS)
    registered = []
    try:
        for key in keys:
            for meta_dir, csv_rel, name, domain, extra in SPECS[key]:
                csv_path = EXT / meta_dir / csv_rel
                if not csv_path.exists():
                    print(f"SKIP {name}: {csv_path} missing (run build_external_datasets.py)")
                    continue
                meta = json.loads((EXT / meta_dir / "metadata.json").read_text(encoding="utf-8"))
                slug = research_dataset_service._slugify(name)
                if not args.force and _already_registered(db, slug):
                    print(f"SKIP {name}: already registered ({slug}); use --force for a new version")
                    continue
                source, lic, desc = _provenance(meta, extra)
                v = research_dataset_service.upload_dataset(
                    db,
                    name=name,
                    domain=domain,
                    filename=csv_path.name,
                    content=csv_path.read_bytes(),
                    description=desc,
                    source=source,
                    license=lic,
                    created_by="register_external_datasets.py",
                )
                registered.append((name, slug, v.version, v.row_count, v.column_count, v.validation_ok))
                print(f"OK   {name}: {slug} v{v.version} "
                      f"({v.row_count} rows x {v.column_count} cols, validation_ok={v.validation_ok})")
    finally:
        db.close()

    print(f"\n{len(registered)} dataset version(s) registered.")


if __name__ == "__main__":
    main()
