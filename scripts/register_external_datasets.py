"""Register the processed external benchmark CSVs into the EXISTING Dataset
Registry (research_dataset_service.upload_dataset) - no new dataset system,
no schema change.

Default target is the active **Indian** dataset(s). Each is labelled with an
"External Benchmark - India" source plus its real licence + citation, so the
Research Console clearly distinguishes it from the bundled synthetic platform
datasets.

    python scripts/register_external_datasets.py [--force] [--only india]
    python scripts/register_external_datasets.py --retired [--only uci|m5|regional]

``--retired`` re-registers the archived non-Indian benchmarks; their name and
source are prefixed ``RETIRED_NON_INDIAN_BENCHMARK`` so they can never be
mistaken for the active India-focused evaluation.

Requires DATABASE_URL. Run scripts/build_external_datasets.py first.
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
RETIRED = EXT / "_retired_non_indian"

# key -> list of (base_dir, metadata_dir, processed_csv, registry_name, domain, extra_description)
ACTIVE_SPECS = {
    "india": [
        (EXT, "india_agmarknet", "processed/india_agmarknet_forecasting.csv",
         "External India AGMARKNET - Forecasting", "forecasting",
         "INDIAN PRICE-FORECASTING BENCHMARK (AGMARKNET daily mandi modal prices, "
         "data.gov.in, GODL-India). NOTE: this source has NO transaction-quantity "
         "field, so the canonical 'units_sold' column carries the daily MODAL PRICE "
         "(INR/quintal) being forecast; 'price' is a 28-day backward rolling median "
         "(no leakage); marketing_spend/promotion_flag are 0 (absent in source)."),
        (EXT, "india_agmarknet", "processed/india_agmarknet_regional_analytics.csv",
         "External India AGMARKNET - Regional Analytics", "other",
         "State x commodity x month price level / volatility / spread table. "
         "Descriptive only; not consumed by any training task."),
    ],
}

RETIRED_SPECS = {
    "uci": [
        (RETIRED, "uci_online_retail", "processed/uci_forecasting.csv",
         "External UCI Online Retail - Forecasting", "forecasting", ""),
        (RETIRED, "uci_online_retail", "processed/uci_churn_derived.csv",
         "External UCI Online Retail - Derived Churn", "churn",
         "DERIVED CHURN LABEL (inactivity-based, time-aware split). Does NOT replace platform-churn-v1."),
        (RETIRED, "uci_online_retail", "processed/uci_customer_rfm.csv",
         "External UCI Online Retail - Customer RFM", "other",
         "Descriptive RFM table; not consumed by any training task."),
    ],
    "m5": [
        (RETIRED, "m5_forecasting", "processed/m5_forecasting.csv",
         "External M5 Forecasting Benchmark", "forecasting",
         "40-series deterministic subsample; marketing_spend/promotion_flag held at 0."),
    ],
    "regional": [
        (RETIRED, "regional_retail", "processed/regional_retail_forecasting.csv",
         "External Regional Retail (Myanmar) - Forecasting", "forecasting",
         "Myanmar, NOT India. Small; illustrative regional benchmark only."),
        (RETIRED, "regional_retail", "processed/regional_retail_analytics.csv",
         "External Regional Retail (Myanmar) - Analytics", "other",
         "Margin/analytics table; not consumed by any training task."),
    ],
}

RETIRED_PREFIX = "RETIRED_NON_INDIAN_BENCHMARK"


def _provenance(meta: dict, extra: str, retired: bool) -> tuple[str, str, str]:
    dt = meta.get("data_type", "unknown")
    name = meta.get("dataset_name") or meta.get("name") or "?"
    source = f"External Benchmark - {name} (data_type={dt})"
    if retired:
        source = f"{RETIRED_PREFIX} - {source}"
    lic = meta.get("license", "see metadata")
    desc = (
        f"{name}. Source: {meta.get('source') or meta.get('source_name')} "
        f"({meta.get('source_url')}). Downloaded {meta.get('download_date')}. "
        f"Citation: {meta.get('citation')}. Geography: "
        f"{meta.get('geography') or meta.get('country_context')}. {extra}"
    ).strip()
    if retired:
        desc = f"[{RETIRED_PREFIX}] {desc}"
    return source, lic, desc[:2000]


def _already_registered(db, slug: str) -> bool:
    ds = db.query(ResearchDataset).filter(ResearchDataset.dataset_id == slug).one_or_none()
    if ds is None:
        return False
    return (
        db.query(ResearchDatasetVersion).filter(ResearchDatasetVersion.dataset_id == ds.id).count() > 0
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="upload a new version even if already registered")
    ap.add_argument("--retired", action="store_true", help="register the archived non-Indian benchmarks")
    ap.add_argument("--only", default=None)
    args = ap.parse_args()

    specs = RETIRED_SPECS if args.retired else ACTIVE_SPECS
    if args.only and args.only not in specs:
        ap.error(f"--only must be one of {list(specs)} ({'retired' if args.retired else 'active'} set)")

    Base.metadata.create_all(engine)
    db = SessionLocal()
    keys = [args.only] if args.only else list(specs)
    registered = []
    try:
        for key in keys:
            for base_dir, meta_dir, csv_rel, name, domain, extra in specs[key]:
                reg_name = f"{RETIRED_PREFIX} {name}" if args.retired else name
                csv_path = base_dir / meta_dir / csv_rel
                if not csv_path.exists():
                    print(f"SKIP {reg_name}: {csv_path} missing (run build_external_datasets.py)")
                    continue
                meta = json.loads((base_dir / meta_dir / "metadata.json").read_text(encoding="utf-8"))
                slug = research_dataset_service._slugify(reg_name)
                if not args.force and _already_registered(db, slug):
                    print(f"SKIP {reg_name}: already registered ({slug}); use --force for a new version")
                    continue
                source, lic, desc = _provenance(meta, extra, args.retired)
                v = research_dataset_service.upload_dataset(
                    db, name=reg_name, domain=domain, filename=csv_path.name,
                    content=csv_path.read_bytes(), description=desc, source=source,
                    license=lic, created_by="register_external_datasets.py",
                )
                registered.append((reg_name, slug, v.version))
                print(f"OK   {reg_name}: {slug} v{v.version} "
                      f"({v.row_count} rows x {v.column_count} cols, validation_ok={v.validation_ok})")
    finally:
        db.close()

    print(f"\n{len(registered)} dataset version(s) registered.")


if __name__ == "__main__":
    main()
