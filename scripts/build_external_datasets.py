"""Build processed canonical CSVs for every external benchmark dataset.

Reads only the UNMODIFIED raw files in ``data/external/<name>/raw/`` and
writes deterministic, small ``data/external/<name>/processed/*.csv``.
Re-runnable; overwrites the processed files in place.

    python scripts/build_external_datasets.py [--only uci|m5|regional]

Raw files must be present first (see docs/DATASET_DOWNLOAD_INSTRUCTIONS.md).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from ml.preprocessing import (  # noqa: E402
    CHURN_CANONICAL_COLUMNS,
    FORECASTING_CANONICAL_COLUMNS,
    m5_adapter,
    supermarket_sales_adapter,
    uci_online_retail_adapter,
)

EXT = ROOT / "data" / "external"


def _write(df: pd.DataFrame, rel: str) -> None:
    path = EXT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"  wrote {rel}: {len(df):,} rows x {df.shape[1]} cols")


def _check_forecasting(df: pd.DataFrame, name: str) -> None:
    missing = [c for c in FORECASTING_CANONICAL_COLUMNS if c not in df.columns]
    assert not missing, f"{name}: forecasting output missing {missing}"
    assert df["units_sold"].ge(0).all(), f"{name}: negative units_sold"
    assert df["price"].gt(0).all(), f"{name}: non-positive price"
    per_series = df.groupby("series_id").size()
    usable_series = int((per_series >= 30).sum())
    print(f"  [{name}] series={df['series_id'].nunique()} "
          f"(>=30 rows: {usable_series}) date {df['date'].min()}..{df['date'].max()}")


def _check_churn(df: pd.DataFrame, name: str) -> None:
    missing = [c for c in CHURN_CANONICAL_COLUMNS if c not in df.columns]
    assert not missing, f"{name}: churn output missing {missing}"
    vc = df["churned"].value_counts().to_dict()
    assert set(df["churned"].unique()) <= {0, 1}, f"{name}: churned not binary"
    assert len(vc) == 2, f"{name}: churn label has one class: {vc}"
    print(f"  [{name}] rows={len(df)} churn_balance={vc}")


def build_uci() -> None:
    raw = EXT / "uci_online_retail" / "raw"
    print("UCI Online Retail:")
    fc = uci_online_retail_adapter.build_forecasting(raw)
    _check_forecasting(fc, "uci_forecasting")
    _write(fc, "uci_online_retail/processed/uci_forecasting.csv")

    rfm = uci_online_retail_adapter.build_customer_rfm(raw)
    _write(rfm, "uci_online_retail/processed/uci_customer_rfm.csv")

    churn = uci_online_retail_adapter.build_churn_derived(raw)
    _check_churn(churn, "uci_churn_derived")
    _write(churn, "uci_online_retail/processed/uci_churn_derived.csv")


def build_m5() -> None:
    raw = EXT / "m5_forecasting" / "raw"
    print("M5 Forecasting:")
    fc = m5_adapter.build_forecasting(raw)
    _check_forecasting(fc, "m5_forecasting")
    _write(fc, "m5_forecasting/processed/m5_forecasting.csv")


def build_regional() -> None:
    raw = EXT / "regional_retail" / "raw"
    print("Supermarket Sales (regional, Myanmar):")
    fc = supermarket_sales_adapter.build_forecasting(raw)
    _check_forecasting(fc, "regional_retail_forecasting")
    _write(fc, "regional_retail/processed/regional_retail_forecasting.csv")

    an = supermarket_sales_adapter.build_analytics(raw)
    _write(an, "regional_retail/processed/regional_retail_analytics.csv")


BUILDERS = {"uci": build_uci, "m5": build_m5, "regional": build_regional}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(BUILDERS), default=None)
    args = ap.parse_args()
    todo = [args.only] if args.only else list(BUILDERS)
    for key in todo:
        try:
            BUILDERS[key]()
        except FileNotFoundError as exc:
            print(f"  SKIP {key}: {exc}")
    print("done.")


if __name__ == "__main__":
    main()
