"""F2: demand forecasting on UCI Online Retail II (one real UK online retailer, 2009-12-01 .. 2011-12-09).

Two targets, one protocol (direct horizon H=28, three rolling validation windows, untouched final 28 days):
  * ``total_daily_revenue``  - one series (calendar-complete; closed days are real zeros)
  * ``top20_sku_daily_units``- the 20 SKUs with the largest revenue BEFORE the first validation origin (a rule that uses only past data)
No price covariates are used: realised prices are not known in advance for a future day, so price/availability features are dropped.
Calendar flags are rules known in advance (weekday, day of month, month, Christmas/New-Year closure window).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.benchmark import datasets as ds
from ml.benchmark import direct
from ml.benchmark import models as zoo

H = 28
TRAIN_SPAN = 730


def _calendar(dates: pd.DatetimeIndex) -> pd.DataFrame:
    xmas = ((dates.month == 12) & (dates.day >= 24)) | ((dates.month == 1) & (dates.day <= 3))
    return pd.DataFrame({"date": dates, "dow": dates.dayofweek.to_numpy(), "month": dates.month.to_numpy(), "dom": dates.day.to_numpy(),
                         "event": xmas.astype(int), "snap": np.zeros(len(dates), dtype=int)})


def build_arrays(d: pd.DataFrame, top_k: int = 20, first_val_origin: int | None = None):
    full = pd.date_range(d["day"].min(), d["day"].max(), freq="D")
    rev = d.groupby("day")["revenue"].sum().reindex(full, fill_value=0.0).to_numpy(dtype=np.float32)
    units = d.pivot_table(index="StockCode", columns="day", values="Quantity", aggfunc="sum", fill_value=0).reindex(columns=full, fill_value=0)
    cut = full[first_val_origin] if first_val_origin is not None else full[-1]
    revenue_by_sku = d[d["day"] < cut].groupby("StockCode")["revenue"].sum()
    top = revenue_by_sku.nlargest(top_k).index.tolist()
    return full, rev[None, :], units.loc[top].to_numpy(dtype=np.float32), top


def run_f2(seed: int = 42, families: dict[str, list[str]] | None = None, log=print) -> dict:
    d, info = ds.load_online_retail_ii()
    full, rev, _, _ = build_arrays(d)
    T = len(full)
    test_lo = T - H
    val_origins = [test_lo - H * k for k in (3, 2, 1)]
    full, rev, sku_units, top = build_arrays(d, first_val_origin=val_origins[0])
    cal = _calendar(full)
    fams = families or {f: list(v) for f, v in zoo.GRID.items()}
    out = {"dataset": info, "top_skus": top, "calendar": {"first": str(full[0].date()), "last": str(full[-1].date()), "days": T},
           "test_window": [str(full[test_lo].date()), str(full[-1].date())],
           "validation_windows": [[str(full[o].date()), str(full[o + H - 1].date())] for o in val_origins]}
    tasks = {
        "total_daily_revenue": rev,
        "top20_sku_daily_units": sku_units,
    }
    preds = {}
    for name, Y in tasks.items():
        n = Y.shape[0]
        static = {"dept_code": np.zeros(n), "cat_code": np.zeros(n), "item_code": np.arange(n)}
        price = np.ones_like(Y, dtype=np.float32)
        r = direct.run_direct(Y, price, cal, static, H=H, test_lo=test_lo, val_origins=val_origins, train_span=TRAIN_SPAN, families=fams,
                              seed=seed, drop_features=direct.PRICE_FEATURES + ("dept_code", "cat_code"), min_history=84, log=log)
        out[name] = r["results"]
        preds[name] = r["predictions"]
    return {"results": out, "predictions": preds}
