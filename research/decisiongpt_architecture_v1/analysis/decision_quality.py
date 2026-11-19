"""Analysis A (protocol section 3): independent re-computation of the locked decision-quality contrasts from the stored raw records (read-only).

    python research/decisiongpt_architecture_v1/analysis/decision_quality.py

Outcome: stored exogenous normalised regret of the selected action (0 = oracle action). Unit of analysis: the scenario (regret averaged over its seeds).
Reference policies (naive / greedy / classical optimizer) are scored with the identical formula from the stored policy values:
regret = (oracle_value - value) / (oracle_value - worst_value).
Writes results/decision_quality.json. Replication check against the stored statistical_results.json is included.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "research" / "decisiongpt_architecture_v1" / "results" / "decision_quality.json"
BOOT_B, BOOT_SEED = 10000, 20261023
STUDIES = {"r1": REPO / "experiments" / "r1", "upgraded_v1": REPO / "experiments" / "upgraded_controlled_v1"}
CONTRASTS = [("B", "A"), ("C", "B"), ("D", "C"), ("D", "B"), ("D", "A"), ("D", "greedy"), ("D", "classical"), ("D", "naive")]
HOLM_SETS = {"r1": [("B", "A"), ("C", "B"), ("D", "C"), ("D", "B")],            # the locked R1 family
             "upgraded_v1": [("B", "A"), ("C", "B"), ("D", "A"), ("D", "B")]}   # the locked upgraded-v1 family
NEAR = (0.05, 0.10, 0.20)


def ref_regret(base: dict, name: str) -> float | None:
    o = base["oracle"]
    span = o["value"] - o["worst_value"]
    v = base[name]["value"]
    if span <= 0 or v is None:
        return None
    return (o["value"] - v) / span


def load(study_dir: Path):
    d = json.loads((study_dir / "results.json").read_text(encoding="utf-8"))
    per = defaultdict(lambda: defaultdict(list))     # scenario -> policy -> [regret per seed]
    fam = {}
    n_excl = 0
    for rec in d["records"]:
        r = rec["result"]
        if r.get("exclude_from_primary"):
            n_excl += 1
            continue
        sid = r["scenario_id"]
        fam[sid] = r["family_id"]
        for k, c in r["conditions"].items():
            if c["status"] == "ok" and c["primary_regret"] is not None:
                per[sid][k].append(c["primary_regret"])
        for k, key in (("greedy", "greedy"), ("classical", "classical_optimizer"), ("naive", "naive")):
            x = ref_regret(r["baselines"], key)
            if x is not None:
                per[sid][k].append(x)
    return d, per, fam, n_excl


def paired(per, fam, a, b, rng, fams=None):
    sids = [s for s in sorted(per) if (fams is None or fam[s] in fams) and per[s].get(a) and per[s].get(b)]
    x = np.array([np.mean(per[s][a]) for s in sids])
    y = np.array([np.mean(per[s][b]) for s in sids])
    diff = x - y
    n = len(diff)
    if n == 0:
        return None
    idx = rng.integers(0, n, size=(BOOT_B, n))
    bs = diff[idx].mean(axis=1)
    nz = diff[diff != 0]
    if len(nz) >= 1:
        w = stats.wilcoxon(nz, zero_method="wilcox", alternative="two-sided", method="auto")
        ranks = stats.rankdata(np.abs(nz))
        rb = float((ranks[nz > 0].sum() - ranks[nz < 0].sum()) / ranks.sum())
        p = float(w.pvalue)
    else:
        rb, p = 0.0, 1.0
    return {"n_scenarios": n, "mean_a": float(x.mean()), "mean_b": float(y.mean()), "mean_diff_a_minus_b": float(diff.mean()),
            "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], "wilcoxon_p": p, "rank_biserial_a_vs_b": rb,
            "a_better_(lower)": int((diff < 0).sum()), "ties": int((diff == 0).sum()), "a_worse_(higher)": int((diff > 0).sum())}


def holm(ps: dict[str, float]) -> dict[str, float]:
    order = sorted(ps, key=ps.get)
    out, run = {}, 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, (len(ps) - i) * ps[k]))
        out[k] = run
    return out


def main() -> None:
    res = {"protocol": "research/decisiongpt_architecture_v1/EXPERIMENT_PROTOCOL.md section 3", "bootstrap": {"B": BOOT_B, "seed": BOOT_SEED}, "studies": {}}
    for name, sd in STUDIES.items():
        d, per, fam, n_excl = load(sd)
        rng = np.random.default_rng(BOOT_SEED)
        families = sorted(set(fam.values()))
        out = {"n_scenarios": len(per), "n_records": len(d["records"]), "n_excluded_records": n_excl, "families": families,
               "mean_regret_by_policy": {}, "contrasts": {}, "by_family": {}, "near_optimal": {}}
        pols = ["A", "B", "C", "D", "greedy", "classical", "naive"]
        for pol in pols:
            v = np.array([np.mean(per[s][pol]) for s in sorted(per) if per[s].get(pol)])
            bs = v[rng.integers(0, len(v), size=(BOOT_B, len(v)))].mean(axis=1)
            out["mean_regret_by_policy"][pol] = {"mean": float(v.mean()), "n": len(v), "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}
        for a, b in CONTRASTS:
            out["contrasts"][f"{a}_vs_{b}"] = paired(per, fam, a, b, rng)
        out["holm_family"] = [f"{a}_vs_{b}" for a, b in HOLM_SETS[name]]
        h = holm({f"{a}_vs_{b}": out["contrasts"][f"{a}_vs_{b}"]["wilcoxon_p"] for a, b in HOLM_SETS[name]})
        for k, v in h.items():
            out["contrasts"][k]["holm_p_over_primary_four"] = v
        for f in families:
            out["by_family"][f] = {f"{a}_vs_{b}": paired(per, fam, a, b, rng, {f}) for a, b in (("D", "B"), ("B", "A"), ("D", "C"))}
        for thr in NEAR:
            out["near_optimal"][str(thr)] = {}
            for pol in pols:
                vals = [x for s in per for x in per[s].get(pol, [])]
                out["near_optimal"][str(thr)][pol] = float(np.mean([x <= thr for x in vals]))
        # replication check against stored statistical results (R1 primary)
        sp = sd / "statistical_results.json"
        if sp.exists():
            st = json.loads(sp.read_text(encoding="utf-8"))
            out["stored_statistical_results_keys"] = list(st.keys())[:20]
        res["studies"][name] = out
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    for name, o in res["studies"].items():
        print(name, "scenarios", o["n_scenarios"], {k: round(v["mean"], 4) for k, v in o["mean_regret_by_policy"].items()})
        for k in ("B_vs_A", "C_vs_B", "D_vs_C", "D_vs_B", "D_vs_A"):
            c = o["contrasts"][k]
            print(" ", k, round(c["mean_diff_a_minus_b"], 4), [round(x, 4) for x in c["ci95"]], "p", f"{c['wilcoxon_p']:.2e}", "holm", c.get("holm_p_over_primary_four"), "rb", round(c["rank_biserial_a_vs_b"], 3), c["a_better_(lower)"], c["ties"], c["a_worse_(higher)"])


if __name__ == "__main__":
    main()
