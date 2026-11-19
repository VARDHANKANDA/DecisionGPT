"""Dataset loader of forecast_study_v3.

Same sampling procedure as ml.benchmark.datasets.load_m5_subset (department-stratified random sample, seeded, price matrix, calendar), with three differences fixed in the protocol:
  1. the series-eligibility cut-off (first non-zero sale on or before day MAX_FIRST_SALE_DAY) is window-specific (848 for W4) so that it uses nothing from the validation or test period;
  2. the 40 series of the retired Training Center benchmark are excluded;
  3. the sample seed is SERIES_SEED.
The function body below is copied from the historical loader (read-only reference) with only those changes; the Dataset object returned is the v2 Dataset class so that the v2 pipeline runs unchanged.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.benchmark import datasets as ds
from research.forecast_study_v2 import data as dat2
from research.forecast_study_v2 import windows as win2

from . import v3common as C


def retired_pairs() -> set[tuple[str, str]]:
    ids = pd.read_csv(C.RETIRED_BENCHMARK_CSV, usecols=["series_id"])["series_id"].unique()
    return {tuple(s.split("__")) for s in ids}      # (item_id, store_id)


def load_m5_subset_v3(store: str, n_series: int = C.N_SERIES, seed: int = C.SERIES_SEED, max_first_sale_day: int = C.MAX_FIRST_SALE_DAY):
    raw = ds.M5_RAW
    cal = pd.read_csv(raw / "calendar.csv")
    cal = cal.iloc[: ds.M5_N_DAYS].reset_index(drop=True)
    dcols = [f"d_{i}" for i in range(1, ds.M5_N_DAYS + 1)]
    id_cols = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
    sales = pd.read_csv(raw / "sales_train_evaluation.csv", dtype={c: "int16" for c in dcols})
    sales = sales[sales["store_id"] == store].reset_index(drop=True)
    y_all = sales[dcols].to_numpy(dtype=np.float32)
    first = np.where(y_all.sum(axis=1) > 0, (y_all > 0).argmax(axis=1) + 1, ds.M5_N_DAYS + 1)
    retired = retired_pairs()
    not_retired = np.array([(it, store) not in retired for it in sales["item_id"]])
    eligible = np.flatnonzero((first <= max_first_sale_day) & not_retired)
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
    prices = pd.read_csv(raw / "sell_prices.csv", dtype={"store_id": "category", "item_id": "category", "wm_yr_wk": "int32", "sell_price": "float32"})
    prices = prices[prices["store_id"] == store]
    prices = prices[prices["item_id"].isin(meta["item_id"].unique())]
    pw = prices.pivot_table(index="item_id", columns="wm_yr_wk", values="sell_price", observed=True)
    wk = cal["wm_yr_wk"].to_numpy()
    price = np.full((len(meta), ds.M5_N_DAYS), np.nan, dtype=np.float32)
    for i, item in enumerate(meta["item_id"]):
        if item in pw.index:
            price[i] = pw.loc[item].reindex(wk).to_numpy(dtype=np.float32)
    snap_col = f"snap_{meta['state_id'].iloc[0]}"
    c = pd.DataFrame({"date": pd.to_datetime(cal["date"]), "dow": pd.to_datetime(cal["date"]).dt.dayofweek.to_numpy(), "month": pd.to_datetime(cal["date"]).dt.month.to_numpy(),
                      "dom": pd.to_datetime(cal["date"]).dt.day.to_numpy(), "event": cal["event_name_1"].notna().astype(int).to_numpy(), "snap": cal[snap_col].astype(int).to_numpy()})
    info = {"store": store, "n_series": int(len(meta)), "n_days": ds.M5_N_DAYS, "seed": seed, "max_first_sale_day": max_first_sale_day, "eligible_series_in_store": int(len(eligible)), "series_in_store": int(len(sales)),
            "excluded_retired_benchmark_series_in_store": int((~not_retired).sum()), "units_sold_on_days_without_price": int(((y > 0) & np.isnan(price)).sum()), "negative_units": int((y < 0).sum()),
            "zero_share": float((y == 0).mean()), "missing_price_share": float(np.isnan(price).mean()), "series_ids": meta["id"].tolist(),
            "source_files": {f.name: ds.sha256_of(f) for f in (raw / "calendar.csv", raw / "sales_train_evaluation.csv", raw / "sell_prices.csv")}}
    if info["negative_units"]:
        raise ValueError("negative unit sales")
    return ds.M5Subset(meta=meta, y=y, price=price, calendar=c, info=info)


_CACHE: dict = {}


def load(key: str, window: str):
    """Drop-in replacement for research.forecast_study_v2.data.load for the v3 stores."""
    if key not in C.STORES:
        return _ORIG_LOAD(key, window)
    store = C.STORES[key]
    if store not in _CACHE:
        _CACHE[store] = load_m5_subset_v3(store)
    m = _CACHE[store]
    T_full = m.y.shape[1]
    Tp = win2.truncated_length(T_full, window)
    static = {k: m.meta[c].astype("category").cat.codes.to_numpy() for k, c in (("dept_code", "dept_id"), ("cat_code", "cat_id"), ("item_code", "item_id"))}
    info = dict(m.info) | {"window": window, "T_trunc": Tp, "first_unused_day_index": Tp}
    info.pop("series_ids", None)
    return dat2.Dataset(key, window, m.y[:, :Tp].copy(), m.price[:, :Tp].copy(), m.calendar.iloc[:Tp].reset_index(drop=True), static, m.meta["id"].tolist(), pd.DatetimeIndex(m.calendar["date"].iloc[:Tp]), (), T_full, info)


_ORIG_LOAD = dat2.load


def install():
    """Patch the v2 modules IN MEMORY (no file is modified): add window W4, the v3 store keys and the v3 loader."""
    win2.OFFSETS[C.WINDOW] = C.WINDOW_OFFSET
    dat2.KEYS = tuple(dat2.KEYS) + tuple(C.STORES)
    dat2.STORE.update(C.STORES)
    dat2.load = load
