"""Compare the independent re-computation (results/decision_quality.json) with the STORED locked statistical results (read-only).

    python research/decisiongpt_architecture_v1/analysis/replication_check.py

Fields compared per stored contrast: mean difference (abs tol 1e-5), Wilcoxon p (relative tol 1e-3 -- the stored p uses scipy mode 'approx', ours 'auto'),
win/tie/loss counts (both orientations are tested; an orientation reversal is reported, not hidden), Holm-adjusted p where stored.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RES = REPO / "research" / "decisiongpt_architecture_v1" / "results"


def main():
    dq = json.loads((RES / "decision_quality.json").read_text(encoding="utf-8"))
    out = {"checks": [], "notes": []}
    # R1
    r1 = json.loads((REPO / "experiments/r1/statistical_results.json").read_text(encoding="utf-8"))["primary_and_confirmatory_contrasts"]
    for k, v in r1.items():
        mine = dq["studies"]["r1"]["contrasts"][k]
        wtl = v["wins_ties_losses"]
        out["checks"].append({"study": "r1", "contrast": k, "stored_mean": v["mean_difference"], "mine_mean": mine["mean_diff_a_minus_b"], "mean_ok": abs(v["mean_difference"] - mine["mean_diff_a_minus_b"]) < 1e-5,
                              "stored_p": v["wilcoxon"]["p_value"], "mine_p": mine["wilcoxon_p"], "p_ok": abs(v["wilcoxon"]["p_value"] - mine["wilcoxon_p"]) <= 1e-3 * max(v["wilcoxon"]["p_value"], 1e-300) or abs(v["wilcoxon"]["p_value"] - mine["wilcoxon_p"]) < 1e-12,
                              "stored_wtl": wtl, "mine_wtl": [mine["a_better_(lower)"], mine["ties"], mine["a_worse_(higher)"]], "wtl_same_orientation": wtl == [mine["a_better_(lower)"], mine["ties"], mine["a_worse_(higher)"]],
                              "stored_rank_biserial": v["matched_pairs_rank_biserial"], "mine_rank_biserial_kerby_nonzero_pairs": mine["rank_biserial_a_vs_b"]})
    # upgraded v1
    u = json.loads((REPO / "experiments/upgraded_controlled_v1/statistical_results.json").read_text(encoding="utf-8"))
    hol = u["holm_family"]["results"]
    for k, v in u["primary_contrasts"].items():
        mine = dq["studies"]["upgraded_v1"]["contrasts"][k]
        wtl = v["wins_ties_losses"]
        m = [mine["a_better_(lower)"], mine["ties"], mine["a_worse_(higher)"]]
        out["checks"].append({"study": "upgraded_v1", "contrast": k, "stored_mean": v["mean_difference"], "mine_mean": mine["mean_diff_a_minus_b"], "mean_ok": abs(v["mean_difference"] - mine["mean_diff_a_minus_b"]) < 1e-5,
                              "stored_p": v["wilcoxon"]["p_value"], "mine_p": mine["wilcoxon_p"], "p_ok": abs(v["wilcoxon"]["p_value"] - mine["wilcoxon_p"]) <= 1e-3 * v["wilcoxon"]["p_value"],
                              "stored_holm": hol[k]["p_holm"], "mine_holm": mine.get("holm_p_over_primary_four"), "holm_ok": abs(hol[k]["p_holm"] - (mine.get("holm_p_over_primary_four") or -1)) < 1e-6,
                              "stored_wtl": wtl, "mine_wtl": m, "wtl_same_orientation": wtl == m, "wtl_reversed_orientation": wtl == m[::-1],
                              "stored_rank_biserial": v["rank_biserial"], "mine_rank_biserial_kerby_nonzero_pairs": mine["rank_biserial_a_vs_b"]})
    bad = [c for c in out["checks"] if not (c["mean_ok"] and c["p_ok"])]
    out["summary"] = {"n_checked": len(out["checks"]), "mean_and_p_all_match": not bad, "mismatches": [(c["study"], c["contrast"]) for c in bad],
                      "wtl_orientation_reversed_in_stored_file": [(c["study"], c["contrast"]) for c in out["checks"] if not c["wtl_same_orientation"] and c.get("wtl_reversed_orientation")]}
    out["notes"] = ["Rank-biserial: the stored files use a different sign/definition than the standard matched-pairs formula (Kerby 2014) applied here to the non-zero paired differences; the effect size is therefore reported with its definition and not compared numerically.",
                    "upgraded_v1: the stored `wins_ties_losses` is listed as [count(first higher), ties, count(first lower)] although its label says wins first; the direction of every effect is fixed by the signed mean difference and by our recount from raw records, which agree with each other."]
    (RES / "replication_check.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out["summary"], indent=1))
    for c in out["checks"]:
        print(c["study"], c["contrast"], "mean_ok", c["mean_ok"], "p_ok", c["p_ok"], "wtl same", c["wtl_same_orientation"], "reversed", c.get("wtl_reversed_orientation"))


if __name__ == "__main__":
    main()
