"""Download the Indian benchmark dataset(s) through legitimate public access.

Dataset A - India Agri-Commodity Daily Market Prices (AGMARKNET)
    Source : Open Government Data (OGD) Platform India - data.gov.in
             resource 35985678-0d79-46b4-9ed6-6f13308a1d24
             "Variety-wise Daily Market Prices Data of Commodity"
             Directorate of Marketing & Inspection (DMI),
             Ministry of Agriculture & Farmers Welfare, Government of India.
    Licence: Government Open Data License - India (GODL-India).
    Access : public JSON REST API. No login, no scraping, no ToS bypass.
             data.gov.in publishes a shared demo API key in its own API docs
             for exactly this use; override with the DATA_GOV_IN_API_KEY env
             var if you have registered your own free key.

The raw pull is written verbatim to
``data/external/india_agmarknet/raw/india_agmarknet_raw.csv`` and is
never modified afterwards (``scripts/build_external_datasets.py`` reads it
read-only and writes ``processed/``).

    python scripts/download_india_datasets.py [--limit-pages N] [--fresh]

Per-series responses are checkpointed under ``raw/_parts/`` so an
interrupted run resumes where it stopped. ``--fresh`` clears the checkpoints.
Deterministic: a fixed, curated list of (state, commodity, market) series is
pulled in a fixed order, each page sorted, so re-running produces the same
file (subject to the government adding new rows over time).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "external" / "india_agmarknet" / "raw"
PARTS_DIR = RAW_DIR / "_parts"

RESOURCE_ID = "35985678-0d79-46b4-9ed6-6f13308a1d24"
API = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
# data.gov.in's own published demo key (see the "API" tab of any dataset page).
# The demo key returns ~10 records/call; a registered free key returns 1000+.
# We paginate with sort[Arrival_Date]=asc so the pull is a contiguous daily
# series regardless of page size. Set DATA_GOV_IN_API_KEY to use your own key
# (far fewer calls).
DEMO_KEY = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"
PAGE = 100                # requested; demo key caps the actual return at ~10
TIMEOUT = 90

# Curated, deterministic (State, Commodity, Market) series. Chosen for long,
# dense daily history in high-liquidity markets across several states so the
# chronological train/test split is meaningful. Kept small on purpose.
SERIES = [
    ("Maharashtra", "Onion", "Lasalgaon"),
    ("Maharashtra", "Onion", "Pune"),
    ("Maharashtra", "Tomato", "Pune"),
    ("Maharashtra", "Soyabean", "Latur"),
    ("Karnataka", "Onion", "Bangalore"),
    ("Karnataka", "Tomato", "Kolar"),
    ("Madhya Pradesh", "Wheat", "Indore"),
    ("Uttar Pradesh", "Potato", "Agra"),
]

COLUMNS = ["Arrival_Date", "State", "District", "Market", "Commodity",
           "Variety", "Grade", "Min_Price", "Max_Price", "Modal_Price"]


def _api_key() -> str:
    return os.environ.get("DATA_GOV_IN_API_KEY", "").strip() or DEMO_KEY


def _get(params: dict) -> dict:
    """GET via curl - fast and reliable on this environment; no ToS bypass,
    plain public JSON API."""
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(12):
        try:
            out = subprocess.run(
                ["curl", "-sS", "-L", "--max-time", str(TIMEOUT), url],
                capture_output=True, text=True, timeout=TIMEOUT + 15,
            )
            if out.returncode != 0 or not out.stdout.strip():
                raise RuntimeError(f"curl rc={out.returncode} {out.stderr[:120]}")
            data = json.loads(out.stdout)
            if isinstance(data, dict) and data.get("error"):
                # e.g. {"error": "Rate limit exceeded"} - the demo key uses a
                # short burst window; wait it out rather than give up.
                raise RuntimeError(str(data["error"]))
            return data
        except Exception as exc:  # noqa: BLE001 - transient network / rate limit
            if attempt == 11:
                raise
            wait = 90 if "Rate limit" in str(exc) else 4 * (attempt + 1)
            print(f"    retry {attempt + 1}/11 in {wait}s ({exc})", flush=True)
            time.sleep(wait)
    return {}


def _part_path(state: str, commodity: str, market: str) -> Path:
    safe = urllib.parse.quote(f"{state}__{commodity}__{market}", safe="")
    return PARTS_DIR / f"{safe}.json"


def pull_series(state: str, commodity: str, market: str, max_pages: int) -> list[dict]:
    part = _part_path(state, commodity, market)
    if part.exists():
        rows = json.loads(part.read_text(encoding="utf-8"))
        print(f"  cached {state} / {commodity} / {market}: {len(rows)} rows")
        return rows

    key = _api_key()
    base = {
        "api-key": key, "format": "json", "limit": PAGE,
        "sort[Arrival_Date]": "asc",
        "filters[State]": state, "filters[Commodity]": commodity,
        "filters[Market]": market,
    }
    # NB: the API returns a null body for limit=1 together with sort[...], so
    # there is no cheap HEAD - we read `total` off the first real page.
    out: list[dict] = []
    offset = 0
    total = None
    for _ in range(max_pages):
        try:
            d = _get({**base, "offset": offset})
        except Exception as exc:  # noqa: BLE001
            print(f"    offset {offset} failed ({exc}) - keeping {len(out)} rows so far", flush=True)
            break
        if total is None:
            total = int(d.get("total", 0) or 0)
            if total == 0:
                print(f"  !! 0 rows for {state} / {commodity} / {market} - skipped", flush=True)
                break
        recs = d.get("records", [])
        if not recs:
            break
        for r in recs:
            out.append({c: r.get(c, r.get(c.lower(), "")) for c in COLUMNS})
        offset += len(recs)
        if len(out) % 250 == 0:  # incremental checkpoint within a long series
            PARTS_DIR.mkdir(parents=True, exist_ok=True)
            part.write_text(json.dumps(out), encoding="utf-8")
        if offset >= total:
            break
        time.sleep(4.0)

    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    part.write_text(json.dumps(out), encoding="utf-8")
    span = f"{out[0]['Arrival_Date']}..{out[-1]['Arrival_Date']}" if out else "empty"
    print(f"  ok {state} / {commodity} / {market}: {len(out)}/{total} rows ({span})", flush=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-pages", type=int, default=95,
                    help="max API calls per series (demo key ~10 rows/call)")
    ap.add_argument("--fresh", action="store_true", help="ignore/clear checkpoints")
    args = ap.parse_args()

    if args.fresh and PARTS_DIR.exists():
        for f in PARTS_DIR.glob("*.json"):
            f.unlink()

    print("using " + ("DATA_GOV_IN_API_KEY from environment"
          if os.environ.get("DATA_GOV_IN_API_KEY", "").strip()
          else "data.gov.in published demo API key"))

    all_rows: list[dict] = []
    for state, commodity, market in SERIES:
        all_rows.extend(pull_series(state, commodity, market, args.limit_pages))

    if not all_rows:
        print("no rows pulled - aborting (check network / API key)")
        sys.exit(1)

    all_rows.sort(key=lambda r: (r["State"], r["Commodity"], r["Market"],
                                 r["Arrival_Date"], r["Variety"], r["Grade"]))
    out_path = RAW_DIR / "india_agmarknet_raw.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS)
    w.writeheader()
    w.writerows(all_rows)
    out_path.write_text(buf.getvalue(), encoding="utf-8")

    n_series = len({(r["State"], r["Commodity"], r["Market"]) for r in all_rows})
    print(f"\nwrote {out_path}  ({len(all_rows):,} rows, {n_series} non-empty series)")
    print("Raw file is now frozen - build with scripts/build_external_datasets.py")


if __name__ == "__main__":
    main()
