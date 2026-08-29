"""Import anonymised real Indian SME decision-outcome records.

Reads a CSV or JSON file matching docs/templates/real_indian_sme_outcome_template.*
and persists each valid row as a Decision + DecisionOutcome
(source_type = real_indian_sme) via
`app.services.real_sme_outcome_service.import_outcome_record`.

  * Rows whose `business_id` starts with "EXAMPLE" or whose `_label` / `notes`
    contain "EXAMPLE" or "SYNTHETIC" are SKIPPED — the template's illustration
    row can never be imported as evidence.
  * Any validation failure prints the full error list and the row is skipped;
    other rows still import.
  * Nothing is fabricated. If the file only has the example row, 0 records
    import and Table 2 stays NOT READY.

Usage:
  DATABASE_URL=... python scripts/import_real_sme_outcomes.py path/to/records.csv
  DATABASE_URL=... python scripts/import_real_sme_outcomes.py path/to/records.json
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.errors import ValidationFailedError  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services import real_sme_outcome_service as svc  # noqa: E402

_EXAMPLE_MARKERS = ("example", "synthetic")


def _is_example(rec: dict) -> bool:
    bid = str(rec.get("business_id", "")).lower()
    blob = " ".join(str(rec.get(k, "")) for k in ("_label", "notes", "_comment")).lower()
    return bid.startswith("example") or any(m in blob for m in _EXAMPLE_MARKERS)


def _load(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("records", data) if isinstance(data, dict) else list(data)
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    path = Path(argv[1])
    if not path.exists():
        print(f"file not found: {path}")
        return 2

    records = _load(path)
    db = SessionLocal()
    imported = skipped_example = failed = 0
    try:
        for i, rec in enumerate(records, 1):
            if _is_example(rec):
                print(f"[{i}] SKIP — example / synthetic illustration row (never imported as evidence)")
                skipped_example += 1
                continue
            try:
                res = svc.import_outcome_record(db, rec)
                print(f"[{i}] imported outcome {res['outcome_id'][:8]} "
                      f"(business {res['business_id'][:8]}, {res['data_category']})")
                imported += 1
            except ValidationFailedError as exc:
                failed += 1
                print(f"[{i}] REJECTED — {exc.message}")
                for e in (exc.details or {}).get("errors", []):
                    print(f"       - {e}")
    finally:
        db.close()

    print(f"\nimported={imported}  skipped_example={skipped_example}  rejected={failed}")
    if imported == 0:
        print("REAL SME OUTCOME COLLECTION = PENDING ; TABLE 2 = NOT READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
