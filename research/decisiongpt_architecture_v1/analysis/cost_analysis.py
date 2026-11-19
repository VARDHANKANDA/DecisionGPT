"""Analysis B + C (protocol sections 4-5): summarise the E-COST measurement and combine it with stored decision quality.

    python research/decisiongpt_architecture_v1/analysis/cost_analysis.py

Reads results/cost_measurement.jsonl (repeat 0 = main run of every locked R1 scenario with the first locked seed; repeat 1,2 = timing repeats of a 48-scenario subset)
and experiments/r1/results.json (stored regrets, read-only). Writes results/cost_summary.json.
End-to-end time: B = shared simulation + B pick; C = shared simulation + C pick; D = full pipeline (decision_service.analyze_goal). A recommends nothing (no decision cost).
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
R = REPO / "research" / "decisiongpt_architecture_v1" / "results"
BOOT_B, SEED = 10000, 20261024


def q(x, p):
    return float(np.percentile(x, p))


def desc(x):
    x = np.asarray(x, float)
    return {"n": int(len(x)), "median": q(x, 50), "iqr": [q(x, 25), q(x, 75)], "p95": q(x, 95), "mean": float(x.mean()), "min": float(x.min()), "max": float(x.max())}


def boot_median_ratio(num, den, rng):
    lr = np.log(np.asarray(num) / np.asarray(den))
    idx = rng.integers(0, len(lr), size=(BOOT_B, len(lr)))
    m = np.median(lr[idx], axis=1)
    return {"median_ratio": float(np.exp(np.median(lr))), "ci95": [float(np.exp(np.percentile(m, 2.5))), float(np.exp(np.percentile(m, 97.5)))]}


def main():
    rows = [json.loads(l) for l in (R / "cost_measurement.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    ok = [r for r in rows if r["error"] is None]
    errs = [r for r in rows if r["error"] is not None]
    main_rows = [r for r in ok if r["repeat"] == 0]
    rng = np.random.default_rng(SEED)
    out = {"n_rows": len(rows), "n_errors": len(errs), "errors": [(r["scenario_id"], r["error"]) for r in errs][:10], "n_main": len(main_rows)}

    def e2e(r):
        sh, ph = r["phase_seconds"].get("shared_sim", 0.0), r["phase_seconds"]
        return {"B": sh + r["stage_latency_s"]["B"], "C": sh + r["stage_latency_s"]["C"], "D": ph.get("D", r["stage_latency_s"]["D"]),
                "shared": sh, "B_pick": r["stage_latency_s"]["B"], "C_pick": r["stage_latency_s"]["C"],
                "D_sim": r["sim_seconds_by_phase"].get("D", 0.0), "D_overhead": ph.get("D", r["stage_latency_s"]["D"]) - r["sim_seconds_by_phase"].get("D", 0.0),
                "shared_sim_in_sim": r["sim_seconds_by_phase"].get("shared_sim", 0.0)}

    T = {r["scenario_id"]: e2e(r) for r in main_rows}
    sids = sorted(T)
    arr = {k: np.array([T[s][k] for s in sids]) for k in ("B", "C", "D", "shared", "B_pick", "C_pick", "D_sim", "D_overhead", "shared_sim_in_sim")}
    out["end_to_end_seconds"] = {k: desc(arr[k]) for k in ("B", "C", "D")}
    out["components_seconds"] = {k: desc(arr[k]) for k in ("shared", "B_pick", "C_pick", "D_sim", "D_overhead")}
    out["D_orchestration_overhead_share_of_D"] = desc(arr["D_overhead"] / arr["D"])
    out["D_overhead_over_own_sim"] = desc(arr["D_overhead"] / arr["D_sim"])
    out["D_sim_over_shared_sim_(same_work_twice)"] = boot_median_ratio(arr["D_sim"], arr["shared_sim_in_sim"], rng)
    out["ratios"] = {"D_over_B": boot_median_ratio(arr["D"], arr["B"], rng), "D_over_C": boot_median_ratio(arr["D"], arr["C"], rng), "C_over_B": boot_median_ratio(arr["C"], arr["B"], rng)}
    out["ratios"]["D_over_B"]["share_D_slower"] = float(np.mean(arr["D"] > arr["B"]))
    out["ratios"]["D_over_B"]["per_instance"] = desc(arr["D"] / arr["B"])
    out["d_minus_b_seconds"] = desc(arr["D"] - arr["B"])
    out["incremental_over_b_seconds"] = {"C": desc(arr["C"] - arr["B"]), "D": desc(arr["D"] - arr["B"])}

    # counts (per instance, main rows)
    cnt = defaultdict(list)
    for r in main_rows:
        c = r["counts"]
        sh, d, dg = c.get("shared_sim", {}), c.get("D", {}), c.get("diagnostics", {})
        oth = c.get("other", {})
        cnt["sim_calls_shared_(B,C)"].append(sh.get("simulate_strategy_calls", 0))
        cnt["forecast_model_runs_shared_(B,C)"].append(sh.get("model_forecast_runs", 0))
        cnt["sim_calls_D"].append(d.get("simulate_strategy_calls", 0))
        cnt["forecast_model_runs_D"].append(d.get("model_forecast_runs", 0))
        cnt["agent_BA_D"].append(d.get("agent_BA", 0))
        cnt["agent_FA_D"].append(d.get("agent_FA", 0))
        cnt["agent_RM_D"].append(d.get("agent_RM", 0))
        cnt["agent_single_C_pick"].append(oth.get("agent_single", 0))
        cnt["llm_facade_template_calls_D"].append(sum(v for k, v in d.items() if k.startswith("llm_facade_")))
        cnt["llm_network_requests_attempted_all"].append(sum(v.get("llm_requests_attempted", 0) for v in c.values()))
    out["counts_per_decision"] = {k: {"min": int(min(v)), "median": float(np.median(v)), "max": int(max(v))} for k, v in cnt.items()}

    # timing repeats
    rep = defaultdict(list)
    for r in ok:
        rep[r["scenario_id"]].append(e2e(r))
    cv = {"B": [], "C": [], "D": []}
    for s, lst in rep.items():
        if len(lst) >= 3:
            for k in cv:
                v = np.array([x[k] for x in lst])
                cv[k].append(float(v.std(ddof=1) / v.mean()))
    out["repeat_cv"] = {k: (desc(v) if v else None) for k, v in cv.items()}
    out["n_scenarios_with_3_repeats"] = len(cv["D"])
    ratio_rep = [np.median([x["D"] / x["B"] for x in lst]) for lst in rep.values() if len(lst) >= 3]
    out["D_over_B_repeat_median_by_scenario"] = desc(ratio_rep) if ratio_rep else None

    # determinism
    from collections import Counter as collections_counter
    stored_sel = {(rec["scenario_id"], rec["seed"]): {k: c["selected_action_key"] for k, c in rec["result"]["conditions"].items()} for rec in json.loads((REPO / "experiments/r1/results.json").read_text(encoding="utf-8"))["records"]}
    chk = [r.get("matches_stored_locked_run") for r in main_rows]                 # main run: one instance per locked scenario (first seed)
    out["determinism_matches_stored"] = {"checked": len(chk), "match": int(sum(1 for c in chk if c)), "mismatch": int(sum(1 for c in chk if c is False))}
    chk_all = [r.get("matches_stored_locked_run") for r in ok]                    # including the timing repeats (same instances re-run)
    out["determinism_matches_stored_incl_repeats"] = {"checked": len(chk_all), "match": int(sum(1 for c in chk_all if c)), "mismatch": int(sum(1 for c in chk_all if c is False))}
    mm = [r for r in main_rows if r.get("matches_stored_locked_run") is False]
    out["determinism_mismatch_detail_main"] = {"n": len(mm), "families": dict(collections_counter([r["family_id"] for r in mm])),
                                               "conditions_differing": sorted({k for r in mm for k in "ABCD" if r["selected"][k] != stored_sel[(r["scenario_id"], r["seed"])][k]})}

    # by family
    fam = defaultdict(list)
    for r in main_rows:
        fam[r["family_id"]].append(r["scenario_id"])
    out["by_family_median_seconds"] = {f: {k: float(np.median([T[s][k] for s in ss])) for k in ("B", "C", "D")} for f, ss in sorted(fam.items())}

    # quality-cost: stored regret for the same scenarios (mean over the 10 stored seeds), D/B etc.
    stored = json.loads((REPO / "experiments/r1/results.json").read_text(encoding="utf-8"))["records"]
    reg = defaultdict(lambda: defaultdict(list))
    for rec in stored:
        for k, c in rec["result"]["conditions"].items():
            if c["primary_regret"] is not None and not rec["result"]["exclude_from_primary"]:
                reg[rec["scenario_id"]][k].append(c["primary_regret"])
    usable = [s for s in sids if s in reg]
    pol = {}
    for k in ("A", "B", "C", "D"):
        mr = [float(np.mean(reg[s][k])) for s in usable]
        row = {"mean_regret": float(np.mean(mr)), "n_scenarios": len(usable)}
        if k != "A":
            row["median_seconds"] = float(np.median([T[s][k] for s in usable]))
            row["mean_seconds"] = float(np.mean([T[s][k] for s in usable]))
        else:
            row["median_seconds"] = 0.0
            row["mean_seconds"] = 0.0
        pol[k] = row
    # Pareto frontier on (mean_seconds, mean_regret): a policy is dominated if another is no worse on both and strictly better on one
    names = list(pol)
    front = []
    for a in names:
        dom = any(pol[b]["mean_seconds"] <= pol[a]["mean_seconds"] and pol[b]["mean_regret"] <= pol[a]["mean_regret"] and (pol[b]["mean_seconds"] < pol[a]["mean_seconds"] or pol[b]["mean_regret"] < pol[a]["mean_regret"]) for b in names if b != a)
        pol[a]["dominated"] = bool(dom)
        if not dom:
            front.append(a)
    out["quality_cost"] = {"policies": pol, "pareto_frontier": front, "note": "A is a status-quo proxy (Amendment 1); regret = stored locked R1 mean over 10 seeds; seconds = E-COST seed 1 (scenario-level)"}
    nearopt = {}
    for thr in (0.05, 0.10, 0.20):
        nearopt[str(thr)] = {}
        for k in ("A", "B", "C", "D"):
            vals = [x for s in usable for x in reg[s][k]]
            share = float(np.mean([v <= thr for v in vals]))
            ms = pol[k]["mean_seconds"]
            nearopt[str(thr)][k] = {"share_near_optimal": share, "mean_seconds": ms, "seconds_per_near_optimal_decision": (ms / share if share > 0 and ms > 0 else None)}
    out["near_optimal"] = nearopt
    # paired scenario-level relation between D-vs-B time cost and D-vs-B regret
    dd = np.array([np.mean(reg[s]["D"]) - np.mean(reg[s]["B"]) for s in usable])
    dt = np.array([T[s]["D"] - T[s]["B"] for s in usable])
    out["extra_time_vs_regret_change_D_minus_B"] = {"n": len(usable), "share_scenarios_D_better_and_slower": float(np.mean((dd < 0) & (dt > 0))), "share_scenarios_D_worse_and_slower": float(np.mean((dd > 0) & (dt > 0))),
                                                    "share_scenarios_D_equal_regret_and_slower": float(np.mean((dd == 0) & (dt > 0))),
                                                    "spearman": None}
    try:
        from scipy.stats import spearmanr
        sr = spearmanr(dt, dd)
        out["extra_time_vs_regret_change_D_minus_B"]["spearman"] = {"rho": float(sr.statistic), "p": float(sr.pvalue), "note": "exploratory"}
    except Exception:
        pass

    # re-run on a different calendar date: contrasts recomputed from the NEW run's regrets (first seed) next to the stored first-seed values
    newreg = {r["scenario_id"]: r["regret"] for r in main_rows}
    first_seed = stored[0]["seed"]
    old = {rec["scenario_id"]: {k: c["primary_regret"] for k, c in rec["result"]["conditions"].items()} for rec in stored if rec["seed"] == first_seed}
    rr = {}
    for a, b in (("B", "A"), ("C", "B"), ("D", "C"), ("D", "B")):
        sidsx = [s for s in sids if s in old]
        dn = np.array([newreg[s][a] - newreg[s][b] for s in sidsx])
        do = np.array([old[s][a] - old[s][b] for s in sidsx])
        bs = dn[rng.integers(0, len(dn), size=(BOOT_B, len(dn)))].mean(axis=1)
        rr[f"{a}_vs_{b}"] = {"n": len(dn), "new_run_mean": float(dn.mean()), "new_run_ci95": [q(bs, 2.5), q(bs, 97.5)], "stored_first_seed_mean": float(do.mean())}
    flips = [s for s in sids if s in old and any(newreg[s][k] != old[s][k] for k in "ABCD")]
    out["rerun_on_new_date"] = {"contrasts": rr, "instances_with_any_regret_difference": len(flips), "n": len([s for s in sids if s in old]),
                                "conditions_differing": {k: int(sum(1 for s in sids if s in old and newreg[s][k] != old[s][k])) for k in "ABCD"},
                                "note": "the harness anchors each synthetic history to the run date (date.today()); the stored locked run was executed on a different date, so near-tie choices of D can flip"}
    (R / "cost_summary.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("n_rows", "n_errors", "n_main", "end_to_end_seconds", "ratios", "counts_per_decision", "determinism_matches_stored")}, indent=1)[:3500])
    print(json.dumps(out["quality_cost"]["policies"], indent=1))


if __name__ == "__main__":
    main()
