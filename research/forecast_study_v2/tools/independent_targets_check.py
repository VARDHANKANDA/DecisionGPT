"""Independent rebuild of the evaluation targets from the raw files, compared with the arrays the study code builds (every dataset, every window).
The raw files are read directly with pandas; only the series IDS of the sampled entities (a seeded draw whose rule is documented in DATA_AUDIT.md) are taken from the study loader.
Writes results/independent_targets_check.json. Run before the freeze (targets are data, not outcomes)."""
import numpy as np
import pandas as pd

from research.forecast_study_v2 import data as dat
from research.forecast_study_v2 import windows as win
from research.forecast_study_v2.common import ROOT, RESULTS, atomic_write_json

RAW = ROOT / "data" / "external" / "m5_forecasting" / "raw"
NON_PRODUCT = {"ADJUST", "AMAZONFEE", "B", "BANK CHARGES", "C2", "CRUK", "D", "DOT", "GIFT", "M", "PADS", "POST", "S", "TEST001", "TEST002"}
out = {}

sales = pd.read_csv(RAW / "sales_train_evaluation.csv", usecols=lambda c: c in ("id", "store_id") or c.startswith("d_"))
cal = pd.read_csv(RAW / "calendar.csv")
prices = pd.read_csv(RAW / "sell_prices.csv", dtype={"store_id": "category", "item_id": "category"})
dcols = [f"d_{i}" for i in range(1, 1942)]
for key, store in dat.STORE.items():
    sub = sales[sales["store_id"] == store].set_index("id")
    for w in win.OFFSETS:
        d = dat.load(key, w)
        raw = sub.loc[d.series_ids, dcols].to_numpy(dtype=float)[:, : d.T]
        r = {"targets_equal_raw": bool(np.array_equal(raw, d.y)), "series": len(d.series_ids), "T_trunc": d.T, "last_day_used_is_d": f"d_{d.T}", "dates_match_calendar": bool((pd.to_datetime(cal["date"].iloc[: d.T]).to_numpy() == d.dates.to_numpy()).all()),
             "negative": int((raw < 0).sum()), "nan": int(np.isnan(raw).sum())}
        # price availability: an item-week without a listing must carry zero demand (the eligible-row rule relies on this)
        if w == "W1":
            items = [i.rsplit(f"_{store}_", 1)[0] for i in d.series_ids]
            pr = prices[(prices["store_id"] == store) & (prices["item_id"].isin(set(items)))]
            wk = cal["wm_yr_wk"].to_numpy()[: d.T]
            listed = {(it, int(w_)) for it, w_ in zip(pr["item_id"].astype(str), pr["wm_yr_wk"])}
            bad = 0
            for i, it in enumerate(items):
                for t in np.flatnonzero(raw[i] > 0):
                    if (it, int(wk[t])) not in listed:
                        bad += 1
            r["positive_demand_days_without_price_listing"] = int(bad)
        out[f"{key}_{w}"] = r
        print(key, w, r["targets_equal_raw"], flush=True)

# Online Retail II
raw = pd.read_csv(ROOT / "data" / "external" / "uci_online_retail_ii" / "processed" / "online_retail_ii_raw_as_csv.csv", dtype={"Invoice": str, "StockCode": str}, parse_dates=["InvoiceDate"])
n0 = len(raw)
c = raw[~raw["Invoice"].str.startswith("C")]
c = c[(c["Quantity"] > 0) & (c["Price"] > 0) & ~c["StockCode"].isin(NON_PRODUCT)]
c = c[~c.duplicated(["Invoice", "StockCode", "Quantity", "InvoiceDate", "Price", "Customer ID"])].copy()
c["day"] = c["InvoiceDate"].dt.normalize()
c["rev"] = c["Quantity"] * c["Price"]
full = pd.date_range(c["day"].min(), c["day"].max(), freq="D")
for w in ("W1", "W2"):
    d = dat.load("or2", w)
    Tp = d.T
    first_val = win.blocks(Tp, 28)["val"][0]
    top = c[c["day"] < full[first_val]].groupby("StockCode")["rev"].sum().sort_values(ascending=False, kind="mergesort").head(100).index.tolist()
    u = c[(c["StockCode"].isin(top)) & (c["day"] < (full[Tp] if Tp < len(full) else full[-1] + pd.Timedelta(days=1)))].groupby(["StockCode", "day"])["Quantity"].sum().unstack(fill_value=0).reindex(index=top, columns=full[:Tp], fill_value=0)
    r = {"sku_list_equal": top == d.series_ids, "targets_equal_raw": bool(np.array_equal(u.to_numpy(dtype=float), d.y.astype(float))), "T_trunc": Tp, "date_last_used": str(full[Tp - 1].date()), "rows_in": n0, "rows_kept": int(len(c))}
    out[f"or2_{w}"] = r
    print("or2", w, r["sku_list_equal"], r["targets_equal_raw"], flush=True)
atomic_write_json(RESULTS / "independent_targets_check.json", out)
print("all equal:", all(v.get("targets_equal_raw") and v.get("sku_list_equal", True) for v in out.values()))
