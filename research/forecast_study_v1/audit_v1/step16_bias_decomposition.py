"""Step 16 (read-only diagnostic for the manuscript revision): where does the matched trailing median's under-forecast come from?
(a) share of the bias in rows with a zero forecast vs rows with a positive forecast; (b) bias of the matched trailing MEAN over the same 28-day window (same information, different functional);
(c) mean-to-median ratio of positive daily demand per series (skewness diagnostic). Writes work/step16.json."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import ind_core as ic  # noqa: E402

out = {}
for cell in ic.CELLS:
    A = ic.stored(cell)
    y, s = A["y"].astype(float), A["series"].astype(int)
    med = A["base__matched__trailing_median28"].astype(float)
    mean = A["base__matched__trailing_mean28"].astype(float)
    tot = y.sum()
    z = med == 0
    r = {"bias_median": float((med - y).sum() / tot), "bias_trailing_mean_same_window": float((mean - y).sum() / tot),
         "bias_share_from_zero_forecast_rows": float((med[z] - y[z]).sum() / tot), "bias_share_from_positive_forecast_rows": float((med[~z] - y[~z]).sum() / tot),
         "zero_forecast_row_share": float(z.mean()), "demand_share_in_zero_forecast_rows": float(y[z].sum() / tot),
         "sum_median_forecast_over_sum_demand_in_positive_forecast_rows": float(med[~z].sum() / max(y[~z].sum(), 1e-12))}
    # skewness diagnostic: per series, mean / median of positive demand days in the test rows (weighted by demand)
    ratios, w = [], []
    for k in np.unique(s):
        v = y[(s == k) & (y > 0)]
        if v.size >= 5:
            ratios.append(v.mean() / np.median(v))
            w.append(v.sum())
    r["demand_weighted_mean_over_median_of_positive_days"] = float(np.average(ratios, weights=w))
    out[cell] = r
    print(cell, {k: round(v, 3) for k, v in r.items()})
(Path(__file__).parent / "work" / "step16.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
