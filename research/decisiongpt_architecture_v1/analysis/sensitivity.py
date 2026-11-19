"""Post-hoc sensitivity analyses of the R1 locked contrasts (read-only; labelled post-hoc in the paper).

    python research/decisiongpt_architecture_v1/analysis/sensitivity.py

S1: drop the instances in which the R1 elasticity estimator fell back to the generator's declared parameters (factors.r1_dt_method == 'fallback_generator'); the stored run has 69 of 4,080.
S2: first-seed-only (the seed used by the cost measurement): contrasts on the 408 scenarios using only the first locked seed.
S3: leave-one-family-out D-B (is the pooled result driven by a single family?).
S4: near-optimal share at three thresholds (descriptive).
Writes results/sensitivity.json.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "research" / "decisiongpt_architecture_v1" / "results" / "sensitivity.json"
BOOT_B, SEED = 10000, 20261025


def contrast(per, a, b, rng, keep=None):
    sids = [s for s in sorted(per) if (keep is None or s in keep) and per[s].get(a) and per[s].get(b)]
    d = np.array([np.mean(per[s][a]) - np.mean(per[s][b]) for s in sids])
    bs = d[rng.integers(0, len(d), size=(BOOT_B, len(d)))].mean(axis=1)
    nz = d[d != 0]
    p = float(stats.wilcoxon(nz).pvalue) if len(nz) else 1.0
    return {"n_scenarios": len(d), "mean_diff": float(d.mean()), "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], "wilcoxon_p": p,
            "first_lower/ties/first_higher": [int((d < 0).sum()), int((d == 0).sum()), int((d > 0).sum())]}


def main():
    rng = np.random.default_rng(SEED)
    d = json.loads((REPO / "experiments/r1/results.json").read_text(encoding="utf-8"))
    seeds = d["seeds"]
    full, nofb, first = defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(list))
    fam = {}
    fb = Counter()
    for rec in d["records"]:
        r = rec["result"]
        sid = r["scenario_id"]
        fam[sid] = r["family_id"]
        is_fb = r["factors"].get("r1_dt_method") != "ols"
        fb[(r["family_id"], is_fb)] += 1
        for k, c in r["conditions"].items():
            x = c["primary_regret"]
            full[sid][k].append(x)
            if not is_fb:
                nofb[sid][k].append(x)
            if rec["seed"] == seeds[0]:
                first[sid][k].append(x)
    out = {"fallback_instances": sum(v for (f, i), v in fb.items() if i), "n_instances": len(d["records"]),
           "fallback_by_family": {f: v for (f, i), v in sorted(fb.items()) if i},
           "scenarios_with_any_fallback": len({s for s in full if len(nofb.get(s, {}).get("D", [])) < len(full[s]["D"])}),
           "S1_excluding_fallback_instances": {}, "S2_first_seed_only": {}, "S3_leave_one_family_out_D_minus_B": {}, "S4_near_optimal_share": {}}
    for a, b in (("B", "A"), ("C", "B"), ("D", "C"), ("D", "B"), ("D", "A")):
        out["S1_excluding_fallback_instances"][f"{a}_vs_{b}"] = contrast(nofb, a, b, rng)
        out["S2_first_seed_only"][f"{a}_vs_{b}"] = contrast(first, a, b, rng)
    for f in sorted(set(fam.values())):
        keep = {s for s in full if fam[s] != f}
        out["S3_leave_one_family_out_D_minus_B"][f] = contrast(full, "D", "B", rng, keep)
    for thr in (0.05, 0.10, 0.20):
        out["S4_near_optimal_share"][str(thr)] = {k: float(np.mean([x <= thr for s in full for x in full[s][k]])) for k in ("A", "B", "C", "D")}
    s3 = out["S3_leave_one_family_out_D_minus_B"]
    out["S3_summary"] = {"all_positive": all(v["mean_diff"] > 0 for v in s3.values()), "min": min(v["mean_diff"] for v in s3.values()), "max": max(v["mean_diff"] for v in s3.values()),
                         "all_ci_exclude_zero": all(v["ci95"][0] > 0 for v in s3.values())}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("fallback instances", out["fallback_instances"], "/", out["n_instances"], "scenarios affected", out["scenarios_with_any_fallback"], out["fallback_by_family"])
    for k, v in out["S1_excluding_fallback_instances"].items():
        print("S1", k, round(v["mean_diff"], 4), [round(x, 4) for x in v["ci95"]], f"p={v['wilcoxon_p']:.2e}", v["first_lower/ties/first_higher"])
    for k in ("D_vs_B", "B_vs_A", "C_vs_B", "D_vs_C"):
        v = out["S2_first_seed_only"][k]
        print("S2", k, round(v["mean_diff"], 4), [round(x, 4) for x in v["ci95"]], f"p={v['wilcoxon_p']:.2e}")
    print("S3", out["S3_summary"])


if __name__ == "__main__":
    main()
