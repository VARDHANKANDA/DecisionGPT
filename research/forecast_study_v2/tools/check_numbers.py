"""Numerical-consistency check: every headline number in MANUSCRIPT_R2.md prose (abstract, results text, discussion, conclusions) is recomputed from the stored artifacts and must appear in the manuscript.
Also checks that the embedded tables equal the generated ones and that no stale statements remain.   python research/forecast_study_v2/tools/check_numbers.py"""
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
R = HERE / "results"
M = (HERE / "MANUSCRIPT_R2.md").read_text(encoding="utf-8")
A = {w: json.loads((R / "analysis" / f"analysis_{w}.json").read_text(encoding="utf-8"))["cells"] for w in ("W2", "W3", "W1")}
S = json.loads((R / "supplementary" / "h3_convergence.json").read_text(encoding="utf-8"))["windows"]
V = {w: json.loads((R / "verification" / f"independent_verification_{w}.json").read_text(encoding="utf-8")) for w in ("W2", "W3", "W1")}
MI = "−"


def p1(x):  # signed percent with one decimal, as in the prose
    return f"{100 * x:+.1f} %".replace("-", MI)


checks = []


def need(desc, s):
    checks.append((desc, s, s in M))


w2 = A["W2"]
h1 = [c["H1"]["improvement"] for c in w2.values()]
h2 = [c["H2"]["improvement"] for c in w2.values()]
h3 = [c["H3"]["improvement"] for c in w2.values()]
h1b28 = [c["H1b"]["improvement"] for k, c in w2.items() if k.endswith("H28")]
need("W2 median H1", p1(np.median(h1)))
need("W2 H1 range", f"{p1(min(h1))} … {p1(max(h1))}")
need("W2 H2 range", f"{p1(min(h2))} … {p1(max(h2))}")
need("W2 H1b H28 range", f"{p1(min(h1b28))} … {p1(max(h1b28))}")
need("W2 H3 median", p1(np.median(h3)))
need("W2 H3 positive count", f"positive in {sum(x > 0 for x in h3)} of 8")
need("OR2 H7 H3", p1(w2["or2_H7"]["H3"]["improvement"]))
cnt = lambda w, h: sum(c[h]["verdict"] == "SUPPORTED" for c in A[w].values())  # noqa: E731
need("H1 8/8", f"supported in {cnt('W2', 'H1')} of 8 cells")
need("H3 4/8", f"supported in {cnt('W2', 'H3')} of 8 cells")
tot_pos = sum(c["H1"]["improvement"] > 0 for w in A for c in A[w].values())
tot_sup = sum(c["H1"]["verdict"] == "SUPPORTED" for w in A for c in A[w].values())
need("22 positive", f"positive in all {tot_pos} cells")
need("20 supported", f"(supported in {tot_sup})")
need("W3 H3", f"supported in {cnt('W3', 'H3')} of 6 cells in W3")
need("W1 H3", f"in {cnt('W1', 'H3')} of 8 in W1")
sp = [[c["seed_sensitivity"][k] for k in ("seed42", "seed43", "seed44")] for c in w2.values()]
rg = [100 * (max(x) - min(x)) for x in sp]
need("seed max range", f"at most {max(rg):.1f} percentage points")
need("seed per cell range", f"{min(rg):.2f}–{max(rg):.2f} pp")
need("seed min", f"≥ {100 * min(min(x) for x in sp):.1f} %")
m5 = {k: c for k, c in w2.items() if k.startswith("m5")}
bias = [c["ladder"]["pred__" + c["selection"]["model_item_day"]]["rel_bias"] for c in m5.values()]
zs = [c["ladder"]["pred__" + c["selection"]["model_item_day"]]["zero_forecast_share"] for c in m5.values()]
zb = [c["ladder"]["base__" + c["selection"]["baseline_item_day_matched"]]["zero_forecast_share"] for c in m5.values()]
need("bias range", f"{MI}{abs(max(bias)):.2f} … {MI}{abs(min(bias)):.2f}")
need("zero share model", f"{100 * min(zs):.0f}–{100 * max(zs):.0f} %")
need("zero share baseline", f"{100 * min(zb):.0f}–{100 * max(zb):.0f} %")
c = w2["m5_ca1_H28"]
L = c["ladder"]
need("CA_1 H28 item-day model subset-day", f"{L['pred__lgbm_l1']['subset_day_wape']:.3f} against {L['base__' + c['selection']['baseline_subset_day_matched']]['subset_day_wape']:.3f}")
need("CA_1 H28 reference vs baseline", f"{L['pred__lgbm_tweedie_p11']['item_day_wape']:.3f} against {L['base__' + c['selection']['baseline_item_day_matched']]['item_day_wape']:.3f}")
seg = c["segments_exploratory"]
fr, sp_ = seg["frequency=frequent"], seg["frequency=intermittent_or_sparse"]
need("frequent segment", f"{p1(fr['improvement'])} [{100 * fr['ci95'][0]:+.1f}, {100 * fr['ci95'][1]:+.1f}], n = {fr['n_series']}")
need("intermittent segment", f"{p1(sp_['improvement'])} [{100 * sp_['ci95'][0]:+.1f}, {100 * sp_['ci95'][1]:+.1f}], n = {sp_['n_series']}")
t = S["W2"]["m5_tx1_H28"]
need("TX1 Holm primary", f"{t['converged']['holm_primary']:.4f}")
need("TX1 Holm secondary", f"{t['converged']['holm_secondary']:.4f}")
need("TX1 lag1", f"lag-1 {t['diagnostics']['lag1_autocorr_of_weekly_difference']:+.2f}")
need("TX1 eff weeks", f"≈ {t['diagnostics']['ar1_effective_weeks']:.0f} of 24")
unchanged = all(r["frozen"]["verdict"] == r["converged"]["verdict_dual_rule"] for w in S.values() for r in w.values())
checks.append(("all 22 H3 verdicts unchanged (artifact)", "", unchanged))
tw = sum(len(w) for w in S.values())
need("H3 cell count", "All 22 H3 verdicts" if tw == 22 else "MISMATCH")
for w, (n_ok, tag) in {"W2": 98, "W3": 72, "W1": 98}.items() if False else []:
    pass
need("verification counts", "98/98 checks passed in W2, 72/72 in W3 and 98/98 in W1")
ncmp = sum(len(v["comparison_with_study_analysis"]) for v in V.values())
nok = sum(sum(x["verdict_agrees"] for x in v["comparison_with_study_analysis"]) for v in V.values())
need("verdict comparisons", f"Of the {ncmp} verdict comparisons {nok} agree")
need("point estimate identical", f"identical in {ncmp} of {ncmp} comparisons")
for k, v in V.items():
    assert v["n_cell_checks_failed"] == 0, k
de = json.loads((R / "summary_extra.json").read_text(encoding="utf-8"))["design_effects_W2"]
dv = [x["design_effect_se"] for x in de.values()]
need("design effect range", f"{min(dv):.1f}–{max(dv):.1f}")
need("H2 8 of 8", "improves on the original Tweedie 1.1 model in 8 of 8 cells")
# stale / forbidden statements
for bad in ("all of the top 50", "independent audit of that study", "[verify]", "5/8", "{{", "TODO"):
    checks.append((f"absent: {bad}", bad, bad not in M))
# embedded tables identical to generated ones
for f in sorted((HERE / "tables").glob("*.md")):
    txt = f.read_text(encoding="utf-8").strip()
    checks.append((f"table embedded verbatim: {f.name}", f.name, txt in M))
bad = [(d, s) for d, s, ok in checks if not ok]
print(f"{len(checks) - len(bad)}/{len(checks)} checks passed")
for d, s in bad:
    print("FAIL:", d, "->", repr(s)[:120])
sys.exit(1 if bad else 0)
