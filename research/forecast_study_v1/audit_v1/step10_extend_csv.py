"""Step 10: extend METRIC_RECOMPUTATION.csv with the manuscript's numeric claims outside Tables 1-2 (sections 11-15), compared with the independent recomputations in work/step3,5,6,8.
Manuscript values are typed from MANUSCRIPT.md (line numbers in the note column); tolerances reflect the rounding printed in the manuscript (+ Monte-Carlo error for bootstrap endpoints)."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
AUD = Path(__file__).parent
W = AUD / "work"
s3, s5, s6, s8 = (json.load(open(W / f"step{i}.json", encoding="utf-8")) for i in (3, 5, 6, 8))
rows = []


def add(cell, q, ms, ind, tol, note):
    ok = abs(ms - ind) <= tol
    rows.append({"cell": cell, "quantity": q, "manuscript_value": ms, "independent_value": ind, "abs_difference": abs(ms - ind), "rounding_tolerance": tol, "verdict": "PASS" if ok else "FAIL", "note": note})


# ---- section 11 (line 112): crossed vs series-only
CELLS = list(s3["cells"])
ratios = [(s3["cells"][c]["H1"]["pigeonhole_independent"]["ci95"][1] - s3["cells"][c]["H1"]["pigeonhole_independent"]["ci95"][0]) / (s3["cells"][c]["H1"]["series_only_bootstrap"]["ci95"][1] - s3["cells"][c]["H1"]["series_only_bootstrap"]["ci95"][0]) for c in CELLS]
add("all", "sec 11: min crossed/series-only CI-width ratio (manuscript 1.21)", 1.21, min(ratios), 0.08, "line 112; Monte-Carlo error of two bootstraps")
add("all", "sec 11: max crossed/series-only CI-width ratio (manuscript 1.47)", 1.47, max(ratios), 0.10, "line 112")
so = s3["cells"]["fs1_m5_ca1_H28"]["H1"]["series_only_bootstrap"]["ci95"]
add("fs1_m5_ca1_H28", "sec 11: series-only CI lower (-5.1 %)", -5.1, 100 * so[0], 0.2, "line 112")
add("fs1_m5_ca1_H28", "sec 11: series-only CI upper (-0.2 %)", -0.2, 100 * so[1], 0.2, "line 112")
# ---- section 12 (lines 116-118): segments and ablations
for key, ms in {"fs1_m5_ca1_H28:frequency=frequent": (6.3, 3.3, 9.5), "fs1_m5_ca1_H28:frequency=intermittent_or_sparse": (-8.0, -12.0, -3.8), "fs1_m5_ca1_H28:volume=high": (4.8, 0.8, 7.8),
                "fs1_m5_ca1_H28:volume=low": (-35.0, -44.9, -25.8), "fs1_m5_ca1_H28:pattern=smooth": (7.9, None, None), "fs1_m5_tx1_H28:frequency=frequent": (2.1, -1.7, 6.0), "fs1_m5_tx1_H28:volume=high": (-2.4, -5.7, 0.7)}.items():
    r = s8["segments"][key]
    add(key, "sec 12: segment relative improvement %", ms[0], 100 * r["improvement"], 0.05, "line 116; point estimate")
    if ms[1] is not None:
        add(key, "sec 12: segment CI lower %", ms[1], 100 * r["ci95_independent"][0], 0.5, "line 116; bootstrap MC tolerance 0.5 pp")
        add(key, "sec 12: segment CI upper %", ms[2], 100 * r["ci95_independent"][1], 0.5, "line 116")
for g, (chg, lo, hi) in {"calendar": (2.6, 1.1, 4.3), "history_stats": (3.5, 2.3, 4.5), "price": (0.8, -0.1, 1.8), "static_ids": (0.3, -0.4, 0.8)}.items():
    r = s8["ablations"][g]
    add("fs1_m5_ca1_H28", f"sec 12: ablation {g}: WAPE change when removed %", chg, 100 * r["relative_change_when_removed"], 0.06, "line 118")
    add("fs1_m5_ca1_H28", f"sec 12: ablation {g}: CI lower %", lo, 100 * r["full_vs_ablated_ci95"][0], 0.4, "line 118")
    add("fs1_m5_ca1_H28", f"sec 12: ablation {g}: CI upper %", hi, 100 * r["full_vs_ablated_ci95"][1], 0.4, "line 118")
add("fs1_m5_ca1_H28", "sec 12: ablation price Holm p (0.19)", 0.19, s8["ablations"]["price"]["holm_p"], 0.03, "line 118")
add("fs1_m5_ca1_H28", "sec 12: ablation static_ids Holm p (0.38)", 0.38, s8["ablations"]["static_ids"]["holm_p"], 0.03, "line 118")
# ---- section 13 (line 124-128): E1 table
E1 = {"fs1_m5_ca1_H28": (0.699, 0.370, -0.366, 3.4, -0.5, 5.9), "fs1_m5_tx1_H28": (0.743, 0.450, -0.445, 0.8, -2.4, 10.9), "fs1_or2_top100_H28": (0.787, 0.523, -0.491, 9.9, 9.9, 13.1)}
for c, (w, a, b, vm, va, vt) in E1.items():
    r = s8["E1"][c]
    add(c, "sec 13 E1: L1 pooled WAPE", w, r["l1"]["wape"], 0.0005 + 1e-9, "lines 124-128 (post hoc)")
    add(c, "sec 13 E1: L1 aggregate WAPE", a, r["l1"]["agg"], 0.0005 + 1e-9, "")
    add(c, "sec 13 E1: L1 bias", b, r["l1"]["bias"], 0.0005 + 1e-9, "")
    add(c, "sec 13 E1: L1 vs matched baseline %", vm, 100 * r["vs_matched"]["improvement"], 0.06, "")
    add(c, "sec 13 E1: L1 vs best any-info baseline %", va, 100 * r["vs_any"]["improvement"], 0.06, "")
    add(c, "sec 13 E1: L1 vs Tweedie model %", vt, 100 * r["vs_tweedie"]["improvement"], 0.06, "")
# ---- section 14 (line 134): conformal
MC = {"fs1_m5_ca1_H28": 0.802, "fs1_m5_ca1_H7": 0.802, "fs1_m5_tx1_H28": 0.794, "fs1_m5_tx1_H7": 0.793, "fs1_or2_top100_H28": 0.807, "fs1_or2_top100_H7": 0.810}
for c, v in MC.items():
    add(c, "sec 14: model overall 80% interval coverage", v, s5[c]["model"]["coverage_overall"], 0.0005 + 1e-9, "line 134")
allblk = [x for c in MC for x in s5[c]["model"]["coverage_by_block"].values()]
add("all", "sec 14: min per-origin model coverage (0.775)", 0.775, min(allblk), 0.0005 + 1e-9, "line 134")
add("all", "sec 14: max per-origin model coverage (0.824)", 0.824, max(allblk), 0.0005 + 1e-9, "line 134")
fr = [s5[c]["model"]["by_frequency_segment"]["frequent"] for c in MC]
add("all", "sec 14: min frequent-series coverage (0.66)", 0.66, min(fr), 0.005, "line 134")
add("all", "sec 14: max frequent-series coverage (0.78)", 0.78, max(fr), 0.005, "line 134")
it = [s5[c]["model"]["by_frequency_segment"]["intermittent_or_sparse"] for c in MC]
add("all", "sec 14: min intermittent-series coverage (0.81)", 0.81, min(it), 0.005, "line 134")
add("all", "sec 14: max intermittent-series coverage (0.82)", 0.82, max(it), 0.005, "line 134")
add("fs1_m5_ca1_H28", "sec 14: model mean interval width (2.50)", 2.50, s5["fs1_m5_ca1_H28"]["model"]["mean_width"], 0.005, "line 134")
add("fs1_m5_ca1_H28", "sec 14: matched-baseline mean interval width (2.29)", 2.29, s5["fs1_m5_ca1_H28"]["ref_matched"]["mean_width"], 0.005, "line 134")
add("fs1_or2_top100_H28", "sec 14: model mean interval width (53.5)", 53.5, s5["fs1_or2_top100_H28"]["model"]["mean_width"], 0.05, "line 134")
add("fs1_or2_top100_H28", "sec 14: matched-baseline mean interval width (35.6)", 35.6, s5["fs1_or2_top100_H28"]["ref_matched"]["mean_width"], 0.05, "line 134")
# ---- section 15 (lines 138-157): inactivity
A, B = s6["origins"]["A"], s6["origins"]["B"]
for o, r, v in (("A", A, (0.804, 0.881, 0.776, 0.871)), ("B", B, (0.799, 0.818, 0.762, 0.798))):
    add(f"S2 origin {o}", "sec 15: model ROC-AUC", v[0], r["roc_auc"]["model"], 0.0005 + 1e-9, "Table 3")
    add(f"S2 origin {o}", "sec 15: model PR-AUC", v[1], r["pr_auc"]["model"], 0.0005 + 1e-9, "Table 3")
    add(f"S2 origin {o}", "sec 15: recency ROC-AUC", v[2], r["roc_auc"]["baseline"], 0.0005 + 1e-9, "Table 3")
    add(f"S2 origin {o}", "sec 15: recency PR-AUC", v[3], r["pr_auc"]["baseline"], 0.0005 + 1e-9, "Table 3")
for o, r, ece_raw, ece_pl in (("A", A, 0.083, 0.038), ("B", B, 0.092, 0.126)):
    add(f"S2 origin {o}", "sec 15: ECE10 raw", ece_raw, r["calibration"]["ece10_test_raw"], 0.0005 + 1e-9, "Table 3")
    add(f"S2 origin {o}", "sec 15: ECE10 Platt", ece_pl, r["calibration"]["ece10_test_platt"], 0.0005 + 1e-9, "Table 3 / line 153")
for o, r, d_auc, lo, hi, d_pr, plo, phi in (("A", A, 0.028, 0.017, 0.039, 0.010, 0.002, 0.018), ("B", B, 0.037, 0.029, 0.044, 0.020, 0.011, 0.029)):
    pb = r["paired_bootstrap_independent"]
    add(f"S2 origin {o}", "sec 15: ROC-AUC difference", d_auc, pb["roc_auc"]["difference"], 0.0005 + 1e-9, "line 151")
    add(f"S2 origin {o}", "sec 15: ROC-AUC CI lower", lo, pb["roc_auc"]["ci95"][0], 0.0015, "line 151; MC")
    add(f"S2 origin {o}", "sec 15: ROC-AUC CI upper", hi, pb["roc_auc"]["ci95"][1], 0.0015, "line 151")
    add(f"S2 origin {o}", "sec 15: PR-AUC difference", d_pr, pb["pr_auc"]["difference"], 0.0005 + 1e-9, "line 151")
    add(f"S2 origin {o}", "sec 15: PR-AUC CI lower", plo, pb["pr_auc"]["ci95"][0], 0.0015, "line 151")
    add(f"S2 origin {o}", "sec 15: PR-AUC CI upper", phi, pb["pr_auc"]["ci95"][1], 0.0015, "line 151")
for o, r, acc, rec, pre, maj in (("A", A, 0.762, 0.955, 0.757, 0.677), ("B", B, 0.691, 0.966, 0.653, 0.565)):
    t = r["threshold"]
    add(f"S2 origin {o}", "sec 15: accuracy at the one validation threshold", acc, t["accuracy"], 0.0005 + 1e-9, "line 155")
    add(f"S2 origin {o}", "sec 15: recall", rec, t["recall"], 0.0005 + 1e-9, "line 155")
    add(f"S2 origin {o}", "sec 15: precision", pre, t["precision"], 0.0005 + 1e-9, "line 155")
    add(f"S2 origin {o}", "sec 15: majority-class accuracy", maj, t["majority_accuracy"], 0.0005 + 1e-9, "line 155")
add("S2 holm", "sec 15: Holm p, origin A PR-AUC (0.021)", 0.021, s6["holm_independent"]["A:pr_auc"], 0.01, "line 151; bootstrap resolution 0.0005 x multiplier")

# merge
p = AUD / "METRIC_RECOMPUTATION.csv"
old = list(csv.DictReader(open(p, encoding="utf-8")))
old = [r for r in old if not r.get("quantity", "").startswith(("sec 11", "sec 12", "sec 13", "sec 14", "sec 15"))]
with open(p, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(old + rows)
print(len(old), "base rows +", len(rows), "extension rows;", sum(r["verdict"] == "FAIL" for r in rows), "extension FAIL")
for r in rows:
    if r["verdict"] == "FAIL":
        print("FAIL", r["cell"], r["quantity"], r["manuscript_value"], round(r["independent_value"], 4), "tol", r["rounding_tolerance"])
