"""Supermarket Sales (Myanmar) -> DecisionGPT forecasting canonical schema
+ a descriptive analytics table.

Raw (unmodified): ``data/external/regional_retail/raw/supermarket_sales.csv``.

Output:
  * forecasting : ``series_id, date, units_sold, price, marketing_spend,
    promotion_flag`` — daily units per ``Branch|Product line`` (18 series,
    ~89 days; small — illustrative only).
  * analytics   : adds ``revenue, cogs, gross_income, margin_pct`` — NOT
    consumed by any model; for descriptive analytics in the paper.

``marketing_spend`` / ``promotion_flag`` are held at 0 (no such field).

See ``data/external/regional_retail/metadata.md``. This dataset is Myanmar,
NOT India.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def _raw(raw_dir: str | Path) -> Path:
    p = Path(raw_dir) / "supermarket_sales.csv"
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found. Download per docs/DATASET_DOWNLOAD_INSTRUCTIONS.md."
        )
    return p


def _daily(raw_dir: str | Path) -> pd.DataFrame:
    df = pd.read_csv(_raw(raw_dir))
    df["date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
    df["series_id"] = "SS_" + df["Branch"].astype(str) + "|" + df["Product line"].astype(str)
    df["line_revenue"] = df["Unit price"] * df["Quantity"]
    g = df.groupby(["series_id", "date"])
    daily = g.agg(
        units_sold=("Quantity", "sum"),
        line_revenue=("line_revenue", "sum"),
        revenue=("Total", "sum"),
        cogs=("Cost of goods sold", "sum"),
        gross_income=("Gross income", "sum"),
    ).reset_index()
    daily["price"] = (daily["line_revenue"] / daily["units_sold"]).round(2)
    return daily


def build_forecasting(raw_dir: str | Path) -> pd.DataFrame:
    daily = _daily(raw_dir)
    daily["marketing_spend"] = 0.0
    daily["promotion_flag"] = 0
    out = daily[
        ["series_id", "date", "units_sold", "price", "marketing_spend", "promotion_flag"]
    ].copy()
    out["units_sold"] = out["units_sold"].astype(int)
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out.sort_values(["series_id", "date"]).reset_index(drop=True)


def build_analytics(raw_dir: str | Path) -> pd.DataFrame:
    daily = _daily(raw_dir)
    daily["margin_pct"] = (daily["gross_income"] / daily["revenue"]).round(4)
    out = daily[
        ["series_id", "date", "units_sold", "price", "revenue", "cogs", "gross_income", "margin_pct"]
    ].copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out.sort_values(["series_id", "date"]).reset_index(drop=True)
