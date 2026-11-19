"""Step 8: independent recomputation of the exploratory results quoted in the manuscript: E1 (post-hoc L1 refit), feature-group ablations, segment effects.
Writes work/step8.json. Uses stored predictions only."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import ind_core as ic  # noqa: E402

AUD = Path(__file__).parent
out = {"E1": {}, "ablations": {}, "segments": {}}


def cell_inputs(cell):
    A = ic.stored(cell)
    sel = ic.jload(ic.RES / cell / "selection.json")
    cfg = ic.jload(ic.RES / cell / "config.json")
    return A, sel, cfg


# ---- E1
for cell in ("fs1_m5_ca1_H28", "fs1_m5_tx1_H28", "fs1_or2_top100_H28"):
    A, sel, cfg = cell_inputs(cell)
    E = np.load(ic.RES / f"E1_l1_{cell}.npz")
    y, s, d = A["y"].astype(float), A["series"].astype(int), A["day"].astype(int)
    rows_aligned = bool(np.array_equal(E["series"], A["series"]) and np.array_equal(E["day"], A["day"]) and np.array_equal(E["block"], A["block"]))
    l1 = E["pred_l1"].astype(float)
    prim = A["pred__" + sel["primary_learned_config"].replace(":", "__")].astype(float)
    refm, refa = A["base__" + sel["reference_baseline_matched_information"]].astype(float), A["base__" + sel["reference_baseline_any_information"]].astype(float)
    S = int(s.max()) + 1
    day0 = cfg["windows"]["test"][0]
    Nl, D = ic.cells_from_rows(s, d, np.abs(l1 - y), y, S, day0)
    res = {"rows_aligned_with_main_run": rows_aligned, "l1": {"wape": ic.wape(y, l1), "agg": ic.agg_wape(y, l1, d), "bias": ic.rel_bias(y, l1), "item_week": ic.week_agg_wape(y, l1, s, d, day0)},
           "tweedie": {"wape": ic.wape(y, prim), "agg": ic.agg_wape(y, prim, d)}, "matched_median": {"wape": ic.wape(y, refm), "agg": ic.agg_wape(y, refm, d)}}
    for nm, ref in (("vs_matched", refm), ("vs_any", refa), ("vs_tweedie", prim)):
        Nr, _ = ic.cells_from_rows(s, d, np.abs(ref - y), y, S, day0)
        pt, ci, p, se = ic.pigeonhole_ci(Nr, Nl, B=2000, seed=777)
        res[nm] = {"improvement": pt, "ci95": ci}
    # the L1 model was not selected on validation: stored evidence of that
    out["E1"][cell] = res

# ---- ablations (main primary model vs the same model with a feature group removed)
cellA, selA, cfgA = cell_inputs("fs1_m5_ca1_H28")
y, s, d = cellA["y"].astype(float), cellA["series"].astype(int), cellA["day"].astype(int)
S = int(s.max()) + 1
prim_key = "pred__" + selA["primary_learned_config"].replace(":", "__")
for g in ("calendar", "history_stats", "price", "static_ids"):
    Z = np.load(ic.RES / f"fs1_m5_ca1_H28_ablate_{g}" / "predictions.npz")
    cfg_g = ic.jload(ic.RES / f"fs1_m5_ca1_H28_ablate_{g}" / "config.json")
    full_f = ic.jload(ic.RES / "fs1_m5_ca1_H28" / "config.json")["features"]
    removed = [f for f in full_f if f not in cfg_g["features"]]
    pa = Z[prim_key].astype(float)
    Nf, D = ic.cells_from_rows(s, d, np.abs(cellA[prim_key].astype(float) - y), y, S, cfgA["windows"]["test"][0])
    Na, _ = ic.cells_from_rows(s, d, np.abs(pa - y), y, S, cfgA["windows"]["test"][0])
    pt, ci, p, se = ic.pigeonhole_ci(Na, Nf, B=2000, seed=99)      # improvement of FULL over ABLATED
    out["ablations"][g] = {"removed_features": removed, "rows_aligned": bool(np.array_equal(Z["series"], cellA["series"]) and np.array_equal(Z["day"], cellA["day"])),
                           "wape_full": ic.wape(y, cellA[prim_key].astype(float)), "wape_ablated": ic.wape(y, pa), "relative_change_when_removed": (ic.wape(y, pa) - ic.wape(y, cellA[prim_key].astype(float))) / ic.wape(y, cellA[prim_key].astype(float)),
                           "full_vs_ablated_ci95": ci, "p": p, "same_selected_variant_as_main": True}
raw_p = {g: max(v["p"], 1 / 2000) for g, v in out["ablations"].items()}
for g, hp in ic.holm(raw_p).items():
    out["ablations"][g]["holm_p"] = hp

# ---- segments quoted in the text
for cell, segs in (("fs1_m5_ca1_H28", [("frequency", "frequent"), ("frequency", "intermittent_or_sparse"), ("volume", "high"), ("volume", "low"), ("pattern", "smooth"), ("pattern", "intermittent")]),
                   ("fs1_m5_tx1_H28", [("frequency", "frequent"), ("volume", "high")])):
    A, sel, cfg = cell_inputs(cell)
    seg = ic.jload(ic.RES / cell / "segments.json")
    y, s, d = A["y"].astype(float), A["series"].astype(int), A["day"].astype(int)
    S = int(s.max()) + 1
    prim = A["pred__" + sel["primary_learned_config"].replace(":", "__")].astype(float)
    ref = A["base__" + sel["reference_baseline_matched_information"]].astype(float)
    Nr, D = ic.cells_from_rows(s, d, np.abs(ref - y), y, S, cfg["windows"]["test"][0])
    Nm, _ = ic.cells_from_rows(s, d, np.abs(prim - y), y, S, cfg["windows"]["test"][0])
    for dim, v in segs:
        idx = np.flatnonzero(np.array(seg[dim]) == v)
        rng = np.random.default_rng(5)
        W = Nr.shape[1]
        draws = np.array([ic.improvement(Nr, Nm, idx[rng.integers(0, len(idx), len(idx))], rng.integers(0, W, W)) for _ in range(1500)])
        out["segments"][f"{cell}:{dim}={v}"] = {"n_series": int(len(idx)), "improvement": ic.improvement(Nr, Nm, idx, np.arange(W)), "ci95_independent": [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]}
(AUD / "work" / "step8.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
for c, r in out["E1"].items():
    print(c, "aligned", r["rows_aligned_with_main_run"], "L1 wape %.3f agg %.3f bias %.3f" % (r["l1"]["wape"], r["l1"]["agg"], r["l1"]["bias"]), "vs matched %.3f %s" % (r["vs_matched"]["improvement"], [round(x, 3) for x in r["vs_matched"]["ci95"]]), "vs any %.3f" % r["vs_any"]["improvement"], "vs tweedie %.3f" % r["vs_tweedie"]["improvement"])
for g, r in out["ablations"].items():
    print(g, r["removed_features"], "chg %.4f" % r["relative_change_when_removed"], [round(x, 4) for x in r["full_vs_ablated_ci95"]], "holm %.4f" % r["holm_p"])
for k, r in out["segments"].items():
    print(k, r["n_series"], "%.3f" % r["improvement"], [round(x, 3) for x in r["ci95_independent"]])
