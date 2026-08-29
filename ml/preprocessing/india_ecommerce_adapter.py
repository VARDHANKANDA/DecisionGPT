"""Indian e-commerce orders (Benroshan "Ecommerce data") -> DecisionGPT canonical.

Source : Kaggle `benroshan/ecommerce-data` (CC0: Public Domain), mirrored in
         several public repos. "Sales details from Indian e-commerce website"
         - the uploader states it came from their university, original author
         unknown, so PROVENANCE IS UNVERIFIED. Treated as INDIA_REAL_BUSINESS
         with that caveat recorded in the metadata.
Files  : data/external/india_ecommerce/raw/{List of Orders.csv, Order Details.csv,
         Sales target.csv}. Never modified.

Fields that EXIST: order id/date, customer name, state, city, product
category/sub-category, quantity, Amount (= line revenue in INR), Profit,
monthly per-category Target.
Fields that DO NOT exist (never invented): unit price, discount, ship date,
marketing spend, inventory, customer id, churn label. ``price`` in the
forecasting frame is a DERIVED implied unit price (revenue / quantity),
documented as such; ``marketing_spend`` / ``promotion_flag`` are held at 0.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

SEED = 42


def _raw(raw_dir) -> Path:
    p = Path(raw_dir)
    if not (p / "List of Orders.csv").exists():
        raise FileNotFoundError(
            f"{p}/List of Orders.csv not found - run "
            "scripts/download_india_business_datasets.py --only benroshan first."
        )
    return p


def load_clean(raw_dir) -> pd.DataFrame:
    """Join orders + line items, structurally cleaned. No imputation, no
    synthetic rows. One row per order line."""
    p = _raw(raw_dir)
    orders = pd.read_csv(p / "List of Orders.csv").dropna(how="all").drop_duplicates()
    details = pd.read_csv(p / "Order Details.csv")

    orders = orders.rename(columns={"Order ID": "order_id", "CustomerName": "customer_name"})
    orders["order_date"] = pd.to_datetime(orders["Order Date"], dayfirst=True, errors="coerce")
    orders = orders.dropna(subset=["order_id", "order_date"])
    orders["State"] = orders["State"].str.strip()

    details = details.rename(
        columns={"Order ID": "order_id", "Amount": "revenue", "Profit": "profit",
                 "Quantity": "quantity", "Sub-Category": "sub_category", "Category": "category"}
    )
    details = details.dropna(subset=["order_id", "revenue", "quantity"])
    details = details[details["quantity"] > 0]

    merged = details.merge(
        orders[["order_id", "order_date", "customer_name", "State", "City"]],
        on="order_id", how="inner",
    )
    return merged.sort_values(["order_date", "order_id"]).reset_index(drop=True)


def _targets(raw_dir) -> pd.DataFrame:
    p = _raw(raw_dir)
    t = pd.read_csv(p / "Sales target.csv").rename(
        columns={"Month of Order Date": "month_label", "Category": "category", "Target": "target"}
    )
    t["month"] = pd.to_datetime(t["month_label"], format="%b-%y", errors="coerce")
    return t.dropna(subset=["month"])


def build_analytics(raw_dir) -> pd.DataFrame:
    """category x state descriptive table: orders, units, revenue, profit,
    margin, average order value. Not consumed by any training task."""
    m = load_clean(raw_dir)
    agg = (
        m.groupby(["category", "State"], as_index=False)
        .agg(orders=("order_id", "nunique"), line_items=("order_id", "size"),
             units=("quantity", "sum"), revenue=("revenue", "sum"), profit=("profit", "sum"))
        .sort_values(["category", "State"])
        .reset_index(drop=True)
    )
    agg["margin_pct"] = (agg["profit"] / agg["revenue"]).round(4)
    agg["avg_order_value"] = (agg["revenue"] / agg["orders"]).round(2)
    agg["revenue"] = agg["revenue"].round(2)
    agg["profit"] = agg["profit"].round(2)
    return agg


def build_target_attainment(raw_dir) -> pd.DataFrame:
    """monthly per-category actual revenue vs the dataset's own Target."""
    m = load_clean(raw_dir)
    m["month"] = m["order_date"].dt.to_period("M").dt.to_timestamp()
    actual = m.groupby(["category", "month"], as_index=False).agg(actual_revenue=("revenue", "sum"))
    out = actual.merge(_targets(raw_dir)[["category", "month", "target"]], on=["category", "month"], how="left")
    out["attainment_pct"] = (out["actual_revenue"] / out["target"]).round(4)
    out["month"] = out["month"].dt.strftime("%Y-%m-%d")
    return out.sort_values(["category", "month"]).reset_index(drop=True)


def build_forecasting(raw_dir) -> pd.DataFrame:
    """Small daily total-units series for a forecasting benchmark.

    NOTE: this dataset is small (~500 orders / 12 months). The forecasting
    frame is a single zero-filled daily series; ``price`` is a DERIVED implied
    unit price (daily revenue / daily units, ffilled). Use for a *small*
    benchmark only - the analytics table above is the primary output.
    """
    m = load_clean(raw_dir)
    daily = (
        m.groupby(m["order_date"].dt.normalize())
        .agg(units_sold=("quantity", "sum"), revenue=("revenue", "sum"))
        .rename_axis("date")
        .reset_index()
    )
    full = pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")
    daily = daily.set_index("date").reindex(full).rename_axis("date").reset_index()
    daily["units_sold"] = daily["units_sold"].fillna(0.0)
    daily["revenue"] = daily["revenue"].fillna(0.0)

    implied = (daily["revenue"] / daily["units_sold"]).replace([float("inf"), -float("inf")], pd.NA)
    daily["price"] = implied.ffill().bfill().round(2)

    out = pd.DataFrame({
        "series_id": "IEC_TOTAL",
        "date": daily["date"].dt.strftime("%Y-%m-%d"),
        "units_sold": daily["units_sold"].astype(float),
        "price": daily["price"].astype(float),
        "marketing_spend": 0.0,
        "promotion_flag": 0,
    })
    return out.reset_index(drop=True)


def _slug(v: str) -> str:  # kept for parity with other adapters / future per-category series
    return re.sub(r"[^A-Za-z0-9]+", "_", str(v).strip()).strip("_").upper() or "NA"
