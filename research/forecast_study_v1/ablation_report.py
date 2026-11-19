"""H5 (exploratory): feature-group ablations against the main run of the same cell.

``python -m research.forecast_study_v1.ablation_report fs1_m5_ca1_H28``  ->  ``results/ABLATIONS_<cell>.json``

Every ablated run reuses the main run's selected variant (no re-tuning) and is scored on the SAME rows; the comparison is the paired crossed-bootstrap relative WAPE
change of the ablated model against the full-feature model (positive = removing the group made the forecast WORSE, i.e. the group helped). Holm over the ablations.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from research.forecast_study_v1 import inference as inf
from research.forecast_study_v1 import metrics as mt

RESULTS = Path(__file__).resolve().parent / "results"


def report(cell: str) -> dict:
    main = np.load(RESULTS / cell / "predictions.npz")
    sel = json.load(open(RESULTS / cell / "selection.json", encoding="utf-8"))
    cfg = json.load(open(RESULTS / cell / "config.json", encoding="utf-8"))
    seg = json.load(open(RESULTS / cell / "segments.json", encoding="utf-8"))
    key = "pred__" + sel["primary_learned_config"].replace(":", "__")
    S, day0 = len(seg["adi"]), cfg["windows"]["test"][0]
    rows = {}
    for d in sorted(RESULTS.glob(f"{cell}_ablate_*")):
        z = np.load(d / "predictions.npz")
        if not (np.array_equal(z["series"], main["series"]) and np.array_equal(z["day"], main["day"])):
            rows[d.name] = {"error": "rows differ from the main run: not comparable"}
            continue
        y = main["y"].astype(float)
        cells = inf.cell_matrices(main["series"], main["day"], y, {"full": main[key].astype(float), "ablated": z[key].astype(float)}, S, day0, 7)
        r = inf.crossed_bootstrap(cells["N"]["ablated"], cells["N"]["full"], cells["D"], B=1000)
        # crossed_bootstrap(a=ablated, b=full) is "improvement of full over ablated": positive = the removed group helped
        rows[d.name] = {"removed_groups": json.load(open(d / "config.json", encoding="utf-8"))["dropped_features"], "wape_full": mt.wape(y, main[key]), "wape_ablated": mt.wape(y, z[key]),
                        "relative_change_when_removed": (mt.wape(y, z[key]) - mt.wape(y, main[key])) / mt.wape(y, main[key]), "full_vs_ablated": {k: r[k] for k in ("estimate", "ci95", "p_two_sided")}}
    adj = inf.holm({k: v["full_vs_ablated"]["p_two_sided"] for k, v in rows.items() if "full_vs_ablated" in v})
    for k in rows:
        if "full_vs_ablated" in rows[k]:
            rows[k]["holm_p"] = adj[k]
    out = {"cell": cell, "label": "EXPLORATORY (H5): no re-tuning; Holm over the ablations run", "primary": key, "ablations": rows}
    (RESULTS / f"ABLATIONS_{cell}.json").write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    return out


if __name__ == "__main__":
    for c in sys.argv[1:]:
        print(json.dumps(report(c), indent=1, default=float)[:3000])
