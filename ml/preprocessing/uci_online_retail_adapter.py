"""UCI Online Retail -> DecisionGPT canonical schemas.

Raw: ``data/external/uci_online_retail/raw/Online Retail.xlsx`` (unmodified).

Produces:
  * forecasting  : daily units per product (top-N by volume)
  * customer RFM : recency / frequency / monetary per customer
  * churn (DERIVED, optional): inactivity label with a strict time-aware
    observation/holdout split — features use the observation window only,
    so there is no future leakage.

See ``data/external/uci_online_retail/metadata.md`` for the full definition.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42

# Observation / holdout boundary for the DERIVED churn label. The raw data
# spans 2010-12-01 .. 2011-12-09; ~9 months observation, ~3 months holdout.
OBSERVATION_END = pd.Timestamp("2011-09-09")
DATA_END = pd.Timestamp("2011-12-09")

# StockCodes that are not real products (postage, fees, adjustments, ...).
NON_PRODUCT_CODES = {
    "POST", "DOT", "M", "m", "C2", "BANK CHARGES", "AMAZONFEE", "S", "D",
    "CRUK", "PADS", "B", "gift_0001_10", "gift_0001_20", "gift_0001_30",
    "gift_0001_40", "gift_0001_50",
}


def _raw_path(raw_dir: str | Path) -> Path:
    p = Path(raw_dir) / "Online Retail.xlsx"
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found. Download per docs/DATASET_DOWNLOAD_INSTRUCTIONS.md "
            "(UCI ML Repository dataset 352)."
        )
    return p


def load_clean(raw_dir: str | Path) -> pd.DataFrame:
    """Raw transactions with cancellations / invalid rows removed. Used by
    both the forecasting and customer/churn builders."""
    df = pd.read_excel(
        _raw_path(raw_dir),
        usecols=["InvoiceNo", "StockCode", "Description", "Quantity",
                 "InvoiceDate", "UnitPrice", "CustomerID", "Country"],
    )
    df["InvoiceNo"] = df["InvoiceNo"].astype(str)
    df["StockCode"] = df["StockCode"].astype(str)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])

    df = df[~df["InvoiceNo"].str.startswith("C")]              # cancellations
    df = df[df["Quantity"] > 0]
    df = df[df["UnitPrice"] > 0]
    df = df[~df["StockCode"].isin(NON_PRODUCT_CODES)]
    df = df[~df["StockCode"].str.fullmatch(r"[A-Za-z]+")]      # letter-only codes
    df = df.drop_duplicates()
    df["line_revenue"] = df["Quantity"] * df["UnitPrice"]
    return df.reset_index(drop=True)


# --- forecasting -----------------------------------------------------------


def build_forecasting(raw_dir: str | Path, top_n_products: int = 40) -> pd.DataFrame:
    clean = load_clean(raw_dir)
    clean = clean.dropna(subset=["StockCode"])
    clean["date"] = clean["InvoiceDate"].dt.floor("D")

    totals = clean.groupby("StockCode")["Quantity"].sum().sort_values(ascending=False)
    keep = list(totals.head(top_n_products).index)
    sub = clean[clean["StockCode"].isin(keep)]

    daily = (
        sub.groupby(["StockCode", "date"])
        .agg(units_sold=("Quantity", "sum"), revenue=("line_revenue", "sum"))
        .reset_index()
    )
    daily["price"] = (daily["revenue"] / daily["units_sold"]).round(2)
    daily["series_id"] = "UCI_" + daily["StockCode"].astype(str)
    daily["marketing_spend"] = 0.0
    daily["promotion_flag"] = 0
    out = daily[
        ["series_id", "date", "units_sold", "price", "marketing_spend", "promotion_flag"]
    ].copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out.sort_values(["series_id", "date"]).reset_index(drop=True)


# --- customer RFM + DERIVED churn ---------------------------------------


def build_customer_rfm(raw_dir: str | Path) -> pd.DataFrame:
    """RFM over the whole observation window (customers with an id)."""
    clean = load_clean(raw_dir).dropna(subset=["CustomerID"])
    clean["CustomerID"] = clean["CustomerID"].astype(int).astype(str)
    obs = clean[clean["InvoiceDate"] <= OBSERVATION_END]

    g = obs.groupby("CustomerID")
    rfm = pd.DataFrame(
        {
            "first_purchase": g["InvoiceDate"].min(),
            "last_purchase": g["InvoiceDate"].max(),
            "frequency": g["InvoiceNo"].nunique(),
            "monetary_value": g["line_revenue"].sum().round(2),
        }
    )
    rfm["tenure_days"] = (OBSERVATION_END - rfm["first_purchase"]).dt.days.clip(lower=1)
    rfm["recency_days"] = (OBSERVATION_END - rfm["last_purchase"]).dt.days.clip(lower=0)
    rfm["avg_order_value"] = (rfm["monetary_value"] / rfm["frequency"]).round(2)
    return rfm.reset_index()


def build_churn_derived(raw_dir: str | Path) -> pd.DataFrame:
    """DERIVED CHURN LABEL. Time-aware: features from the observation
    window only; label from holdout-window activity. No future leakage."""
    clean = load_clean(raw_dir).dropna(subset=["CustomerID"])
    clean["CustomerID"] = clean["CustomerID"].astype(int).astype(str)

    obs = clean[clean["InvoiceDate"] <= OBSERVATION_END]
    holdout = clean[
        (clean["InvoiceDate"] > OBSERVATION_END) & (clean["InvoiceDate"] <= DATA_END)
    ]

    active_obs = set(obs["CustomerID"].unique())
    active_holdout = set(holdout["CustomerID"].unique())

    rfm = build_customer_rfm(raw_dir)
    rfm = rfm[rfm["CustomerID"].isin(active_obs)].copy()
    rfm["churned"] = (~rfm["CustomerID"].isin(active_holdout)).astype(int)

    out = rfm[
        [
            "tenure_days", "recency_days", "frequency",
            "avg_order_value", "monetary_value", "churned",
        ]
    ].copy()
    # guard against any inf from degenerate rows
    out = out.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)
    return out
