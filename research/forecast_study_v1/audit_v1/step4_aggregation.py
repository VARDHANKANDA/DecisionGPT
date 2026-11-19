"""Step 4: why does the ranking reverse between item-day pooled WAPE and store(subset)-day aggregate WAPE? Decomposition from stored predictions.
Also independently recomputes the demand segments from the raw histories. Writes work/step4.json."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import ind_core as ic  # noqa: E402

AUD = Path(__file__).parent
out = {}
cache = {}


def raw_Y(cell):
    key = cell.split("_H")[0]
    if key not in cache:
        meta = ic.jload(ic.RES / cell / "metadata.json")
        if "m5" in key:
            cache[key] = ic.load_m5_series({"fs1_m5_ca1": "CA_1", "fs1_m5_tx1": "TX_1"}[key], meta["series_ids"])
        else:
            cache[key] = ic.or2_units_top100(ic.load_or2_clean())[0]
    return cache[key]


def segments(Y, first_val):
    h = Y[:, first_val - 365: first_val]
    nz = (h > 0).sum(axis=1)
    adi = np.where(nz > 0, 365 / np.maximum(nz, 1), np.inf)
    cv2 = np.array([((v.std() / v.mean()) ** 2 if v.size > 1 else 0.0) for v in (row[row > 0] for row in h)])
    pattern = np.where(adi < 1.32, np.where(cv2 < 0.49, "smooth", "erratic"), np.where(cv2 < 0.49, "intermittent", "lumpy"))
    freq = np.where(adi < 1.32, "frequent", "intermittent_or_sparse")
    mean = h.mean(axis=1)
    c1, c2 = np.quantile(mean, [1 / 3, 2 / 3])
    vol = np.where(mean <= c1, "low", np.where(mean <= c2, "mid", "high"))
    return {"pattern": pattern, "frequency": freq, "volume": vol}


for cell in ic.CELLS:
    A = ic.stored(cell)
    sel = ic.jload(ic.RES / cell / "selection.json")
    cfg = ic.jload(ic.RES / cell / "config.json")
    seg_stored = ic.jload(ic.RES / cell / "segments.json")
    y, s, d, blk = A["y"].astype(float), A["series"].astype(int), A["day"].astype(int), A["block"].astype(int)
    day0 = cfg["windows"]["test"][0]
    Y = raw_Y(cell)
    first_val = cfg["windows"]["val"][0]
    segs = segments(Y, first_val)
    r = {"segment_labels_match_stored": {k: bool(np.array_equal(segs[k], np.array(seg_stored[k]))) for k in segs},
         "segment_counts_independent": {k: {v: int((segs[k] == v).sum()) for v in sorted(set(segs[k]))} for k in segs}}
    prim = A["pred__" + sel["primary_learned_config"].replace(":", "__")].astype(float)
    ref = A["base__" + sel["reference_baseline_matched_information"]].astype(float)
    tot = np.abs(y).sum()

    def level_stats(p):
        e = p - y
        return {"pooled_wape": ic.wape(y, p), "item_week_wape": ic.week_agg_wape(y, p, s, d, day0), "subset_day_aggregate_wape": ic.agg_wape(y, p, d),
                "abs_relative_bias": abs(float(e.sum() / tot)), "relative_bias": float(e.sum() / tot)}

    # store-week: sum all series and each 7-day block
    def store_week(p):
        w = (d - day0) // 7
        a = pd.Series(p - y).groupby(w).sum()
        b = pd.Series(y).groupby(w).sum()
        return float(np.abs(a).sum() / b.sum())

    for nm, p in (("model", prim), ("matched_median_reference", ref)):
        st = level_stats(p)
        st["subset_week_aggregate_wape"] = store_week(p)
        st["aggregate_minus_abs_bias"] = st["subset_day_aggregate_wape"] - st["abs_relative_bias"]
        sc = tot / p.sum()                                              # global multiplicative bias correction (DIAGNOSTIC ONLY: uses test totals)
        st["after_global_scale_correction"] = {"scale": float(sc), "pooled_wape": ic.wape(y, p * sc), "subset_day_aggregate_wape": ic.agg_wape(y, p * sc, d)}
        st["identity_aggregate_wape_ge_abs_bias_holds"] = bool(st["subset_day_aggregate_wape"] >= st["abs_relative_bias"] - 1e-12)
        r[nm] = st
    # segment decomposition of the pooled comparison and of the bias
    seg_tab = {}
    for dim, lab in segs.items():
        for v in sorted(set(lab)):
            m = np.isin(s, np.flatnonzero(lab == v))
            e_m, e_b = np.abs(prim[m] - y[m]).sum(), np.abs(ref[m] - y[m]).sum()
            seg_tab[f"{dim}={v}"] = {"n_series": int((lab == v).sum()), "share_of_total_demand": float(y[m].sum() / tot), "share_of_rows_with_zero_demand": float((y[m] == 0).mean()),
                                     "model_abs_err_share_of_total_demand": float(e_m / tot), "ref_abs_err_share_of_total_demand": float(e_b / tot),
                                     "contribution_to_pooled_wape_gap_(ref_minus_model)": float((e_b - e_m) / tot),
                                     "model_bias_contribution": float((prim[m] - y[m]).sum() / tot), "ref_bias_contribution": float((ref[m] - y[m]).sum() / tot),
                                     "ref_share_of_forecasts_exactly_zero": float((ref[m] == 0).mean()), "model_share_of_forecasts_below_0.05": float((prim[m] < 0.05).mean()),
                                     "share_of_this_segment_demand_in_rows_where_ref_forecasts_zero": float(y[m][ref[m] == 0].sum() / max(y[m].sum(), 1e-12))}
    r["segments"] = seg_tab
    r["gap_pooled_wape_ref_minus_model"] = float(ic.wape(y, ref) - ic.wape(y, prim))
    r["ref_forecast_exactly_zero_share_overall"] = float((ref == 0).mean())
    r["ref_zero_forecast_on_positive_demand_rows"] = float(((ref == 0) & (y > 0)).sum() / max((y > 0).sum(), 1))
    r["total_demand_in_rows_where_ref_forecasts_zero_share"] = float(y[ref == 0].sum() / tot)
    r["demand_share_top_decile_series"] = float(np.sort(pd.Series(y).groupby(s).sum().to_numpy())[::-1][: max(1, len(np.unique(s)) // 10)].sum() / tot)
    out[cell] = r
    print(cell, "segments match:", r["segment_labels_match_stored"], "| agg>=|bias|:", r["model"]["identity_aggregate_wape_ge_abs_bias_holds"], r["matched_median_reference"]["identity_aggregate_wape_ge_abs_bias_holds"], flush=True)
(AUD / "work" / "step4.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
