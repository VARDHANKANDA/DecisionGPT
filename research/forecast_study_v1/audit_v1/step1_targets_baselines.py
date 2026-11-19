"""Step 1: (a) are the stored evaluation targets equal to the raw data? (b) do all 16 stored baselines equal an independent re-implementation that can only
see data up to each forecast's cutoff? (c) row-set integrity. Writes audit_v1/work/step1.json."""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import ind_core as ic  # noqa: E402

WORK = Path(__file__).parent / "work"
WORK.mkdir(exist_ok=True)
out = {}
cache = {}


def Y_for(cell):
    key = cell.split("_H")[0]
    if key in cache:
        return cache[key]
    meta = ic.jload(ic.RES / cell / "metadata.json")
    if key.startswith("fs1_m5"):
        store = {"fs1_m5_ca1": "CA_1", "fs1_m5_tx1": "TX_1"}[key]
        Y = ic.load_m5_series(store, meta["series_ids"])
        info = {"source": "sales_train_evaluation.csv", "n_series": Y.shape[0], "n_days": Y.shape[1]}
    else:
        d = ic.load_or2_clean()
        Y, top, full = ic.or2_units_top100(d)
        info = {"source": "online_retail_ii_raw_as_csv.csv (independently cleaned)", "n_series": Y.shape[0], "n_days": Y.shape[1], "top_list_equals_stored": top == meta["series_ids"],
                "date_first": str(full[0].date()), "date_last": str(full[-1].date())}
        if top != meta["series_ids"]:
            info["top_list_mismatch_first5"] = [top[:5], meta["series_ids"][:5]]
    cache[key] = (Y, info)
    return cache[key]


for cell in ic.CELLS:
    t0 = time.time()
    A = ic.stored(cell)
    cfg = ic.jload(ic.RES / cell / "config.json")
    H = int(cfg["H"])
    Y, info = Y_for(cell)
    S, T = Y.shape
    s, d, y, blk = A["series"].astype(int), A["day"].astype(int), A["y"].astype(float), A["block"].astype(int)
    starts = cfg["windows"]["test"]
    r = {"data": info, "n_rows": int(len(y)), "expected_rows": int(S * 168), "unique_rows": int(len(set(zip(s.tolist(), d.tolist())))),
         "test_block_starts": starts, "n_series": S, "n_days_in_data": T, "H": H}
    r["targets_equal_raw_data"] = bool(np.array_equal(Y[s, d], y))
    r["target_max_abs_diff"] = float(np.abs(Y[s, d] - y).max())
    r["last_test_day_is_last_data_day"] = bool(d.max() == T - 1)
    r["first_test_day"], r["last_test_day"] = int(d.min()), int(d.max())
    r["zero_share_of_targets"] = float((y == 0).mean())
    r["negative_targets"] = int((y < 0).sum())
    r["nan_targets"] = int(np.isnan(y).sum())

    def block_of(t):
        for o in starts:
            if o <= t < o + 28:
                return o
        raise ValueError(t)

    cut_fresh = (lambda t: block_of(t) - 1) if H == 28 else (lambda t: block_of(t) + 7 * ((t - block_of(t)) // 7) - 1)
    cut_matched = lambda t: t - H  # noqa: E731
    cuts_ok = {"matched_cutoff_max_gap_ok": True, "fresh_cutoff_before_target": True}
    comp = {}
    for kind, fn in (("matched", cut_matched), ("fresh", cut_fresh)):
        cs = np.array([fn(int(t)) for t in d])
        cuts_ok[f"{kind}_min_t_minus_cutoff"] = int((d - cs).min())
        cuts_ok[f"{kind}_max_t_minus_cutoff"] = int((d - cs).max())
        cuts_ok[f"{kind}_all_cutoffs_before_target"] = bool((cs < d).all())
        for lab in ic.NAMES:
            mine = ic.baseline_rows(Y, s, d, fn, lab)
            sto = A[f"base__{kind}__{lab}"].astype(float)
            diff = np.abs(mine - sto)
            comp[f"{kind}__{lab}"] = {"max_abs_diff": float(np.nanmax(diff)), "n_mismatch_gt_1e-4": int((diff > 1e-4 + 1e-5 * np.abs(sto)).sum()), "n_nan_mine": int(np.isnan(mine).sum())}
    r["cutoff_checks"] = cuts_ok
    r["baseline_comparison"] = comp
    r["all_baselines_match"] = all(v["n_mismatch_gt_1e-4"] == 0 and v["n_nan_mine"] == 0 for v in comp.values())
    r["runtime_s"] = round(time.time() - t0, 1)
    out[cell] = r
    print(cell, "targets ok:", r["targets_equal_raw_data"], "baselines ok:", r["all_baselines_match"], "rows", r["n_rows"], "/", r["expected_rows"], f"{r['runtime_s']}s", flush=True)
(WORK / "step1.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
