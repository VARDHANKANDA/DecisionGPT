"""Dataset loaders with validation for the public benchmark data.

Raw files under ``data/external/*/raw`` are never modified. Loaders read them, validate schema / dates / duplicates / missingness,
and return plain numpy / pandas objects together with an ``info`` dict that is stored with every run.

Datasets (see ``data/external/DATASET_REGISTRY.json`` for source, licence and checksums):
  * M5 Forecasting Accuracy (Walmart; hierarchical daily unit sales, calendar, weekly selling prices)
  * UCI Online Retail II (one UK online retailer; invoice lines)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
M5_RAW = ROOT / "data" / "external" / "m5_forecasting" / "raw"
OR2_CSV = ROOT / "data" / "external" / "uci_online_retail_ii" / "processed" / "online_retail_ii_raw_as_csv.csv"

M5_LAST_TRAIN_DAY = 1913  # last day of the original M5 training file; days 1914-1941 are the official evaluation window
M5_N_DAYS = 1941
NON_PRODUCT_CODES = {"ADJUST", "AMAZONFEE", "B", "BANK CHARGES", "C2", "CRUK", "D", "DOT", "GIFT", "M", "PADS", "POST", "S",
                     "TEST001", "TEST002"}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------ M5
@dataclass
class M5Subset:
    meta: pd.DataFrame          # one row per series: id, item_id, dept_id, cat_id, store_id
    y: np.ndarray               # (n_series, 1941) float32 units sold
    price: np.ndarray           # (n_series, 1941) float32 selling price; NaN where the item was not on sale that week
    calendar: pd.DataFrame      # 1941 rows: date, weekday index, month, day of month, event flag, snap flag
    info: dict[str, Any]


def load_m5_subset(store: str = "CA_1", n_series: int = 350, seed: int = 20261015, max_first_sale_day: int = 1100,
                   raw_dir: Path | None = None) -> M5Subset:
    """Seeded, department-stratified sample of one store's series (the full 30,490-series table does not fit the 8 GB machine
    comfortably together with feature matrices). Eligibility: the first non-zero sale on or before ``max_first_sale_day`` so
    every series has >= 2 years of history before the validation origins."""
    raw = raw_dir or M5_RAW
    cal = pd.read_csv(raw / "calendar.csv")
    if len(cal) < M5_N_DAYS or cal["d"].iloc[M5_N_DAYS - 1] != f"d_{M5_N_DAYS}":
        raise ValueError(f"calendar does not contain days d_1..d_{M5_N_DAYS} in order ({len(cal)} rows)")
    cal = cal.iloc[:M5_N_DAYS].reset_index(drop=True)  # the file also lists 28 future days that have no sales
    dcols = [f"d_{i}" for i in range(1, M5_N_DAYS + 1)]
    id_cols = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
    dtypes = {c: "int16" for c in dcols}
    sales = pd.read_csv(raw / "sales_train_evaluation.csv", dtype=dtypes)
    missing = [c for c in id_cols + dcols if c not in sales.columns]
    if missing:
        raise ValueError(f"sales file is missing {missing[:5]}")
    sales = sales[sales["store_id"] == store].reset_index(drop=True)
    if sales.empty:
        raise ValueError(f"no series for store {store}")
    y_all = sales[dcols].to_numpy(dtype=np.float32)
    first = np.where(y_all.sum(axis=1) > 0, (y_all > 0).argmax(axis=1) + 1, M5_N_DAYS + 1)  # 1-based day of the first sale
    eligible = np.flatnonzero(first <= max_first_sale_day)
    rng = np.random.default_rng(seed)
    dept = sales.loc[eligible, "dept_id"].to_numpy()
    chosen: list[int] = []
    depts = sorted(set(dept))
    share = {d: (dept == d).sum() / len(dept) for d in depts}
    for d in depts:
        pool = eligible[dept == d]
        k = max(1, int(round(n_series * share[d])))
        chosen.extend(rng.choice(pool, size=min(k, len(pool)), replace=False).tolist())
    chosen = sorted(chosen)[: n_series if len(chosen) > n_series else len(chosen)]
    meta = sales.loc[chosen, id_cols].reset_index(drop=True)
    y = y_all[chosen]
    # weekly prices -> daily matrix through the calendar's wm_yr_wk
    prices = pd.read_csv(raw / "sell_prices.csv", dtype={"store_id": "category", "item_id": "category", "wm_yr_wk": "int32", "sell_price": "float32"})
    prices = prices[prices["store_id"] == store]
    prices = prices[prices["item_id"].isin(meta["item_id"].unique())]
    pw = prices.pivot_table(index="item_id", columns="wm_yr_wk", values="sell_price", observed=True)
    wk = cal["wm_yr_wk"].to_numpy()
    price = np.full((len(meta), M5_N_DAYS), np.nan, dtype=np.float32)
    for i, item in enumerate(meta["item_id"]):
        if item in pw.index:
            row = pw.loc[item]
            price[i] = row.reindex(wk).to_numpy(dtype=np.float32)
    snap_col = f"snap_{meta['state_id'].iloc[0]}"
    c = pd.DataFrame({
        "date": pd.to_datetime(cal["date"]),
        "dow": pd.to_datetime(cal["date"]).dt.dayofweek.to_numpy(),
        "month": pd.to_datetime(cal["date"]).dt.month.to_numpy(),
        "dom": pd.to_datetime(cal["date"]).dt.day.to_numpy(),
        "event": cal["event_name_1"].notna().astype(int).to_numpy(),
        "snap": cal[snap_col].astype(int).to_numpy(),
    })
    on_sale = ~np.isnan(price)
    sold_off_sale = int(((y > 0) & ~on_sale).sum())
    info = {
        "store": store, "n_series": int(len(meta)), "n_days": M5_N_DAYS, "seed": seed, "max_first_sale_day": max_first_sale_day,
        "eligible_series_in_store": int(len(eligible)), "series_in_store": int(len(sales)),
        "dept_counts": meta["dept_id"].value_counts().sort_index().to_dict(),
        "date_first": str(c["date"].iloc[0].date()), "date_last": str(c["date"].iloc[-1].date()),
        "zero_share": float((y == 0).mean()), "missing_price_share": float(np.isnan(price).mean()),
        "units_sold_on_days_without_price": sold_off_sale,
        "negative_units": int((y < 0).sum()),
        "series_ids": meta["id"].tolist(),
        "source_files": {f.name: sha256_of(f) for f in (raw / "calendar.csv", raw / "sales_train_evaluation.csv", raw / "sell_prices.csv") if f.exists()},
    }
    if info["negative_units"]:
        raise ValueError("negative unit sales in M5 subset")
    return M5Subset(meta=meta, y=y, price=price, calendar=c, info=info)


# ------------------------------------------------------------------------------------------------ Online Retail II
def load_online_retail_ii(path: Path | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Clean product sales lines. Rules (stored in ``info``): drop cancellations (invoice starts with 'C'), non-positive quantity or
    price, non-product stock codes, and exact duplicate lines. Rows without a customer id are kept for demand forecasting and
    excluded from customer-level tasks by the caller."""
    p = path or OR2_CSV
    raw = pd.read_csv(p, dtype={"Invoice": str, "StockCode": str}, parse_dates=["InvoiceDate"])
    need = {"Invoice", "StockCode", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"}
    if need - set(raw.columns):
        raise ValueError(f"Online Retail II file is missing {sorted(need - set(raw.columns))}")
    n0 = len(raw)
    d = raw
    reasons: dict[str, int] = {}

    def drop(mask, name):
        nonlocal d
        reasons[name] = int(mask.sum())
        d = d[~mask]

    drop(d["Invoice"].str.startswith("C"), "cancellation_invoice")
    drop(d["Quantity"] <= 0, "non_positive_quantity")
    drop(d["Price"] <= 0, "non_positive_price")
    drop(d["StockCode"].isin(NON_PRODUCT_CODES), "non_product_stock_code")
    drop(d.duplicated(["Invoice", "StockCode", "Quantity", "InvoiceDate", "Price", "Customer ID"]), "exact_duplicate_line")
    d = d.copy()
    d["revenue"] = d["Quantity"] * d["Price"]
    d["day"] = d["InvoiceDate"].dt.normalize()
    info = {"rows_in": n0, "rows_kept": int(len(d)), "dropped": reasons,
            "date_first": str(d["day"].min().date()), "date_last": str(d["day"].max().date()),
            "customers": int(d["Customer ID"].nunique()), "rows_without_customer": int(d["Customer ID"].isna().sum()),
            "source_sha256": sha256_of(p), "currency": "GBP (not stated by the source for each line; UK retailer)"}
    return d.reset_index(drop=True), info


def daily_series(d: pd.DataFrame, value: str = "revenue") -> pd.Series:
    """Calendar-complete daily sum. Closed days (e.g. the retailer never trades on Saturdays) are real zeros, not missing."""
    g = d.groupby("day")[value].sum()
    full = pd.date_range(g.index.min(), g.index.max(), freq="D")
    return g.reindex(full, fill_value=0.0).rename_axis("date").rename(value)
