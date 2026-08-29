"""Build processed canonical CSVs for the external benchmark datasets.

Reads only the UNMODIFIED raw files in ``data/external/<name>/raw/`` and
writes deterministic, small ``data/external/<name>/processed/*.csv``.
Re-runnable; overwrites the processed files in place.

    python scripts/build_external_datasets.py [--only india]
    python scripts/build_external_datasets.py --retired [--only uci|m5|regional]

Default target is the active **Indian** dataset(s). ``--retired`` rebuilds the
archived non-Indian benchmarks under ``data/external/_retired_non_indian/``
(kept only for historical reproducibility - see that folder's README).

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
    FORECASTING_CANONICAL_COLUMNS,
    india_agmarknet_adapter,
    india_customer_adapter,
    india_ecommerce_adapter,
    india_festival_adapter,
    india_macro_adapter,
)

EXT = ROOT / "data" / "external"
RETIRED = EXT / "_retired_non_indian"


def _write(df: pd.DataFrame, path: Path, rel: str) -> None:
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
    from ml.preprocessing import CHURN_CANONICAL_COLUMNS

    missing = [c for c in CHURN_CANONICAL_COLUMNS if c not in df.columns]
    assert not missing, f"{name}: churn output missing {missing}"
    vc = df["churned"].value_counts().to_dict()
    assert set(df["churned"].unique()) <= {0, 1}, f"{name}: churned not binary"
    assert len(vc) == 2, f"{name}: churn label has one class: {vc}"
    print(f"  [{name}] rows={len(df)} churn_balance={vc}")


# --- active: Indian datasets ------------------------------------------


def build_india() -> None:
    raw = EXT / "india_agmarknet" / "raw"
    print("India Agri-Commodity Daily Market Prices (AGMARKNET / data.gov.in):")
    fc = india_agmarknet_adapter.build_forecasting(raw)
    _check_forecasting(fc, "india_agmarknet_forecasting")
    _write(fc, EXT / "india_agmarknet/processed/india_agmarknet_forecasting.csv",
           "india_agmarknet/processed/india_agmarknet_forecasting.csv")

    an = india_agmarknet_adapter.build_regional_analytics(raw)
    _write(an, EXT / "india_agmarknet/processed/india_agmarknet_regional_analytics.csv",
           "india_agmarknet/processed/india_agmarknet_regional_analytics.csv")


def build_festivals() -> None:
    print("India festival / holiday calendar (holidays lib -> INDIA_PUBLIC_CONTEXT):")
    ev = india_festival_adapter.build_events()
    daily = india_festival_adapter.build_daily()
    _write(ev, EXT / "india_context/festivals/processed/india_festivals.csv",
           "india_context/festivals/processed/india_festivals.csv")
    _write(daily, EXT / "india_context/festivals/processed/india_festival_daily.csv",
           "india_context/festivals/processed/india_festival_daily.csv")


def build_macro() -> None:
    print("India macro context (RBI repo rate -> INDIA_PUBLIC_CONTEXT):")
    df = india_macro_adapter.build_context()
    _write(df, EXT / "india_context/macro/processed/india_macro_context.csv",
           "india_context/macro/processed/india_macro_context.csv")


def build_benroshan() -> None:
    raw = EXT / "india_ecommerce" / "raw"
    print("India e-commerce orders (Benroshan, CC0 -> INDIA_REAL_BUSINESS):")
    an = india_ecommerce_adapter.build_analytics(raw)
    _write(an, EXT / "india_ecommerce/processed/india_ecommerce_analytics.csv",
           "india_ecommerce/processed/india_ecommerce_analytics.csv")
    ta = india_ecommerce_adapter.build_target_attainment(raw)
    _write(ta, EXT / "india_ecommerce/processed/india_ecommerce_target_attainment.csv",
           "india_ecommerce/processed/india_ecommerce_target_attainment.csv")
    fc = india_ecommerce_adapter.build_forecasting(raw)
    _check_forecasting(fc, "india_ecommerce_forecasting")
    _write(fc, EXT / "india_ecommerce/processed/india_ecommerce_forecasting.csv",
           "india_ecommerce/processed/india_ecommerce_forecasting.csv")


def build_kundan() -> None:
    raw = EXT / "india_customer_synthetic" / "raw"
    print("India customer behaviour (Kundan, SIMULATED -> SYNTHETIC_INDIAN_CONTEXT):")
    pp = india_customer_adapter.build_purchase_prediction(raw)
    vc = pp["purchased"].value_counts().to_dict()
    assert set(pp["purchased"].unique()) <= {0, 1} and len(vc) == 2, f"bad target: {vc}"
    _write(pp, EXT / "india_customer_synthetic/processed/india_customer_purchase_prediction.csv",
           "india_customer_synthetic/processed/india_customer_purchase_prediction.csv")
    print(f"  [purchase_prediction] rows={len(pp)} class_balance={vc}")


ACTIVE_BUILDERS = {
    "india": build_india,
    "festivals": build_festivals,
    "macro": build_macro,
    "benroshan": build_benroshan,
    "kundan": build_kundan,
}


# --- retired: non-Indian benchmarks (reproducibility only) -----------


def _retired_builders():
    from ml.preprocessing import (
        m5_adapter,
        supermarket_sales_adapter,
        uci_online_retail_adapter,
    )

    def build_uci() -> None:
        raw = RETIRED / "uci_online_retail" / "raw"
        print("[RETIRED] UCI Online Retail (UK):")
        fc = uci_online_retail_adapter.build_forecasting(raw)
        _check_forecasting(fc, "uci_forecasting")
        _write(fc, RETIRED / "uci_online_retail/processed/uci_forecasting.csv",
               "_retired_non_indian/uci_online_retail/processed/uci_forecasting.csv")
        rfm = uci_online_retail_adapter.build_customer_rfm(raw)
        _write(rfm, RETIRED / "uci_online_retail/processed/uci_customer_rfm.csv",
               "_retired_non_indian/uci_online_retail/processed/uci_customer_rfm.csv")
        churn = uci_online_retail_adapter.build_churn_derived(raw)
        _check_churn(churn, "uci_churn_derived")
        _write(churn, RETIRED / "uci_online_retail/processed/uci_churn_derived.csv",
               "_retired_non_indian/uci_online_retail/processed/uci_churn_derived.csv")

    def build_m5() -> None:
        raw = RETIRED / "m5_forecasting" / "raw"
        print("[RETIRED] M5 Forecasting (USA):")
        fc = m5_adapter.build_forecasting(raw)
        _check_forecasting(fc, "m5_forecasting")
        _write(fc, RETIRED / "m5_forecasting/processed/m5_forecasting.csv",
               "_retired_non_indian/m5_forecasting/processed/m5_forecasting.csv")

    def build_regional() -> None:
        raw = RETIRED / "regional_retail" / "raw"
        print("[RETIRED] Supermarket Sales (Myanmar):")
        fc = supermarket_sales_adapter.build_forecasting(raw)
        _check_forecasting(fc, "regional_retail_forecasting")
        _write(fc, RETIRED / "regional_retail/processed/regional_retail_forecasting.csv",
               "_retired_non_indian/regional_retail/processed/regional_retail_forecasting.csv")
        an = supermarket_sales_adapter.build_analytics(raw)
        _write(an, RETIRED / "regional_retail/processed/regional_retail_analytics.csv",
               "_retired_non_indian/regional_retail/processed/regional_retail_analytics.csv")

    return {"uci": build_uci, "m5": build_m5, "regional": build_regional}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retired", action="store_true",
                    help="rebuild the archived non-Indian benchmarks instead")
    ap.add_argument("--only", default=None)
    args = ap.parse_args()

    builders = _retired_builders() if args.retired else ACTIVE_BUILDERS
    if args.only and args.only not in builders:
        ap.error(f"--only must be one of {list(builders)} "
                 f"({'retired' if args.retired else 'active'} set)")
    todo = [args.only] if args.only else list(builders)
    for key in todo:
        try:
            builders[key]()
        except FileNotFoundError as exc:
            print(f"  SKIP {key}: {exc}")
    print("done.")


if __name__ == "__main__":
    main()
