"""India Agri-Commodity Daily Market Prices (AGMARKNET) -> DecisionGPT canonical.

Source : Open Government Data (OGD) Platform India - data.gov.in, resource
         35985678-0d79-46b4-9ed6-6f13308a1d24 "Variety-wise Daily Market
         Prices Data of Commodity". Directorate of Marketing & Inspection
         (DMI), Ministry of Agriculture & Farmers Welfare, Government of India.
Licence: Government Open Data License - India (GODL-India).
Raw    : data/external/india_agmarknet/raw/india_agmarknet_raw.csv
         (fixed columns: Arrival_Date, State, District, Market, Commodity,
          Variety, Grade, Min_Price, Max_Price, Modal_Price). Never modified.

Registry category: INDIA_AGRICULTURAL_PRICE. This is Indian agricultural
commodity WHOLESALE price data - a supplementary Indian price-series
benchmark. It is NOT Indian SME retail transaction data.

IMPORTANT - this source has NO transaction-quantity field. This is therefore
a PRICE-forecasting benchmark: the canonical ``units_sold`` column is reused
to carry the **daily modal price (INR / quintal)** that the model forecasts.
Nothing is fabricated - ``modal_price`` is real, ``marketing_spend`` /
``promotion_flag`` are held at 0 (absent in the source), and the ``price``
feature is a strictly backward-looking rolling median (no leakage). The raw
``modal_price`` / ``min_price`` / ``max_price`` are also emitted as extra
self-documenting columns (the trainer selects only the canonical ones).
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

SEED = 42
RAW_FILENAME = "india_agmarknet_raw.csv"
PRICE_LEVEL_WINDOW = 28          # days; backward rolling median for the 'price' feature
MIN_SERIES_ROWS = 60            # drop thin (commodity x market) series


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value).strip()).strip("_").upper() or "NA"


def _raw_path(raw_dir) -> Path:
    p = Path(raw_dir) / RAW_FILENAME
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found - run scripts/download_india_datasets.py first "
            "(see docs/DATASET_DOWNLOAD_INSTRUCTIONS.md)."
        )
    return p


def load_clean(raw_dir) -> pd.DataFrame:
    """Parse + structurally clean the raw pull. One row per
    (series_id, date): multiple variety/grade quotes on the same day are
    collapsed to their median. No imputation, no synthetic rows."""
    df = pd.read_csv(_raw_path(raw_dir), dtype=str)

    df["date"] = pd.to_datetime(df["Arrival_Date"], format="%d/%m/%Y", errors="coerce")
    for col in ("Min_Price", "Max_Price", "Modal_Price"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["date", "Modal_Price", "Commodity", "Market", "State"])
    df = df[(df["Modal_Price"] > 0) & (df["Max_Price"] >= df["Min_Price"])]

    df["series_id"] = "MANDI_" + df["Commodity"].map(_slug) + "__" + df["Market"].map(_slug)

    grouped = (
        df.groupby(["series_id", "date", "State", "Commodity", "Market"], as_index=False)
        .agg(
            modal_price=("Modal_Price", "median"),
            min_price=("Min_Price", "median"),
            max_price=("Max_Price", "median"),
        )
        .sort_values(["series_id", "date"])
        .reset_index(drop=True)
    )
    return grouped


def build_forecasting(raw_dir) -> pd.DataFrame:
    """Canonical forecasting frame. ``units_sold`` = daily modal price
    (INR/quintal); ``price`` = 28-day backward rolling median of modal price
    (shifted 1 day - strictly past information)."""
    g = load_clean(raw_dir)

    counts = g.groupby("series_id")["date"].transform("size")
    g = g[counts >= MIN_SERIES_ROWS].copy()

    def _level(s: pd.Series) -> pd.Series:
        return s.shift(1).rolling(PRICE_LEVEL_WINDOW, min_periods=5).median()

    g["price"] = g.groupby("series_id")["modal_price"].transform(_level)
    # leading rows: fall back to the series' first observed modal price
    # (known at t0 - not future information)
    first_modal = g.groupby("series_id")["modal_price"].transform("first")
    g["price"] = g["price"].fillna(first_modal)
    g = g[g["price"] > 0]

    out = pd.DataFrame(
        {
            "series_id": g["series_id"].to_numpy(),
            "date": g["date"].dt.strftime("%Y-%m-%d").to_numpy(),
            "units_sold": g["modal_price"].astype(float).to_numpy(),
            "price": g["price"].astype(float).round(2).to_numpy(),
            "marketing_spend": 0.0,
            "promotion_flag": 0,
            "modal_price": g["modal_price"].astype(float).to_numpy(),
            "min_price": g["min_price"].astype(float).to_numpy(),
            "max_price": g["max_price"].astype(float).to_numpy(),
        }
    )
    return out.sort_values(["series_id", "date"]).reset_index(drop=True)


def build_regional_analytics(raw_dir) -> pd.DataFrame:
    """State x Commodity x month descriptive table - price level, volatility,
    spread and breadth. Not consumed by any training task."""
    g = load_clean(raw_dir)
    g["month"] = g["date"].dt.to_period("M").dt.to_timestamp()
    g["spread_pct"] = ((g["max_price"] - g["min_price"]) / g["modal_price"]).clip(lower=0)

    agg = (
        g.groupby(["State", "Commodity", "month"], as_index=False)
        .agg(
            avg_modal_price=("modal_price", "mean"),
            price_volatility_std=("modal_price", "std"),
            avg_spread_pct=("spread_pct", "mean"),
            active_markets=("Market", "nunique"),
            observations=("modal_price", "size"),
        )
        .sort_values(["State", "Commodity", "month"])
        .reset_index(drop=True)
    )
    agg["price_volatility_std"] = agg["price_volatility_std"].fillna(0.0).round(2)
    agg["avg_modal_price"] = agg["avg_modal_price"].round(2)
    agg["avg_spread_pct"] = agg["avg_spread_pct"].round(4)
    agg["mom_pct_change"] = (
        agg.groupby(["State", "Commodity"])["avg_modal_price"].pct_change().round(4)
    )
    agg["month"] = agg["month"].dt.strftime("%Y-%m-%d")
    return agg


# convenience alias used by some callers
build_analytics = build_regional_analytics
