"""Supplementary descriptive summaries for the manuscript (added after the freeze; reads stored analysis/predictions only) -> results/summary_extra.json and results/SUMMARY_EXTRA.md.

    python -m research.forecast_study_v2.report_extra
"""
from __future__ import annotations

import json
import math

import numpy as np

from . import analysis as an
from .common import RESULTS, atomic_write_json

NAME = {"m5_ca1": "M5 CA_1", "m5_tx1": "M5 TX_1", "m5_wi1": "M5 WI_1", "or2": "Online Retail II"}


def design_effect(window, key, H, sel):
    A, _, res = an.load_cell(window, key, H)
    y, s, d = A["y"].astype(float), A["series"].astype(int), A["day"].astype(int)
    S = int(res["n_series"])
    day0 = res["blocks"]["test"][0]
    a = A["base__" + sel["baseline_item_day_matched"]].astype(float)
    b = A["pred__" + sel["model_item_day"]].astype(float)
    Na, W = an.cell_totals(s, d, y, a, S, day0)
    Nb, _ = an.cell_totals(s, d, y, b, S, day0)
    cg = an.cgm_t(Na, Nb)
    dl = (Na - Nb) / Na.sum()
    sd_iid = math.sqrt(dl.size * dl.var(ddof=1))
    return {"series": S, "weekly_blocks": int(W), "cells": int(dl.size), "se_two_way": cg["se"], "se_iid_cells": sd_iid, "design_effect_se": cg["se"] / sd_iid, "effective_independent_cells_approx": float((sd_iid / cg["se"]) ** 2 * dl.size)}


def main():
    out = {"replication": {}, "counts": {}, "design_effects_W2": {}, "segments_W2": {}, "bias_W2": {}}
    an_ = {w: json.loads((RESULTS / "analysis" / f"analysis_{w}.json").read_text(encoding="utf-8")) for w in ("W2", "W3", "W1")}
    for w, a in an_.items():
        out["counts"][w] = {h: {v: sum(1 for c in a["cells"].values() if c[h].get("verdict") == v) for v in ("SUPPORTED", "CONTRADICTED", "INCONCLUSIVE")} | {"not_applicable": sum(1 for c in a["cells"].values() if "primary" not in c[h])} for h in ("H1", "H1b", "H2", "H3")}
        out["counts"][w]["n_cells"] = len(a["cells"])
        out["counts"][w]["median_H1_improvement"] = float(np.median([c["H1"]["improvement"] for c in a["cells"].values()]))
        out["counts"][w]["range_H1_improvement"] = [float(min(c["H1"]["improvement"] for c in a["cells"].values())), float(max(c["H1"]["improvement"] for c in a["cells"].values()))]
        out["counts"][w]["median_H2_improvement"] = float(np.median([c["H2"]["improvement"] for c in a["cells"].values() if "improvement" in c["H2"]]))
        out["counts"][w]["median_H3_improvement"] = float(np.median([c["H3"]["improvement"] for c in a["cells"].values()]))
        out["counts"][w]["sign_H1_positive"] = sum(1 for c in a["cells"].values() if c["H1"]["improvement"] > 0)
    for c, v in an_["W2"]["cells"].items():
        r = {}
        for w in ("W3", "W1"):
            if c in an_[w]["cells"]:
                x = an_[w]["cells"][c]
                r[w] = {"H1_improvement": x["H1"]["improvement"], "H1_verdict": x["H1"]["verdict"], "H3_verdict": x["H3"]["verdict"], "sign_agrees_with_W2": bool((x["H1"]["improvement"] > 0) == (v["H1"]["improvement"] > 0))}
        r["W2"] = {"H1_improvement": v["H1"]["improvement"], "H1_verdict": v["H1"]["verdict"], "H3_verdict": v["H3"]["verdict"]}
        out["replication"][c] = r
        out["design_effects_W2"][c] = design_effect("W2", v["dataset"], v["H"], v["selection"])
        out["segments_W2"][c] = v["segments_exploratory"]
        L = v["ladder"]
        s = v["selection"]
        out["bias_W2"][c] = {"model_item_day": {k: L["pred__" + s["model_item_day"]][k] for k in ("rel_bias", "zero_forecast_share", "subset_day_wape", "item_day_wape")}, "best_matched_baseline": {k: L["base__" + s["baseline_item_day_matched"]][k] for k in ("rel_bias", "zero_forecast_share", "subset_day_wape", "item_day_wape")},
                             "reference_tweedie": {k: L["pred__" + s["reference_model"]][k] for k in ("rel_bias", "zero_forecast_share", "subset_day_wape", "item_day_wape")}}
    atomic_write_json(RESULTS / "summary_extra.json", out)
    md = ["# Supplementary summaries (report_extra.py)", "", "## Verdict counts by window", "", "| window | cells | H1 supp/contra/incon | H1b | H2 | H3 | median H1 improvement | H1 range | median H3 improvement |", "|---|---|---|---|---|---|---|---|---|"]
    for w, k in out["counts"].items():
        f = lambda h: "/".join(str(k[h][v]) for v in ("SUPPORTED", "CONTRADICTED", "INCONCLUSIVE")) + (f" (n/a {k[h]['not_applicable']})" if k[h]["not_applicable"] else "")  # noqa: E731
        md.append(f"| {w} | {k['n_cells']} | {f('H1')} | {f('H1b')} | {f('H2')} | {f('H3')} | {100 * k['median_H1_improvement']:+.1f}% | {100 * k['range_H1_improvement'][0]:+.1f}…{100 * k['range_H1_improvement'][1]:+.1f}% | {100 * k['median_H3_improvement']:+.1f}% |")
    md += ["", "## Design effects (W2, H1 comparison)", "", "| cell | series | weekly blocks | cells | design effect on the s.e. | effective independent cells (approx.) |", "|---|---|---|---|---|---|"]
    for c, d in out["design_effects_W2"].items():
        md.append(f"| {c} | {d['series']} | {d['weekly_blocks']} | {d['cells']} | {d['design_effect_se']:.1f} | {d['effective_independent_cells_approx']:.0f} |")
    (RESULTS / "SUMMARY_EXTRA.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(out["counts"], indent=1))


if __name__ == "__main__":
    main()
