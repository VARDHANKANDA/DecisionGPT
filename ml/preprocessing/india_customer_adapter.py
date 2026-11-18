"""Indian e-commerce customer behaviour (Kundan Bedmutha) -> purchase-prediction frame.

Source : Kaggle `kundanbedmutha/indian-e-commerce-customer-behavior-and-purchase`
         (CC BY 4.0). The dataset description explicitly says the 25,000 rows
         are "generated to simulate realistic online shopping behavior in the
         Indian market" -> this is SIMULATED DATA. Category:
         SYNTHETIC_INDIAN_CONTEXT. Its results are never combined with any
         real-world Indian result.
File   : data/external/india_customer_synthetic/raw/Ecommerce.csv. Never modified.

Task supported: purchase prediction (binary ``purchased``). NOT churn - there
is no churn target; ``cart_abandoned`` is a near-complement of ``purchased``
and is EXCLUDED as leakage, not relabelled as churn.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

SEED = 42
TARGET = "purchased"

# Pre-decision behavioural + pricing signals only. Deliberately EXCLUDED:
#   revenue / revenue_normalized  -> non-zero iff purchased (target leak)
#   cart_abandoned                -> near-complement of the target (leak)
#   rating / review_* / session_duration_bucket -> post-purchase fields
#   *_id columns, visit_date      -> identifiers / raw date
FEATURE_COLUMNS = [
    "unit_price", "quantity", "discount_percent", "discount_amount",
    "pages_viewed", "time_on_site_sec", "added_to_cart",
    "device_type", "user_type", "marketing_channel", "product_category",
    "visit_month", "visit_weekday", "visit_season",
]


def _raw(raw_dir) -> Path:
    p = Path(raw_dir) / "Ecommerce.csv"
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found - run "
            "scripts/download_india_business_datasets.py --only kundan first."
        )
    return p


def build_purchase_prediction(raw_dir) -> pd.DataFrame:
    """Return a modelling frame: FEATURE_COLUMNS + ``purchased`` target.
    Deterministic; no imputation beyond dropping rows missing a feature/target."""
    df = pd.read_csv(_raw(raw_dir))
    keep = [c for c in FEATURE_COLUMNS if c in df.columns] + [TARGET]
    missing = set(FEATURE_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"expected columns absent from source: {sorted(missing)}")
    out = df[keep].dropna().reset_index(drop=True)
    out[TARGET] = out[TARGET].astype(int)
    return out
