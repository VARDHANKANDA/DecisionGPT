"""Datasets of forecast_study_v2, built from the raw files and TRUNCATED to the window length before any feature, baseline, segment or entity selection is computed.

Entities
  * M5 stores (CA_1, TX_1, WI_1): a department-stratified random sample of 350 series per store among series whose first sale falls on or before day d_1100 (the repository's historical
    loader, unchanged). The rule uses nothing after day 1100, so it is identical for every window.
  * Online Retail II: the 100 SKUs with the largest revenue BEFORE the window's first validation block (re-selected per window, so no information from a window's own validation or test period
    selects its entities). Daily gross units after the repository's documented cleaning rules (cancellations, non-positive quantity or price, non-product codes, exact duplicate lines dropped).

Eligible rows: a (series, day) row is evaluated when the M5 item has a selling price listed on that day (days without a listing carry zero demand by construction) and enough history exists; the same
rows are used for every method. Online Retail II has no price file; every day with enough history is eligible.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from ml.benchmark import datasets as ds
from ml.benchmark import f2_retail as f2

from . import windows as win

KEYS = ("m5_ca1", "m5_tx1", "m5_wi1", "or2")
STORE = {"m5_ca1": "CA_1", "m5_tx1": "TX_1", "m5_wi1": "WI_1"}
M5_N_SERIES = 350
OR2_DROP = ("sell_price", "rel_price_91", "price_change_7", "days_since_price_change", "dept_code", "cat_code")


@dataclass
class Dataset:
    key: str
    window: str
    y: np.ndarray               # [series, T'] units
    price: np.ndarray           # [series, T'] (ones for Online Retail II)
    cal: pd.DataFrame           # T' rows
    static: dict[str, np.ndarray]
    series_ids: list[str]
    dates: pd.DatetimeIndex
    drop_features: tuple[str, ...]
    T_full: int
    info: dict[str, Any] = field(default_factory=dict)

    @property
    def T(self) -> int:
        return self.y.shape[1]


@lru_cache(maxsize=4)
def _m5(store: str):
    m = ds.load_m5_subset(store=store, n_series=M5_N_SERIES)
    return m


@lru_cache(maxsize=1)
def _or2_raw():
    d, info = ds.load_online_retail_ii()
    return d, info


def load(key: str, window: str) -> Dataset:
    if key in STORE:
        m = _m5(STORE[key])
        T_full = m.y.shape[1]
        Tp = win.truncated_length(T_full, window)
        static = {k: m.meta[c].astype("category").cat.codes.to_numpy() for k, c in (("dept_code", "dept_id"), ("cat_code", "cat_id"), ("item_code", "item_id"))}
        info = dict(m.info) | {"window": window, "T_trunc": Tp, "first_unused_day_index": Tp}
        info.pop("series_ids", None)
        return Dataset(key, window, m.y[:, :Tp].copy(), m.price[:, :Tp].copy(), m.calendar.iloc[:Tp].reset_index(drop=True), static, m.meta["id"].tolist(),
                       pd.DatetimeIndex(m.calendar["date"].iloc[:Tp]), (), T_full, info)
    if key == "or2":
        d, info0 = _or2_raw()
        full = pd.date_range(d["day"].min(), d["day"].max(), freq="D")
        T_full = len(full)
        Tp = win.truncated_length(T_full, window)
        first_val = win.blocks(Tp, 28)["val"][0]
        cut = full[Tp] if Tp < len(full) else full[-1] + pd.Timedelta(days=1)
        dd = d[d["day"] < cut]                                        # nothing at or after the first unused day is read
        revenue = dd[dd["day"] < full[first_val]].groupby("StockCode")["revenue"].sum()
        top = revenue.sort_values(ascending=False, kind="mergesort").head(100).index.tolist()
        units = dd[dd["StockCode"].isin(top)].groupby(["StockCode", "day"])["Quantity"].sum().unstack(fill_value=0).reindex(index=top, columns=full[:Tp], fill_value=0)
        y = units.to_numpy(dtype=np.float32)
        n = y.shape[0]
        static = {"dept_code": np.zeros(n), "cat_code": np.zeros(n), "item_code": np.arange(n)}
        info = {"rows_in": info0["rows_in"], "rows_kept": info0["rows_kept"], "dropped": info0["dropped"], "source_sha256": info0["source_sha256"], "window": window, "T_trunc": Tp, "first_unused_day_index": Tp,
                "date_first": str(full[0].date()), "date_last_used": str(full[Tp - 1].date()), "sku_rule": "top-100 revenue before the first validation block of the window", "first_validation_day_index": first_val}
        return Dataset(key, window, y, np.ones_like(y, dtype=np.float32), f2._calendar(full[:Tp]), static, [str(s) for s in top], pd.DatetimeIndex(full[:Tp]), OR2_DROP, T_full, info)
    raise ValueError(key)


def segments(y: np.ndarray, first_val_start: int, history: int = 365) -> dict[str, Any]:
    """Demand-frequency (ADI/CV^2) and volume segments from the days before the first validation block (at most ``history`` days; nothing from validation or test)."""
    h = y[:, max(0, first_val_start - history): first_val_start].astype(float)
    nz = (h > 0).sum(axis=1)
    adi = np.where(nz > 0, h.shape[1] / np.maximum(nz, 1), np.inf)
    cv2 = np.array([((v.std() / v.mean()) ** 2 if v.size > 1 else 0.0) for v in (row[row > 0] for row in h)])
    freq = np.where(adi < 1.32, "frequent", "intermittent_or_sparse")
    pattern = np.where(adi < 1.32, np.where(cv2 < 0.49, "smooth", "erratic"), np.where(cv2 < 0.49, "intermittent", "lumpy"))
    mean = h.mean(axis=1)
    c1, c2 = np.quantile(mean, [1 / 3, 2 / 3])
    vol = np.where(mean <= c1, "low", np.where(mean <= c2, "mid", "high"))
    return {"frequency": freq.tolist(), "pattern": pattern.tolist(), "volume": vol.tolist(), "history_days_used": int(h.shape[1])}
