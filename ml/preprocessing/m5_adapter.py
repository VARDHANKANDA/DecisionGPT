"""M5 Forecasting -> DecisionGPT forecasting canonical schema.

Raw (unmodified) in ``data/external/m5_forecasting/raw/``:
  * ``sales_train_evaluation.csv`` — wide daily unit sales (d_1 .. d_1941)
  * ``calendar.csv``               — d_* -> real date + wm_yr_wk
  * ``sell_prices.csv``            — weekly sell_price per (store_id, item_id, wm_yr_wk)

Output: ``series_id, date, units_sold, price, marketing_spend, promotion_flag``
for a deterministic top-N (item x store) subsample. ``marketing_spend`` and
``promotion_flag`` are held at 0 — M5 has no such signal (not invented).

See ``data/external/m5_forecasting/metadata.md``.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

SEED = 42
DEFAULT_N_SERIES = 40


def _raw(raw_dir: str | Path, name: str) -> Path:
    p = Path(raw_dir) / name
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found. Obtain the M5 files per docs/DATASET_DOWNLOAD_INSTRUCTIONS.md."
        )
    return p


def build_forecasting(raw_dir: str | Path, n_series: int = DEFAULT_N_SERIES) -> pd.DataFrame:
    sales = pd.read_csv(_raw(raw_dir, "sales_train_evaluation.csv"))
    calendar = pd.read_csv(_raw(raw_dir, "calendar.csv"), usecols=["date", "wm_yr_wk"])
    # calendar rows are in day order; row i (0-indexed) is d_{i+1}. There is
    # no 'd' column in the raw file.
    calendar.insert(0, "d", [f"d_{i + 1}" for i in range(len(calendar))])

    id_cols = ["item_id", "dept_id", "cat_id", "store_id", "state_id"]
    d_cols = [c for c in sales.columns if c.startswith("d_")]

    # Deterministic subsample: top-N (item x store) by total units.
    totals = sales[d_cols].to_numpy().sum(axis=1)
    order = pd.Series(totals, index=sales.index)
    sales = sales.assign(_total=order).sort_values(
        ["_total", "item_id", "store_id"], ascending=[False, True, True]
    )
    sales = sales.head(n_series).drop(columns=["_total"]).reset_index(drop=True).copy()

    long = sales.melt(
        id_vars=id_cols, value_vars=d_cols, var_name="d", value_name="units_sold"
    )
    long = long.merge(calendar, on="d", how="left")
    long["date"] = pd.to_datetime(long["date"])
    long["series_id"] = long["item_id"].astype(str) + "__" + long["store_id"].astype(str)

    # Weekly sell_price -> daily. Filter sell_prices to the chosen
    # (store, item) pairs with a vectorised key match (the raw file is ~7M
    # rows, so a row-wise apply is far too slow).
    keep_items = set(sales["item_id"])
    keep_stores = set(sales["store_id"])
    prices = pd.read_csv(_raw(raw_dir, "sell_prices.csv"))
    prices = prices[prices["item_id"].isin(keep_items) & prices["store_id"].isin(keep_stores)]
    pair_keys = set(zip(sales["store_id"], sales["item_id"]))
    prices = prices[
        [(s, i) in pair_keys for s, i in zip(prices["store_id"], prices["item_id"])]
    ]
    long = long.merge(
        prices.rename(columns={"sell_price": "price"}),
        on=["store_id", "item_id", "wm_yr_wk"],
        how="left",
    )
    long = long.sort_values(["series_id", "date"])
    long["price"] = long.groupby("series_id")["price"].ffill().bfill()

    # Drop rows before a series has any recorded price, and trim each
    # series' leading run of zero sales (pre-launch).
    long = long.dropna(subset=["price"])
    long["_cum"] = long.groupby("series_id")["units_sold"].cumsum()
    long = long[long["_cum"] > 0]

    long["marketing_spend"] = 0.0
    long["promotion_flag"] = 0
    out = long[
        ["series_id", "date", "units_sold", "price", "marketing_spend", "promotion_flag"]
    ].copy()
    out["units_sold"] = out["units_sold"].astype(int)
    out["price"] = out["price"].round(2)
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out.sort_values(["series_id", "date"]).reset_index(drop=True)
