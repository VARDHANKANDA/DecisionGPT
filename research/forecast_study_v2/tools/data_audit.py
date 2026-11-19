"""Measure dataset/window properties from the raw files (read-only) -> results/data_audit.json. Used by DATA_AUDIT.md."""
import json

import numpy as np

from research.forecast_study_v2 import data as dat
from research.forecast_study_v2 import windows as win
from research.forecast_study_v2.common import RESULTS, atomic_write_json, sha256_file, ROOT

out = {"raw_file_sha256": {}, "datasets": {}}
for rel in ("data/external/m5_forecasting/raw/calendar.csv", "data/external/m5_forecasting/raw/sales_train_evaluation.csv", "data/external/m5_forecasting/raw/sell_prices.csv",
            "data/external/uci_online_retail_ii/processed/online_retail_ii_raw_as_csv.csv"):
    out["raw_file_sha256"][rel] = sha256_file(ROOT / rel)
for key in dat.KEYS:
    for w in win.OFFSETS:
        try:
            d = dat.load(key, w)
        except win.Infeasible as e:
            out["datasets"][f"{key}_{w}"] = {"infeasible": str(e)}
            continue
        r = {"T_trunc": d.T, "T_full": d.T_full, "series": int(d.y.shape[0]), "date_first": str(d.dates[0].date()), "date_last_used": str(d.dates[-1].date()),
             "zero_share_all_days": float((d.y == 0).mean()), "negative_values": int((d.y < 0).sum()), "nan_values": int(np.isnan(d.y).sum()),
             "share_series_days_without_price_listing": float(np.isnan(d.price).mean()) if key != "or2" else None, "units_on_days_without_price": int(((d.y > 0) & np.isnan(d.price)).sum()) if key != "or2" else None}
        for H in win.HORIZONS:
            try:
                b = win.blocks(d.T, H)
            except win.Infeasible:
                continue
            lo, hi = b["val"][0], b["test"][-1] + win.BLOCK - 1
            seg = dat.segments(d.y, b["val"][0])
            r[f"H{H}"] = {"validation_blocks": b["val"], "test_blocks": b["test"], "scored_span_days": [lo, hi], "scored_span_dates": [str(d.dates[lo].date()), str(d.dates[hi].date())],
                          "test_zero_share_all_rows": float((d.y[:, b["test"][0]: hi + 1] == 0).mean()),
                          "segment_counts": {k: {v: int((np.array(seg[k]) == v).sum()) for v in sorted(set(seg[k]))} for k in ("frequency", "volume")}, "segment_history_days": seg["history_days_used"]}
        r["info"] = {k: v for k, v in d.info.items() if k in ("eligible_series_in_store", "series_in_store", "max_first_sale_day", "dept_counts", "rows_in", "rows_kept", "dropped", "sku_rule", "first_validation_day_index")}
        out["datasets"][f"{key}_{w}"] = r
        print(key, w, "ok", flush=True)
atomic_write_json(RESULTS / "data_audit.json", out)
