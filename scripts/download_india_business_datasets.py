"""Download the openly-licensed Indian business datasets that DecisionGPT
evaluated and integrated (docs/INDIAN_DATASET_EVALUATION.md).

These are pulled from Kaggle's **public** dataset-download endpoint, which
serves CC0 / CC-BY datasets to anonymous clients (no login, no API token, no
ToS bypass - the dataset owners licensed them for open redistribution).

    python scripts/download_india_business_datasets.py [--only benroshan|kundan]

Raw files are written verbatim under ``data/external/<name>/raw/`` and are
never modified afterwards (``scripts/build_external_datasets.py`` reads them
read-only). ``raw/`` is gitignored.
"""
from __future__ import annotations

import argparse
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "data" / "external"

# name -> (kaggle owner/slug, licence, raw subdir, expected members)
DATASETS = {
    "benroshan": (
        "benroshan/ecommerce-data",
        "CC0: Public Domain",
        "india_ecommerce/raw",
        ["List of Orders.csv", "Order Details.csv", "Sales target.csv"],
    ),
    "kundan": (
        "kundanbedmutha/indian-e-commerce-customer-behavior-and-purchase",
        "CC BY 4.0",
        "india_customer_synthetic/raw",
        ["Ecommerce.csv"],
    ),
}

_URL = "https://www.kaggle.com/api/v1/datasets/download/{slug}"


def _fetch(slug: str) -> bytes:
    req = urllib.request.Request(_URL.format(slug=slug), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def pull(name: str) -> None:
    slug, licence, subdir, members = DATASETS[name]
    print(f"{name}: {slug}  ({licence})")
    try:
        blob = _fetch(slug)
    except Exception as exc:  # noqa: BLE001
        print(f"  FAILED to download ({exc}).")
        print(f"  Manual: open https://www.kaggle.com/datasets/{slug} and place the "
              f"files under {EXT / subdir}/")
        return
    dest = EXT / subdir
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        got = z.namelist()
        for member in got:
            z.extract(member, dest)
        print(f"  wrote {len(got)} file(s) to {dest}: {got}")
    missing = [m for m in members if not (dest / m).exists()]
    if missing:
        print(f"  WARNING: expected members not found: {missing}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(DATASETS), default=None)
    args = ap.parse_args()
    names = [args.only] if args.only else list(DATASETS)
    for name in names:
        pull(name)
    print("\nRaw files are now frozen - build with scripts/build_external_datasets.py")
    if not any((EXT / DATASETS[n][2]).exists() for n in names):
        sys.exit(1)


if __name__ == "__main__":
    main()
