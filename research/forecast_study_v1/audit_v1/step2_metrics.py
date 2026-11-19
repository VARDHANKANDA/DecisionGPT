"""Step 2: independent recomputation of every primary metric for the six cells and comparison with the values printed in MANUSCRIPT.md (parsed from its tables,
not retyped) and with the study's own analysis.json. Writes METRIC_RECOMPUTATION.csv and work/step2.json."""
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import ind_core as ic  # noqa: E402

AUD = Path(__file__).parent
MS = (ic.STUDY / "manuscript" / "MANUSCRIPT.md").read_text(encoding="utf-8")
LABEL = {"M5 CA_1": "m5_ca1", "M5 TX_1": "m5_tx1", "Online Retail II": "or2_top100", "OR II": "or2_top100"}


def cell_key(label):
    m = re.match(r"(.+?),\s*H=(\d+)", label.strip())
    return f"fs1_{LABEL[m.group(1).strip()]}_H{m.group(2)}"


def decimals(s):
    s = s.strip().replace("%", "").replace("−", "-").replace("+", "")
    return len(s.split(".")[1]) if "." in s else 0


def num(s):
    return float(s.strip().replace("−", "-").replace("%", "").replace("+", "").replace("<", ""))


def table_rows(title_start):
    lines = MS.splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith(title_start))
    rows, k = [], i + 1
    while k < len(lines) and not lines[k].startswith("|"):
        k += 1
    while k < len(lines) and lines[k].startswith("|"):
        rows.append([c.strip() for c in lines[k].strip().strip("|").split("|")])
        k += 1
    return rows[2:]


rows_out, res = [], {}


def add(cell, quantity, manuscript, recomputed, tol, note=""):
    ok = (abs(manuscript - recomputed) <= tol) if manuscript is not None else None
    rows_out.append({"cell": cell, "quantity": quantity, "manuscript_value": "" if manuscript is None else manuscript, "independent_value": recomputed,
                     "abs_difference": "" if manuscript is None else abs(manuscript - recomputed), "rounding_tolerance": tol,
                     "verdict": "NOT IN MANUSCRIPT" if manuscript is None else ("PASS" if ok else "FAIL"), "note": note})


for cell in ic.CELLS:
    A = ic.stored(cell)
    sel = ic.jload(ic.RES / cell / "selection.json")
    cfg = ic.jload(ic.RES / cell / "config.json")
    ana = ic.jload(ic.RES / cell / "analysis.json")
    y, s, d, blk = A["y"].astype(float), A["series"].astype(int), A["day"].astype(int), A["block"].astype(int)
    starts = cfg["windows"]["test"]
    prim = "pred__" + sel["primary_learned_config"].replace(":", "__")
    refm, refa = "base__" + sel["reference_baseline_matched_information"], "base__" + sel["reference_baseline_any_information"]
    names = [k for k in A if k.startswith(("pred__", "base__"))]
    M = {}
    for k in names:
        p = A[k].astype(float)
        M[k] = {"wape": ic.wape(y, p), "agg": ic.agg_wape(y, p, d), "bias": ic.rel_bias(y, p), "mae": float(np.abs(p - y).mean()), "rmse": float(np.sqrt(((p - y) ** 2).mean())),
                "by_block": [ic.wape(y[blk == o], p[blk == o]) for o in starts], "item_week_wape": ic.week_agg_wape(y, p, s, d, starts[0])}
    imp = lambda a, b: (M[a]["wape"] - M[b]["wape"]) / M[a]["wape"]  # noqa: E731  (relative improvement of b over a, the plan's formula)
    res[cell] = {"primary": prim, "ref_matched": refm, "ref_any": refa, "n_rows": int(len(y)), "n_series": int(len(np.unique(s))), "n_days": int(len(np.unique(d))),
                 "n_blocks": len(starts), "n_week_blocks": int(((d.max() - starts[0]) // 7) + 1), "zero_share": float((y == 0).mean()),
                 "H1_improvement": imp(refm, prim), "H2_improvement": imp(refa, prim),
                 "blocks_won_H1": int(sum(M[prim]["by_block"][i] < M[refm]["by_block"][i] for i in range(len(starts)))),
                 "blocks_won_H2": int(sum(M[prim]["by_block"][i] < M[refa]["by_block"][i] for i in range(len(starts)))),
                 "loo_h1": [float((np.abs(A[refm][blk != o] - y[blk != o]).sum() - np.abs(A[prim][blk != o] - y[blk != o]).sum()) / np.abs(A[refm][blk != o] - y[blk != o]).sum()) for o in starts],
                 "metrics": M}
    # ---- agreement with the study's own analysis.json (unrounded)
    for nm, a, b in (("H1_improvement", res[cell]["H1_improvement"], ana["H1_vs_matched_reference"]["estimate"]), ("H2_improvement", res[cell]["H2_improvement"], ana["H2_vs_any_reference"]["estimate"])):
        add(cell, f"{nm} vs study analysis.json (unrounded)", b, a, 1e-9, "internal consistency")
    for k in names:
        add(cell, f"pooled WAPE {k} vs study analysis.json", ana["table"][k]["wape"], M[k]["wape"], 1e-9)
        add(cell, f"aggregate WAPE {k} vs study analysis.json", ana["table"][k]["aggregate_wape"], M[k]["agg"], 1e-9)

# ---- manuscript Table 1
for r in table_rows("**Table 1."):
    cell = cell_key(r[0])
    R = res[cell]
    wb, wm = num(r[1]), num(r[2])
    add(cell, "Table 1 WAPE baseline (matched reference)", wb, R["metrics"][R["ref_matched"]]["wape"], 0.5 * 10 ** -decimals(r[1]) + 1e-9)
    add(cell, "Table 1 WAPE model", wm, R["metrics"][R["primary"]]["wape"], 0.5 * 10 ** -decimals(r[2]) + 1e-9)
    mm = re.match(r"([+\-−]?[\d.]+)\s*%\s*\[([+\-−]?[\d.]+),\s*([+\-−]?[\d.]+)\]", r[3].replace("−", "-"))
    add(cell, "Table 1 relative improvement % (point)", num(mm.group(1)), 100 * R["H1_improvement"], 0.5 * 10 ** -decimals(mm.group(1)) + 1e-9)
    wins = int(r[4].split("/")[0])
    add(cell, "Table 1 blocks won", wins, R["blocks_won_H1"], 0)
    res[cell]["ms_table1_ci"] = [num(mm.group(2)), num(mm.group(3))]
    res[cell]["ms_table1_holm"] = r[5]
    res[cell]["ms_table1_verdict"] = r[6]

# ---- manuscript Table 2 (pairs "model / baseline")
cols = ["pooled WAPE", "store-day aggregate WAPE", "relative bias", "RMSE", "MAE"]
for r in table_rows("**Table 2."):
    cell = cell_key(r[0])
    R = res[cell]
    for j, (c, key) in enumerate(zip(cols, ("wape", "agg", "bias", "rmse", "mae")), start=1):
        mv, bv = [x.strip() for x in r[j].split("/")]
        tolm, tolb = 0.5 * 10 ** -decimals(mv) + 1e-9, 0.5 * 10 ** -decimals(bv) + 1e-9
        add(cell, f"Table 2 {c} model", num(mv), R["metrics"][R["primary"]][key], tolm)
        add(cell, f"Table 2 {c} baseline (matched reference)", num(bv), R["metrics"][R["ref_matched"]][key], tolb)

# ---- other manuscript statements checked numerically
add("all", "leave-one-origin-out: number of the 36 estimates that are negative (manuscript: all 36)", 36, sum(1 for c in ic.CELLS for v in res[c]["loo_h1"] if v < 0), 0)
mt = [res[c]["metrics"][res[c]["ref_matched"]]["bias"] for c in ic.CELLS]
add("all", "abstract: relative bias of matched reference, minimum (manuscript -0.58)", -0.58, min(mt), 0.005)
add("all", "abstract: relative bias of matched reference, maximum (manuscript -0.28)", -0.28, max(mt), 0.005)
m5 = [c for c in ic.CELLS if "m5" in c]
add("m5 cells", "abstract: model aggregate WAPE range low (0.08)", 0.08, min(res[c]["metrics"][res[c]["primary"]]["agg"] for c in m5), 0.005)
add("m5 cells", "abstract: model aggregate WAPE range high (0.11)", 0.11, max(res[c]["metrics"][res[c]["primary"]]["agg"] for c in m5), 0.005)
add("m5 cells", "abstract: baseline aggregate WAPE range low (0.29)", 0.29, min(res[c]["metrics"][res[c]["ref_matched"]]["agg"] for c in m5), 0.005)
add("m5 cells", "abstract: baseline aggregate WAPE range high (0.35)", 0.35, max(res[c]["metrics"][res[c]["ref_matched"]]["agg"] for c in m5), 0.005)
add("fs1_m5_ca1_H28", "discussion: seasonal-naive (matched) pooled WAPE (0.89)", 0.89, res["fs1_m5_ca1_H28"]["metrics"]["base__matched__seasonal_naive"]["wape"], 0.005)

with open(AUD / "METRIC_RECOMPUTATION.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_out[0]))
    w.writeheader()
    w.writerows(rows_out)
fails = [r for r in rows_out if r["verdict"] == "FAIL"]
print(len(rows_out), "comparisons;", len(fails), "FAIL")
for r in fails:
    print("FAIL", r["cell"], r["quantity"], r["manuscript_value"], r["independent_value"])
(AUD / "work" / "step2.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
