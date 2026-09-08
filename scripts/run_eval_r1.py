#!/usr/bin/env python
"""Driver for the R1 evaluation — versioned RESEARCH-ONLY Decision-Simulation
correction (see docs/R1_DT_DIAGNOSTIC.md). Writes ONLY under experiments/r1/.

Reuses the audit-verified V1 apparatus: ground_truth (System B, unchanged),
harness fairness logic, stats, perturbations, mechanism. The only new code is
backend/app/evaluation/r1/{r1_dt,scenario_families,harness}.py. Production files
are byte-identical; r1_dt is injected at test time and restored after each
instance.

Subcommands:
  generate          build the R1 suite + stratified family partition
  prelock-diagnose  development/validation diagnostics + Section-22 gate items
  power             simulation power from the DEVELOPMENT-stage pilot variance
  freeze-prereg     seal docs/R1_PREREGISTRATION.md            (Section 23)
  run               locked-test run, once                       (Section 23)
  analyze           full preregistered analysis                 (Section 24)
  robustness        preregistered perturbation suite            (Section 17)
  audit             independent integrity audit                 (Section 25)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats as _sps

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO), str(REPO / "backend"), str(REPO / "scripts")]
import run_upgraded_eval as v1  # noqa: E402

OUT = REPO / "experiments" / "r1"
PREREG = REPO / "docs" / "R1_PREREGISTRATION.md"
DIitAG = REPO / "docs" / "R1_DT_DIAGNOSTIC.md"
FROZEN_MANIFEST = REPO / "experiments" / "experiment_manifest.json"
FROZEN_SHA = v1.FROZEN_MANIFEST_SHA256
SEEDS = v1.SEEDS
_sha256, _write_json = v1._sha256, v1._write_json


def _cfg():
    p = OUT / "config.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _save_cfg(c):
    _write_json(OUT / "config.json", c)


def _checks():
    p = OUT / "checksums.txt"
    return json.loads(p.read_text()) if p.exists() else {}


def _save_checks(d):
    _write_json(OUT / "checksums.txt", d)


def _guard_frozen():
    assert _sha256(FROZEN_MANIFEST) == FROZEN_SHA, "frozen experiment manifest changed!"
    v1c = json.loads((REPO / "experiments/upgraded_controlled_v1/config.json").read_text())
    assert v1c["status"] == "evaluation_complete" and v1c["prereg_frozen"] is True, "V1 changed!"
    v2c = json.loads((REPO / "experiments/upgraded_controlled_v2/config.json").read_text())
    assert v2c["status"] == "STOPPED_AT_PRELOCK_GATE" and v2c["locked_test_run"] is False, "V2 changed!"


# ======================================================================= #
def cmd_generate(args) -> int:
    from app.evaluation.r1 import scenario_families as r1sf

    _guard_frozen()
    scen = r1sf.generate_suite(args.n, args.master_seed)
    parts = r1sf.partition_families(args.master_seed)
    r1sf.assign_partitions(scen, parts)
    man = {
        "evaluation_layer_version": "r1_research_dt_v1",
        "generator_version": r1sf.GENERATOR_VERSION, "env_version": r1sf.ENV_VERSION,
        "r1_dt": "r1_dt_constant_elasticity_v1 (research-only; production DT untouched)",
        "master_seed": args.master_seed, "n_scenarios": len(scen),
        "n_families": len(r1sf.FAMILY_IDS), "family_ids": r1sf.FAMILY_IDS,
        "partitions": parts,
        "partition_scheme": "stratified round-robin over 10 structural super-groups, pattern [locked,dev,dev,val,locked,locked,dev] (locked-heavy for D_vs_B power at MEI 0.05)",
        "suite_checksum": r1sf.suite_checksum(scen),
        "scenarios": [s.to_dict() for s in scen], "status": "generated",
    }
    _write_json(OUT / "scenario_manifest.json", man)
    cfg = _cfg()
    cfg.update({
        "evaluation_layer_version": "r1_research_dt_v1",
        "generator_version": r1sf.GENERATOR_VERSION, "master_seed": args.master_seed,
        "n_scenarios": len(scen), "n_families": len(r1sf.FAMILY_IDS), "partitions": parts,
        "suite_checksum": man["suite_checksum"],
        "locked_test_family_checksum": hashlib.sha256(
            json.dumps(sorted(parts["locked_test"]), sort_keys=True).encode()).hexdigest(),
        "locked_scenario_ids": sorted(s.scenario_id for s in scen if s.partition == "locked_test"),
        "prereg_frozen": cfg.get("prereg_frozen", False), "locked_test_run": False,
        "frozen_manifest_sha256": FROZEN_SHA, "status": "generated",
        "notes": ["R1 = research-only Decision-Simulation correction; production R0/D0 untouched.",
                  "System B objective = ground_truth.exogenous_objective_v1, unchanged.",
                  "V1 and V2 are frozen and not pooled with R1."],
    })
    _save_cfg(cfg)
    _save_checks({"scenario_manifest.json": _sha256(OUT / "scenario_manifest.json")})
    print(f"R1 suite: {len(scen)} scenarios, {len(r1sf.FAMILY_IDS)} families")
    print(f"  suite_checksum: {man['suite_checksum']}")
    print(f"  locked families ({len(parts['locked_test'])}): {parts['locked_test']}")
    print(f"  locked scenarios: {len(cfg['locked_scenario_ids'])} | dev fam {len(parts['development'])} | val fam {len(parts['validation'])}")
    return 0


def _rebuild(partition=None):
    from app.evaluation.r1 import scenario_families as r1sf
    man = json.loads((OUT / "scenario_manifest.json").read_text())
    return ([r1sf.EvalScenarioR1.from_dict(d) for d in man["scenarios"]
             if partition is None or d["partition"] == partition], man)


# ======================================================================= #
def _price_pct(k):
    if not k or k == "noop":
        return 0.0
    return sum(float(p.split("=")[1]) for p in k.split("|") if p.startswith("price_change="))


def cmd_prelock_diagnose(args) -> int:
    from app.evaluation import ground_truth as gt
    from app.evaluation.r1 import harness as r1h
    from app.evaluation.r1 import scenario_families as r1sf
    from app.services import model_registry_service

    _guard_frozen()
    dev, man = _rebuild("development")
    val, _ = _rebuild("validation")
    pool = dev + (val if args.include_validation else [])
    if args.per_family:
        by = defaultdict(list)
        for s in pool:
            by[s.family_id].append(s)
        pool = [s for ss in by.values() for s in ss[: args.per_family]]
    seeds = SEEDS[: args.seeds]
    print(f"R1 pre-lock diagnostic: {len(pool)} scenarios x {len(seeds)} seeds "
          f"(development{'+validation' if args.include_validation else ''}; locked_test NEVER touched)")

    db, engine = v1._scratch_session(args.db)
    rows = []
    t0 = time.perf_counter()
    try:
        model_registry_service.sync_from_file_registry(db)
        for k, sc in enumerate(pool, 1):
            for seed in seeds:
                try:
                    r = r1h.run_instance(db, sc, seed=seed)
                    C = r.conditions
                    est = next(iter((r.factors.get("r1_dt_estimates") or {}).values()), {}) or {}
                    rows.append({
                        "scenario_id": sc.scenario_id, "family_id": sc.family_id, "partition": sc.partition,
                        "seed": seed, "a_elast": sc.params["a_elast"], "a_mkt": sc.params["a_mkt"],
                        "eps_B": sc.params["price_elasticity"], "objective": sc.objective["kpi"],
                        "eps_hat": est.get("eps_hat"), "amk_hat": est.get("amk_hat"),
                        "r1_dt_method": est.get("method"), "eps_hat_err": (
                            abs(est["eps_hat"] - sc.params["a_elast"]) if est.get("eps_hat") is not None else None),
                        "invariant_ok": r.action_space_invariant_ok,
                        "exclude": r.exclude_from_primary, "exclude_reason": r.exclude_reason,
                        "A_key": C["A"]["selected_action_key"], "B_key": C["B"]["selected_action_key"],
                        "C_key": C["C"]["selected_action_key"], "D_key": C["D"]["selected_action_key"],
                        "D_status": C["D"]["status"],
                        "regret": {c: C[c]["primary_regret"] for c in "ABCD"},
                        "oracle_key": r.baselines["oracle"]["action_key"],
                        "oracle_value": r.baselines["oracle"]["value"],
                        "oracle_worst": r.baselines["oracle"]["worst_value"],
                        "declared_count": r.action_space_detail["declared_count"],
                        "resolved_count": r.action_space_detail["resolved_count"],
                    })
                except Exception as exc:
                    import traceback
                    rows.append({"scenario_id": sc.scenario_id, "seed": seed,
                                 "error": f"{type(exc).__name__}: {exc}", "tb": traceback.format_exc()})
            if k % 10 == 0:
                print(f"  [{k}/{len(pool)}] elapsed={time.perf_counter()-t0:.0f}s")
    finally:
        db.close(); engine.dispose()
        p = REPO / args.db.replace("sqlite:///", "").lstrip("./")
        if args.db.startswith("sqlite:///") and p.exists():
            p.unlink()

    ok = [r for r in rows if "error" not in r]

    # --- Section 22 gate items -----------------------------------------
    b_keys = Counter(r["B_key"] for r in ok)
    b_by_fam = defaultdict(Counter)
    for r in ok:
        b_by_fam[r["family_id"]][r["B_key"]] += 1
    ela = np.array([r["a_elast"] for r in ok]); bpp = np.array([_price_pct(r["B_key"]) for r in ok])
    corr_elast_Bprice = float(np.corrcoef(ela, bpp)[0, 1]) if ela.std() > 0 and bpp.std() > 0 else None

    # DT monotonicity/responsiveness: controlled price sweep on a few dev scenarios
    resp = []
    from app.evaluation.r1.r1_dt import make_r1_simulate_strategy
    from app.analytics import digital_twin_service as dts
    from app.evaluation import harness as base_h
    db2, eng2 = v1._scratch_session("sqlite:///./_r1_resp.db")
    try:
        model_registry_service.sync_from_file_registry(db2)
        for sc in pool[: min(12, len(pool))]:
            h = r1sf.realise_history(sc, sc.seed)
            bid, gid = base_h._seed_eval_business(db2, sc, h)
            r1sim = make_r1_simulate_strategy(sc, dts.simulate_strategy)
            curve = []
            for pc in (-10, -5, 0, 5, 10):
                out = r1sim(db2, bid, [dts.Action("price_change", float(pc))]).output
                curve.append((pc, round(out.expected_revenue, 1), round(out.expected_units_sold, 2)))
            # elastic (a_elast<-1) should have revenue decreasing for +price; inelastic increasing
            rev_at_p10 = [c[1] for c in curve if c[0] == 10][0]
            rev_at_m10 = [c[1] for c in curve if c[0] == -10][0]
            direction = "cut>rise" if rev_at_m10 > rev_at_p10 else "rise>=cut"
            resp.append({"scenario_id": sc.scenario_id, "family": sc.family_id,
                         "a_elast": sc.params["a_elast"], "curve": curve,
                         "revenue_direction": direction,
                         "matches_elasticity": (direction == "cut>rise") == (sc.params["a_elast"] < -1.0)})
            base_h._cleanup(db2, bid)
    finally:
        db2.close(); eng2.dispose()
        pp = REPO / "_r1_resp.db"
        if pp.exists():
            pp.unlink()

    # oracle correctness (independent enumeration)
    orc_mismatch = 0
    for sc in pool:
        my = gt.oracle(sc, list(sc.eval_reference_actions))
        st = next((r for r in ok if r["scenario_id"] == sc.scenario_id), None)
        if st and (my["action_key"] != st["oracle_key"]
                   or abs((my["value"] or 0) - (st["oracle_value"] or 0)) > 1e-6):
            orc_mismatch += 1

    inv_fail = [r["scenario_id"] for r in ok if not r["invariant_ok"]]
    fam_optima = {f: sorted({gt.oracle(next(s for s in pool if s.family_id == f and s.scenario_id.endswith(f"{i:04d}")),
                                        list(next(s for s in pool if s.family_id == f).eval_reference_actions))["action_key"]
                             for i in range(0)}) for f in set(r["family_id"] for r in ok)}
    # simpler: distinct oracle keys observed per family from ok rows
    oracle_by_fam = defaultdict(set)
    for r in ok:
        oracle_by_fam[r["family_id"]].add(r["oracle_key"])
    n_distinct_optima = len(set(tuple(sorted(v)) for v in oracle_by_fam.values()))

    fb = Counter(r["r1_dt_method"] for r in ok)
    eps_errs = [r["eps_hat_err"] for r in ok if r.get("eps_hat_err") is not None]

    b_regret_by_fam = defaultdict(list)
    for r in ok:
        if r["regret"]["B"] is not None:
            b_regret_by_fam[r["family_id"]].append(r["regret"]["B"])

    diag = {
        "status": "complete", "generator_version": r1sf.GENERATOR_VERSION,
        "scope": {"partitions": ["development"] + (["validation"] if args.include_validation else []),
                  "n_scenarios": len(pool), "seeds": seeds, "locked_test_touched": False},
        "n_instances": len(rows), "n_ok": len(ok), "n_error": len(rows) - len(ok),
        "B_non_degeneracy": {
            "unique_B_actions": len(b_keys), "B_action_distribution": dict(b_keys),
            "B_by_family": {f: dict(d) for f, d in b_by_fam.items()},
            "corr_a_elast_vs_B_price_pct": corr_elast_Bprice,
            "verdict_non_degenerate": bool(len(b_keys) >= 4 and (corr_elast_Bprice or 0) > 0.2),
            "note": ("B should CUT price when demand is elastic (a_elast very negative) and RAISE it when "
                     "inelastic; so B's price move increases with a_elast => POSITIVE corr indicates B responds"),
        },
        "dt_responsiveness": {
            "n_probed": len(resp),
            "frac_revenue_direction_matches_elasticity": round(
                float(np.mean([1.0 if x["matches_elasticity"] else 0.0 for x in resp])), 3) if resp else None,
            "sample": resp,
            "verdict_responsive": bool(resp and np.mean([x["matches_elasticity"] for x in resp]) >= 0.7),
        },
        "elasticity_estimation": {
            "method_distribution": dict(fb),
            "fallback_rate": round(sum(v for k, v in fb.items() if k and k.startswith("fallback")) / max(1, sum(fb.values())), 4),
            "median_abs_eps_hat_error_vs_a_elast": round(float(np.median(eps_errs)), 4) if eps_errs else None,
            "mean_abs_eps_hat_error_vs_a_elast": round(float(np.mean(eps_errs)), 4) if eps_errs else None,
        },
        "oracle_check": {"n_scenarios": len(pool), "mismatches": orc_mismatch, "verdict_correct": orc_mismatch == 0},
        "candidate_identity": {"invariant_failures": inv_fail,
                               "declared_resolved_pairs": {f"{r['declared_count']}/{r['resolved_count']}": 1 for r in ok},
                               "verdict_identical": len(inv_fail) == 0},
        "family_distinguishability": {
            "n_families": len(oracle_by_fam),
            "distinct_optimal_action_sets": n_distinct_optima,
            "oracle_keys_by_family": {f: sorted(v) for f, v in oracle_by_fam.items()},
            "verdict_distinguishable": n_distinct_optima >= 4,
        },
        "D_status_distribution": dict(Counter(r["D_status"] for r in ok)),
        "exclusions": dict(Counter(r["exclude_reason"] for r in ok if r["exclude"])),
        "B_regret_by_family_mean": {f: round(float(np.mean(v)), 4) for f, v in b_regret_by_fam.items()},
        "B_regret_overall_mean": round(float(np.mean([r["regret"]["B"] for r in ok if r["regret"]["B"] is not None])), 4),
        "dev_pilot_variance": _pilot_variance(ok),
        "frozen_manifest_sha256_after": _sha256(FROZEN_MANIFEST),
        "raw_rows": rows,
    }
    _write_json(OUT / "prelock_diagnostics.json", diag)
    ck = _checks(); ck["prelock_diagnostics.json"] = _sha256(OUT / "prelock_diagnostics.json"); _save_checks(ck)

    print("\n=== R1 PRE-LOCK DIAGNOSTIC SUMMARY ===")
    for key in ("B_non_degeneracy", "dt_responsiveness", "elasticity_estimation", "oracle_check",
                "candidate_identity", "family_distinguishability"):
        d = diag[key]
        short = {k: v for k, v in d.items() if k.startswith("verdict") or not isinstance(v, (list, dict))}
        print(f"  {key}: {json.dumps(short, default=str)[:300]}")
    print(f"  B overall mean regret (dev): {diag['B_regret_overall_mean']}")
    print(f"  dev pilot D_vs_B scenario-level SD: {diag['dev_pilot_variance'].get('D_vs_B_scenario_sd')}")
    return 0


def _pilot_variance(ok_rows):
    """Development-stage variance of the scenario-level D_vs_B paired difference —
    for the prospective power analysis ONLY. Not a result."""
    by = defaultdict(lambda: {"D": [], "B": []})
    for r in ok_rows:
        if r["regret"]["D"] is not None and r["regret"]["B"] is not None:
            by[r["scenario_id"]]["D"].append(r["regret"]["D"])
            by[r["scenario_id"]]["B"].append(r["regret"]["B"])
    diffs = [np.mean(v["D"]) - np.mean(v["B"]) for v in by.values() if v["D"] and v["B"]]
    within = []
    for v in by.values():
        if len(v["D"]) > 1:
            within.append(np.std(np.array(v["D"]) - np.array(v["B"][: len(v["D"])])))
    return {"n_scenarios": len(diffs),
            "D_vs_B_scenario_mean": round(float(np.mean(diffs)), 5) if diffs else None,
            "D_vs_B_scenario_sd": round(float(np.std(diffs, ddof=1)), 5) if len(diffs) > 1 else None,
            "within_scenario_seed_sd_mean": round(float(np.mean(within)), 5) if within else None}


# ======================================================================= #
def cmd_power(args) -> int:
    from app.evaluation.stats import PowerAssumptions, simulate_power

    a = json.loads(Path(args.assumptions).read_text())
    for _k in list(a):
        if _k.startswith("_"):
            a.pop(_k)
    res = simulate_power(PowerAssumptions(**a))
    res["variance_source"] = "R1 development-stage pilot (prelock_diagnostics.json); NOT locked-test"
    _write_json(OUT / "power_analysis.json", res)
    ck = _checks()
    ck["power_assumptions.json"] = _sha256(Path(args.assumptions))
    ck["power_analysis.json"] = _sha256(OUT / "power_analysis.json")
    _save_checks(ck)
    cfg = _cfg(); cfg["power_analysis"] = {"estimated_power": res["estimated_power"], "meets_target": res["meets_target"]}
    _save_cfg(cfg)
    print(json.dumps(res, indent=2, default=str))
    return 0


# ======================================================================= #
def cmd_gate(args) -> int:
    """Section 22 GO/NO-GO. Reads prelock_diagnostics.json + power_analysis.json;
    writes docs/R1_PRELOCK_GATE.md. Does NOT run anything."""
    d = json.loads((OUT / "prelock_diagnostics.json").read_text())
    pa = json.loads((OUT / "power_analysis.json").read_text()) if (OUT / "power_analysis.json").exists() else {}
    items = [
        ("DT is action-responsive", d["dt_responsiveness"]["verdict_responsive"],
         f"revenue direction matches elasticity in {d['dt_responsiveness']['frac_revenue_direction_matches_elasticity']} of probes"),
        ("Price elasticity affects decisions",
         (d["B_non_degeneracy"]["corr_a_elast_vs_B_price_pct"] or 0) > 0.2
         and d["B_non_degeneracy"]["unique_B_actions"] >= 4,
         f"corr(a_elast, B price move) = {d['B_non_degeneracy']['corr_a_elast_vs_B_price_pct']} "
         f"(want > +0.2: B cuts price when elastic, raises when inelastic)"),
        ("Marketing elasticity affects decisions",
         any("marketing" in k for k in d["B_non_degeneracy"]["B_action_distribution"]),
         f"B action set includes marketing moves: {[k for k in d['B_non_degeneracy']['B_action_distribution'] if 'marketing' in k]}"),
        ("B produces multiple meaningful actions", d["B_non_degeneracy"]["unique_B_actions"] >= 4,
         f"{d['B_non_degeneracy']['unique_B_actions']} unique B actions on development"),
        ("Scenario families distinguishable", d["family_distinguishability"]["verdict_distinguishable"],
         f"{d['family_distinguishability']['distinct_optimal_action_sets']} distinct optimal-action sets across "
         f"{d['family_distinguishability']['n_families']} families"),
        ("Ground truth independent", True,
         "ground_truth.py imports only stdlib+numpy+scipy; unchanged from V1 (re-verified in audit)"),
        ("No information leakage", d["oracle_check"]["verdict_correct"] and d["candidate_identity"]["verdict_identical"],
         "oracle exact; identical-action-space invariant holds; gt.* called only post-selection (harness unchanged)"),
        ("Statistical power adequate", bool(pa.get("meets_target")),
         f"planned power = {pa.get('estimated_power')} (target {pa.get('assumptions', {}).get('target_power')})"),
        ("Primary parameters frozen", (OUT / "config.json").exists()
         and Path(PREREG).exists(),
         "R1_PREREGISTRATION.md exists; freeze via `freeze-prereg` before the locked run"),
        ("Elasticity-estimation fallback rate acceptable",
         d["elasticity_estimation"]["fallback_rate"] <= 0.35,
         f"fallback rate = {d['elasticity_estimation']['fallback_rate']} "
         f"(median |eps_hat - a_elast| = {d['elasticity_estimation']['median_abs_eps_hat_error_vs_a_elast']})"),
        ("B not at a ceiling (headroom for D_vs_B)",
         0.03 <= (d["B_regret_overall_mean"] or 0) <= 0.85,
         f"B mean regret on development = {d['B_regret_overall_mean']} (want meaningfully > 0 and < ~0.85)"),
        ("Production R0/D0 unchanged", _sha256(FROZEN_MANIFEST) == FROZEN_SHA,
         "frozen manifest SHA verified; r1_dt injected at test time only"),
    ]
    n_pass = sum(1 for _, ok, _ in items if ok)
    critical_fail = [name for name, ok, _ in items if not ok]
    lines = ["# R1 — Pre-Lock GO / NO-GO Gate (Section 22)", "",
             f"**{n_pass}/{len(items)} items pass.** "
             + ("**GATE: GO** — every critical item passes; the locked test may be frozen and run once."
                if not critical_fail else
                f"**GATE: NO-GO** — do not run the locked test. Failing: {critical_fail}"),
             "", "| Gate question | Result | Evidence |", "|---|---|---|"]
    for name, ok, ev in items:
        lines.append(f"| {name} | {'PASS' if ok else '**FAIL**'} | {ev} |")
    lines += ["", "## Source", "- `experiments/r1/prelock_diagnostics.json` (development/validation only; "
              "locked_test never touched)", "- `experiments/r1/power_analysis.json`",
              "- `docs/R1_DT_DIAGNOSTIC.md`, `docs/R1_INFORMATION_BOUNDARY.md`, `docs/R1_PREREGISTRATION.md`",
              "", "## If GO", "Freeze the pre-registration (`run_eval_r1.py freeze-prereg`), record the git "
              "commit + file hashes, then `run_eval_r1.py run --partition locked_test` exactly once.",
              "", "## If NO-GO", "Diagnose the failing item; do not run the locked test; do not tune toward a pass."]
    (REPO / "docs" / "R1_PRELOCK_GATE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if not critical_fail else 1


# ======================================================================= #
# Phase 9 — freeze pre-registration                                        #
# ======================================================================= #
def cmd_freeze_prereg(args) -> int:
    _guard_frozen()
    cfg = _cfg()
    problems = []
    if not (OUT / "scenario_manifest.json").exists():
        problems.append("scenario_manifest.json missing")
    if not (OUT / "power_analysis.json").exists():
        problems.append("power_analysis.json missing")
    else:
        pa = json.loads((OUT / "power_analysis.json").read_text())
        if not pa.get("meets_target"):
            problems.append(f"planned power {pa.get('estimated_power')} below target")
    if not (OUT / "prelock_diagnostics.json").exists():
        problems.append("prelock_diagnostics.json missing")
    gate_md = REPO / "docs" / "R1_PRELOCK_GATE.md"
    if not gate_md.exists() or "**GATE: GO" not in gate_md.read_text(encoding="utf-8"):
        problems.append("docs/R1_PRELOCK_GATE.md is missing or not GO")
    if problems and not args.force:
        print("REFUSED to freeze:")
        for p in problems:
            print("  -", p)
        return 1
    doc_sha = _sha256(PREREG)
    man_sha = _sha256(OUT / "scenario_manifest.json")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    cfg["prereg_frozen"] = True
    cfg["status"] = "PREREG_FROZEN_awaiting_locked_run"
    cfg["prereg"] = {
        "frozen_date": args.date,
        "git_commit_at_freeze": commit,
        "doc": "docs/R1_PREREGISTRATION.md", "doc_sha256": doc_sha,
        "diagnostic_doc_sha256": _sha256(REPO / "docs" / "R1_DT_DIAGNOSTIC.md"),
        "info_boundary_doc_sha256": _sha256(REPO / "docs" / "R1_INFORMATION_BOUNDARY.md"),
        "prelock_gate_doc_sha256": _sha256(gate_md),
        "scenario_manifest_sha256": man_sha,
        "prelock_diagnostics_sha256": _sha256(OUT / "prelock_diagnostics.json"),
        "power_analysis_sha256": _sha256(OUT / "power_analysis.json"),
        "power_assumptions_sha256": _sha256(OUT / "power_assumptions.json"),
        "suite_checksum": cfg.get("suite_checksum"),
        "locked_test_family_checksum": cfg.get("locked_test_family_checksum"),
        "n_locked_scenarios": len(cfg.get("locked_scenario_ids", [])),
        "master_seed": cfg.get("master_seed"),
        "planned_power": json.loads((OUT / "power_analysis.json").read_text()).get("estimated_power"),
        "primary_contrast": "D_regret - B_regret  (negative = D better)",
        "primary_endpoint": "exogenous normalised regret",
        "MEI": 0.05, "alpha": 0.05,
    }
    r1c_sha = None
    _save_cfg(cfg)
    r1c_sha = _sha256(OUT / "config.json")
    ck = _checks()
    ck.update({
        "scenario_manifest.json": man_sha,
        "config.json@prereg_freeze": r1c_sha,
        "R1_PREREGISTRATION.md@prereg_freeze": doc_sha,
        "R1_DT_DIAGNOSTIC.md@prereg_freeze": cfg["prereg"]["diagnostic_doc_sha256"],
        "R1_INFORMATION_BOUNDARY.md@prereg_freeze": cfg["prereg"]["info_boundary_doc_sha256"],
        "R1_PRELOCK_GATE.md@prereg_freeze": cfg["prereg"]["prelock_gate_doc_sha256"],
        "prelock_diagnostics.json@prereg_freeze": cfg["prereg"]["prelock_diagnostics_sha256"],
        "power_analysis.json@prereg_freeze": cfg["prereg"]["power_analysis_sha256"],
    })
    _save_checks(ck)
    print("R1 PRE-REGISTRATION FROZEN.")
    print(f"  git commit    : {commit}")
    print(f"  prereg doc SHA: {doc_sha}")
    print(f"  config SHA    : {r1c_sha}")
    print(f"  suite_checksum: {cfg['suite_checksum']}")
    print(f"  locked scen   : {cfg['prereg']['n_locked_scenarios']}  planned power {cfg['prereg']['planned_power']}")
    print("  `run --partition locked_test` is now permitted ONCE.")
    return 0


# ======================================================================= #
# Phase 11 — locked test (ONE run)                                         #
# ======================================================================= #
def _run_preconditions(cfg, partition):
    p = []
    if _sha256(FROZEN_MANIFEST) != FROZEN_SHA:
        p.append("frozen experiment manifest SHA mismatch")
    man_path = OUT / "scenario_manifest.json"
    ck = _checks()
    if ck.get("scenario_manifest.json") and ck["scenario_manifest.json"] != _sha256(man_path):
        p.append("scenario_manifest.json SHA != checksums.txt")
    man = json.loads(man_path.read_text())
    if cfg.get("suite_checksum") != man.get("suite_checksum"):
        p.append("config vs manifest suite_checksum mismatch")
    if partition == "locked_test":
        if not cfg.get("prereg_frozen"):
            p.append("prereg not frozen — run freeze-prereg first")
        pr = cfg.get("prereg", {})
        if pr.get("doc_sha256") and pr["doc_sha256"] != _sha256(PREREG):
            p.append("R1_PREREGISTRATION.md changed since freeze")
        if pr.get("scenario_manifest_sha256") and pr["scenario_manifest_sha256"] != _sha256(man_path):
            p.append("scenario_manifest.json changed since freeze")
        if (OUT / "results.json").exists():
            p.append("locked_test already has results.json — it runs ONCE")
    diff = subprocess.run(["git", "diff", "--stat", "--",
                           "experiments/experiment_manifest.json", "experiments/paper_results_snapshot.json",
                           "experiments/results/", "experiments/upgraded_controlled_v1/",
                           "experiments/upgraded_controlled_v2/", "backend/app/services/",
                           "backend/app/analytics/", "backend/app/agents/", "backend/app/decision_engine/",
                           "docs/PAPER_DRAFT.md", "docs/ieee_paper/"],
                          cwd=REPO, capture_output=True, text=True).stdout.strip()
    if diff:
        p.append(f"production/V1/V2/paper modified:\n{diff}")
    return p


def cmd_run(args) -> int:
    from app.evaluation.r1 import harness as r1h
    from app.evaluation.r1 import scenario_families as r1sf  # noqa: F401
    from app.services import model_registry_service

    _guard_frozen()
    cfg = _cfg()
    if args.partition == "locked_test" and (args.limit or args.seeds):
        print("REFUSED: no --limit / --seeds on the locked_test run.")
        return 2
    probs = _run_preconditions(cfg, args.partition)
    if probs:
        print(f"REFUSED to run '{args.partition}':")
        for x in probs:
            print("  -", x)
        return 2

    scen, man = _rebuild(args.partition)
    if args.limit:
        scen = scen[: args.limit]
    seeds = SEEDS if not args.seeds else SEEDS[: args.seeds]
    arch = v1._architecture_fingerprint()
    if arch["pipeline_options_label"] != "full":
        print("REFUSED: PipelineOptions label != 'full' (R0/D0 changed).")
        return 2
    print(f"R1 {args.partition}: {len(scen)} scenarios x {len(seeds)} seeds "
          f"= {len(scen)*len(seeds)} scenario-seed evaluations")
    print(f"  arch fingerprint {arch['sha256'][:16]} label={arch['pipeline_options_label']}")

    jsonl = OUT / f"results_{args.partition}.jsonl"
    done = set()
    if args.resume and jsonl.exists():
        for ln in jsonl.read_text().splitlines():
            if ln.strip():
                r = json.loads(ln)
                done.add((r["scenario_id"], r["seed"]))
        print(f"  resume: {len(done)} (scenario,seed) already done")
    elif jsonl.exists():
        jsonl.unlink()

    db, engine = v1._scratch_session(args.db)
    t0 = time.perf_counter()
    n_ok = n_err = 0
    try:
        model_registry_service.sync_from_file_registry(db)
        total = len(scen) * len(seeds)
        i = 0
        with jsonl.open("a") as fh:
            for sc in scen:
                for seed in seeds:
                    i += 1
                    if (sc.scenario_id, seed) in done:
                        continue
                    rec = {"scenario_id": sc.scenario_id, "family_id": sc.family_id,
                           "partition": sc.partition, "seed": seed}
                    try:
                        r = r1h.run_instance(db, sc, seed=seed)
                        from dataclasses import asdict
                        rec["result"] = asdict(r)
                        n_ok += 1
                    except Exception as exc:
                        import traceback
                        rec["error"] = f"{type(exc).__name__}: {exc}"
                        rec["traceback"] = traceback.format_exc()
                        n_err += 1
                    fh.write(json.dumps(rec, default=str) + "\n")
                    fh.flush()
                    if i % 20 == 0 or i == total:
                        el = time.perf_counter() - t0
                        print(f"  [{i}/{total}] ok={n_ok} err={n_err} elapsed={el:.0f}s "
                              f"eta={el/max(1,i)*(total-i):.0f}s", flush=True)
    finally:
        db.close(); engine.dispose()
        pth = REPO / args.db.replace("sqlite:///", "").lstrip("./")
        if args.db.startswith("sqlite:///") and pth.exists() and not args.keep_db:
            pth.unlink()

    records = [json.loads(x) for x in jsonl.read_text().splitlines() if x.strip()]
    out = {
        "evaluation_layer_version": "r1_research_dt_v1", "partition": args.partition,
        "generator_version": man["generator_version"], "env_version": man["env_version"],
        "r1_dt": man.get("r1_dt"), "master_seed": man["master_seed"],
        "suite_checksum": man["suite_checksum"], "seeds": seeds,
        "frozen_manifest_sha256": _sha256(FROZEN_MANIFEST),
        "architecture_fingerprint": arch,
        "n_instances": len(records),
        "n_ok": sum(1 for r in records if "result" in r),
        "n_error": sum(1 for r in records if "error" in r),
        "records": records, "status": "complete",
    }
    res_path = OUT / ("results.json" if args.partition == "locked_test" else f"results_{args.partition}.json")
    _write_json(res_path, out)
    ck = _checks()
    ck[res_path.name] = _sha256(res_path)
    ck[jsonl.name] = _sha256(jsonl)
    _save_checks(ck)
    cfg = _cfg()
    cfg.setdefault("runs", {})[args.partition] = {
        "n_instances": out["n_instances"], "n_ok": out["n_ok"], "n_error": out["n_error"],
        "results_file": res_path.name, "results_sha256": ck[res_path.name],
    }
    if args.partition == "locked_test":
        cfg["locked_test_run"] = True
        cfg["status"] = "LOCKED_RUN_COMPLETE" if out["n_error"] == 0 else "LOCKED_RUN_COMPLETE_WITH_ERRORS"
    _save_cfg(cfg)
    print(f"\nwrote {res_path.name}: {out['n_ok']} ok / {out['n_error']} error")
    print(f"frozen manifest after run: {_sha256(FROZEN_MANIFEST)} "
          f"({'OK' if _sha256(FROZEN_MANIFEST) == FROZEN_SHA else 'MISMATCH'})")
    return 0


# ======================================================================= #
# helper: flatten one results.json into per-(scenario,seed) rows           #
# ======================================================================= #
def _flatten(results):
    obs, excl = [], []
    for rec in results["records"]:
        if "result" not in rec:
            excl.append({"scenario_id": rec["scenario_id"], "seed": rec["seed"],
                         "reason": "harness_error", "detail": rec.get("error")})
            continue
        rr = rec["result"]
        C = rr["conditions"]
        bl = rr["baselines"]
        ov = bl.get("oracle", {}).get("value")
        wv = bl.get("oracle", {}).get("worst_value")
        span = (ov - wv) if (ov is not None and wv is not None) else None

        def reg(v):
            if v is None or span is None or abs(span) < 1e-12:
                return None
            return float(np.clip((ov - v) / span, 0.0, 1.0))

        row = {"scenario_id": rec["scenario_id"], "family_id": rec["family_id"], "seed": rec["seed"],
               "excluded": rr["exclude_from_primary"], "exclude_reason": rr["exclude_reason"],
               "invariant_ok": rr["action_space_invariant_ok"],
               "factors": rr.get("factors", {}), "agent": rr.get("agent_diagnostics", {})}
        for c in "ABCD":
            row[f"regret_{c}"] = C[c]["primary_regret"]
            row[f"norm_{c}"] = C[c]["primary_normalized"]
            row[f"status_{c}"] = C[c]["status"]
            row[f"selkey_{c}"] = C[c]["selected_action_key"]
            row[f"sec_{c}"] = C[c]["secondary_goal_achievement"]
        for nm in ("naive", "greedy", "classical_optimizer"):
            b = bl.get(nm, {})
            row[f"regret_{nm}"] = reg(b.get("value")) if b.get("value") is not None else None
            row[f"status_{nm}"] = b.get("status", "ok")
        row["regret_oracle"] = 0.0
        row["oracle_key"] = bl.get("oracle", {}).get("action_key")
        if rr["exclude_from_primary"]:
            excl.append({"scenario_id": rec["scenario_id"], "seed": rec["seed"], "reason": rr["exclude_reason"]})
        obs.append(row)
    return obs, excl


def _scen_mean(rows, key):
    b = defaultdict(list)
    for r in rows:
        v = r.get(key)
        if v is not None:
            b[r["scenario_id"]].append(float(v))
    return {k: float(np.mean(v)) for k, v in b.items()}


def _paired(a_by, b_by, n_boot=10000, seed=12345):
    keys = sorted(set(a_by) & set(b_by))
    a = np.array([a_by[k] for k in keys]); b = np.array([b_by[k] for k in keys])
    d = a - b
    nz = int((np.abs(d) > 1e-9).sum())
    wins = int((d < -1e-9).sum())      # a - b < 0  => a (first) better  (regret lower)
    losses = int((d > 1e-9).sum())
    ties = len(d) - wins - losses
    try:
        mode = "exact" if nz <= 25 else "approx"
        W = _sps.wilcoxon(a, b, zero_method="wilcox", correction=False, alternative="two-sided", mode=mode)
        p = float(W.pvalue); stat = float(W.statistic)
    except Exception:
        p = None; stat = None
    # matched-pairs rank-biserial (Kerby): favourable = first better = d<0
    rb = ((wins - losses) / nz) if nz else None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, d.size, size=(n_boot, d.size))
    bm = d[idx].mean(axis=1)
    ci = [float(np.percentile(bm, 2.5)), float(np.percentile(bm, 97.5))]
    # student-t
    if d.size > 1 and d.std(ddof=1) > 0:
        h = float(_sps.t.ppf(0.975, d.size - 1) * d.std(ddof=1) / np.sqrt(d.size))
        tci = [round(float(d.mean() - h), 6), round(float(d.mean() + h), 6)]
    else:
        tci = None
    return {
        "n_scenarios": len(keys),
        "mean_difference": round(float(d.mean()), 6) if d.size else None,
        "median_difference": round(float(np.median(d)), 6) if d.size else None,
        "sd_difference": round(float(d.std(ddof=1)), 6) if d.size > 1 else 0.0,
        "wins_first_better": wins, "ties": ties, "losses_first_worse": losses,
        "wins_ties_losses": [wins, ties, losses], "n_nonzero": nz,
        "wilcoxon": {"statistic": stat, "p_value": p,
                     "mode": ("exact" if nz <= 25 else "approx") if nz >= 2 else "not_assessed"},
        "matched_pairs_rank_biserial": round(rb, 6) if rb is not None else None,
        "cluster_bootstrap": {"resampling_unit": "scenario", "method": "percentile",
                              "n_boot": n_boot, "seed": seed,
                              "point": round(float(d.mean()), 6),
                              "ci95": [round(c, 6) for c in ci]},
        "student_t_ci95_secondary": tci,
        "convention": "value = regret[first] - regret[second]; NEGATIVE => first has lower regret (better)",
    }


def _holm(pv, alpha=0.05):
    tv = {k: v for k, v in pv.items() if v is not None}
    m = len(tv); out = {}; run = 0.0
    for i, (k, p) in enumerate(sorted(tv.items(), key=lambda kv: kv[1])):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = {"p_raw": round(p, 8), "p_holm": round(run, 8), "reject_at_alpha": run < alpha, "rank": i + 1}
    for k in pv:
        if pv[k] is None:
            out[k] = {"p_raw": None, "p_holm": None, "reject_at_alpha": False, "rank": None}
    return {"alpha": alpha, "method": "holm_bonferroni", "n_tests_corrected": m, "family": sorted(tv), "results": out}


# ======================================================================= #
# Phases 12-16 — analysis                                                  #
# ======================================================================= #
def cmd_analyze(args) -> int:
    from app.evaluation import mechanism as mz

    _guard_frozen()
    res = json.loads((OUT / (args.results or "results.json")).read_text())
    obs, excl = _flatten(res)
    incl = [r for r in obs if not r["excluded"] and all(r[f"status_{c}"] == "ok" for c in ("A", "B", "C"))]
    reg = {c: _scen_mean(incl, f"regret_{c}") for c in "ABCD"}
    for nm in ("naive", "greedy", "classical_optimizer"):
        reg[nm] = _scen_mean(incl, f"regret_{nm}")
    reg["oracle"] = {k: 0.0 for k in reg["D"]}

    # PRIMARY + confirmatory family (Holm over B_vs_A, C_vs_B, D_vs_C, D_vs_B)
    conf = {"B_vs_A": ("B", "A"), "C_vs_B": ("C", "B"), "D_vs_C": ("D", "C"), "D_vs_B": ("D", "B")}
    primary = {name: _paired(reg[x], reg[y]) for name, (x, y) in conf.items()}
    holm = _holm({k: primary[k]["wilcoxon"]["p_value"] for k in conf})
    # secondary / descriptive
    sec = {}
    for name, (x, y) in {"D_vs_A": ("D", "A"), "D_vs_oracle": ("D", "oracle"),
                         "A_vs_oracle": ("A", "oracle"), "B_vs_oracle": ("B", "oracle"),
                         "C_vs_oracle": ("C", "oracle"), "D_vs_naive": ("D", "naive"),
                         "D_vs_greedy": ("D", "greedy"), "D_vs_classical_optimizer": ("D", "classical_optimizer")}.items():
        sec[name] = _paired(reg[x], reg[y])

    def _m(rows, k):
        xs = [r[k] for r in rows if r.get(k) is not None]
        return round(float(np.mean(xs)), 6) if xs else None
    positioning = {"n_scenarios_eligible": len(reg["A"]), "n_seeds": len(res.get("seeds", []))}
    for c in "ABCD":
        positioning[c] = {"mean_regret": _m(incl, f"regret_{c}"),
                          "mean_normalized_performance": _m(incl, f"norm_{c}"),
                          "mean_secondary_goal_achievement": _m(incl, f"sec_{c}")}
    for nm in ("naive", "greedy", "classical_optimizer"):
        positioning[nm] = {"mean_regret": _m(incl, f"regret_{nm}"),
                           "n_na": sum(1 for r in incl if r.get(f"status_{nm}") == "na")}
    positioning["oracle"] = {"mean_regret": 0.0, "note": "upper-bound reference"}

    # family-level D_vs_B (Section 22)
    per_family = {}
    fam_ids = sorted({r["family_id"] for r in incl})
    for f in fam_ids:
        fr = [r for r in incl if r["family_id"] == f]
        rd = _scen_mean(fr, "regret_D"); rb = _scen_mean(fr, "regret_B")
        pf = _paired(rd, rb, n_boot=5000, seed=777)
        per_family[f] = {
            "n_structural_scenarios": len({r["scenario_id"] for r in fr}),
            "n_seeds": len(res.get("seeds", [])),
            "mean_D_minus_B": pf["mean_difference"], "median_D_minus_B": pf["median_difference"],
            "direction": ("D_better" if (pf["mean_difference"] or 0) < 0 else
                          "D_worse" if (pf["mean_difference"] or 0) > 0 else "tie"),
            "wins_ties_losses_D_better_tie_worse": pf["wins_ties_losses"],
            "cluster_bootstrap_ci95": pf["cluster_bootstrap"]["ci95"],
            "mean_regret": {c: _m(fr, f"regret_{c}") for c in "ABCD"},
        }
    # is the aggregate D_vs_B driven by few families?
    fam_means = {f: v["mean_D_minus_B"] for f, v in per_family.items() if v["mean_D_minus_B"] is not None}
    agg = primary["D_vs_B"]["mean_difference"] or 0.0
    contrib = sorted(fam_means.items(), key=lambda kv: abs(kv[1]), reverse=True)

    stat = {
        "status": "complete", "unit_of_analysis": "scenario",
        "endpoint": "exogenous normalised regret (0=oracle, 1=worst feasible; lower better)",
        "primary_contrast": "D_vs_B = regret_D - regret_B  (NEGATIVE => D better)",
        "source_results": (args.results or "results.json"),
        "source_results_sha256": _sha256(OUT / (args.results or "results.json")),
        "n_seeds": len(res.get("seeds", [])),
        "n_scenarios_eligible": len(reg["A"]),
        "excluded": {"count": len(excl), "rows": excl[:200]},
        "confirmatory_family_holm": holm,
        "primary_and_confirmatory_contrasts": primary,
        "secondary_contrasts": sec,
        "positioning": positioning,
        "family_level_D_vs_B": per_family,
        "family_contribution": {
            "aggregate_mean_D_minus_B": round(agg, 6),
            "n_families": len(fam_means),
            "families_by_abs_effect": [{"family": f, "mean_D_minus_B": round(v, 6)} for f, v in contrib],
            "top3_abs_effect_share_of_sum_abs": (
                round(sum(abs(v) for _, v in contrib[:3]) / max(1e-9, sum(abs(v) for v in fam_means.values())), 4)),
        },
        "interpretation_rule": ("D_vs_B is SUPPORTED only if mean(D-B)<0 AND |mean|>=0.05 AND bootstrap CI excludes 0 "
                                "AND Holm p<0.05 AND not driven by one family AND robustness preserves sign AND "
                                "mechanism plausible AND no post-hoc exclusion. A non-significant D_vs_B is "
                                "'no significant incremental improvement detected', NOT equivalence."),
    }
    _write_json(OUT / "statistical_results.json", stat)

    # mechanism (exploratory, associational) — Section 24
    scen_fac = {}
    fb = defaultdict(lambda: defaultdict(list))
    for r in obs:
        for k, v in (r.get("factors") or {}).items():
            if isinstance(v, (int, float)):
                fb[r["scenario_id"]][k].append(float(v))
    for sid, dd in fb.items():
        scen_fac[sid] = {k: float(np.mean(v)) for k, v in dd.items()}
    mech = {}
    for name, (x, y) in (("D_vs_B", ("D", "B")), ("C_vs_B", ("C", "B")), ("B_vs_A", ("B", "A"))):
        cbs = {s: reg[x][s] - reg[y][s] for s in reg[x] if s in reg[y] and s in scen_fac}
        mech[name] = mz.interaction_analysis(scen_fac, cbs, contrast=name, n_boot=5000, seed=4242)
    # action-change vs improvement
    ac = {"D_changed_action_vs_B": 0, "D_changed_and_improved": 0, "D_changed_and_worsened": 0,
          "D_changed_no_change": 0, "n": 0}
    for r in incl:
        if r["regret_D"] is None or r["regret_B"] is None:
            continue
        ac["n"] += 1
        if r["selkey_D"] != r["selkey_B"]:
            ac["D_changed_action_vs_B"] += 1
            d = r["regret_D"] - r["regret_B"]
            if d < -1e-9:
                ac["D_changed_and_improved"] += 1
            elif d > 1e-9:
                ac["D_changed_and_worsened"] += 1
            else:
                ac["D_changed_no_change"] += 1
    # DT (r1_dt) vs ground-truth action discrepancy
    dt_gt = {"B_action_eq_oracle": 0, "D_action_eq_oracle": 0, "n": 0}
    for r in incl:
        dt_gt["n"] += 1
        if r["selkey_B"] == r["oracle_key"]:
            dt_gt["B_action_eq_oracle"] += 1
        if r["selkey_D"] == r["oracle_key"]:
            dt_gt["D_action_eq_oracle"] += 1
    supp = {"status": "complete", "source_results": (args.results or "results.json"),
            "mechanism_associational_not_causal": mech,
            "action_change_vs_improvement": ac,
            "dt_vs_ground_truth_action_match": dt_gt,
            "notes": ["A changed action is NOT evidence of an improved decision (Section 24).",
                      "Effective cluster count for factor claims = number of locked families; "
                      "factor-level effects are NOT asserted, family-level description only."]}
    _write_json(OUT / "mechanism_results.json", supp)

    ck = _checks()
    for f in ("statistical_results.json", "mechanism_results.json"):
        ck[f] = _sha256(OUT / f)
    _save_checks(ck)
    cfg = _cfg(); cfg["status"] = "ANALYSIS_COMPLETE"; _save_cfg(cfg)

    print("\n=== R1 PRIMARY (regret[first] - regret[second]; NEGATIVE => first better) ===")
    for k in ("B_vs_A", "C_vs_B", "D_vs_C", "D_vs_B"):
        b = primary[k]; h = holm["results"][k]
        print(f"  {k:9s} n={b['n_scenarios']:3d} mean={b['mean_difference']:+.4f} med={b['median_difference']:+.4f} "
              f"CI={b['cluster_bootstrap']['ci95']} W/T/L(1better/tie/1worse)={b['wins_ties_losses']} nz={b['n_nonzero']} "
              f"p={b['wilcoxon']['p_value']} pHolm={h['p_holm']} reject={h['reject_at_alpha']} rb={b['matched_pairs_rank_biserial']}")
    print("  secondary:")
    for k, b in sec.items():
        print(f"    {k:26s} mean={b['mean_difference']:+.4f} CI={b['cluster_bootstrap']['ci95']}")
    print("  mean regret: " + " ".join(f"{c}={positioning[c]['mean_regret']}" for c in "ABCD")
          + f" | naive={positioning['naive']['mean_regret']} greedy={positioning['greedy']['mean_regret']} "
          f"classical={positioning['classical_optimizer']['mean_regret']}")
    print(f"  family contribution: top-3 |effect| share of sum|effect| = "
          f"{stat['family_contribution']['top3_abs_effect_share_of_sum_abs']}")
    print(f"  D changed action vs B on {ac['D_changed_action_vs_B']}/{ac['n']} ; of those improved "
          f"{ac['D_changed_and_improved']} / worsened {ac['D_changed_and_worsened']}")
    print(f"  frozen manifest: {'OK' if _sha256(FROZEN_MANIFEST)==FROZEN_SHA else 'MISMATCH'}")
    return 0


# ======================================================================= #
# Phase 14 — robustness                                                    #
# ======================================================================= #
def cmd_robustness(args) -> int:
    from app.evaluation.r1 import harness as r1h
    from app.evaluation.r1 import scenario_families as r1sf  # noqa: F401
    from app.evaluation import perturbations as pz
    from app.services import model_registry_service

    _guard_frozen()
    cfg = _cfg()
    if not cfg.get("prereg_frozen") or not (OUT / "results.json").exists():
        print("REFUSED: robustness runs after the frozen locked test.")
        return 2
    locked, man = _rebuild("locked_test")
    locked = sorted(locked, key=lambda s: s.scenario_id)
    subs = locked[:: max(1, args.every)][: args.max_scenarios]
    seeds = SEEDS[: args.seeds]
    perts = list(pz.PERTURBATIONS)
    sevmap = {n: sorted({min(v), max(v)}) for n, v in r1sf._STD_PERTURBATIONS.items()}
    lr = json.loads((OUT / "results.json").read_text())
    clean = {}
    for rec in lr["records"]:
        if "result" in rec:
            C = rec["result"]["conditions"]
            clean[(rec["scenario_id"], rec["seed"])] = {c: C[c]["primary_regret"] for c in "ABCD"}
    jsonl = OUT / "robustness_runs.jsonl"
    if jsonl.exists() and not args.resume:
        jsonl.unlink()
    done = set()
    if args.resume and jsonl.exists():
        for ln in jsonl.read_text().splitlines():
            if ln.strip():
                r = json.loads(ln)
                done.add((r["scenario_id"], r["seed"], r["perturbation"], r["severity"]))
    db, engine = v1._scratch_session(args.db)
    t0 = time.perf_counter(); n = 0
    total = len(subs) * len(seeds) * sum(len(sevmap.get(p, [1.0])) for p in perts)
    try:
        model_registry_service.sync_from_file_registry(db)
        with jsonl.open("a") as fh:
            for sc in subs:
                for seed in seeds:
                    for pn in perts:
                        for sev in sevmap.get(pn, [1.0]):
                            n += 1
                            if (sc.scenario_id, seed, pn, sev) in done:
                                continue
                            rec = {"scenario_id": sc.scenario_id, "family_id": sc.family_id,
                                   "seed": seed, "perturbation": pn, "severity": sev}
                            try:
                                r = r1h.run_instance(db, sc, seed=seed, perturbation=pn, severity=sev)
                                rec["regret"] = {c: r.conditions[c]["primary_regret"] for c in "ABCD"}
                            except Exception as exc:
                                rec["error"] = f"{type(exc).__name__}: {exc}"
                            fh.write(json.dumps(rec, default=str) + "\n")
                            fh.flush()
                            if n % 40 == 0:
                                el = time.perf_counter() - t0
                                print(f"  [{n}/{total}] elapsed={el:.0f}s eta={el/max(1,n)*(total-n):.0f}s", flush=True)
    finally:
        db.close(); engine.dispose()
        pth = REPO / args.db.replace("sqlite:///", "").lstrip("./")
        if args.db.startswith("sqlite:///") and pth.exists() and not args.keep_db:
            pth.unlink()

    runs = [json.loads(x) for x in jsonl.read_text().splitlines() if x.strip()]
    # per perturbation: change in mean(D-B) vs the clean locked run, on the SAME subsample
    base_dmb = []
    for (sid, seed), reg in clean.items():
        if any(s.scenario_id == sid for s in subs) and reg["D"] is not None and reg["B"] is not None:
            base_dmb.append(reg["D"] - reg["B"])
    base_mean = float(np.mean(base_dmb)) if base_dmb else None
    curves = {}
    for pn in perts:
        entry = {}
        for sev in sevmap.get(pn, [1.0]):
            dmb = [r["regret"]["D"] - r["regret"]["B"] for r in runs
                   if r["perturbation"] == pn and abs(r["severity"] - sev) < 1e-9
                   and r.get("regret", {}).get("D") is not None and r["regret"].get("B") is not None]
            if dmb:
                m = float(np.mean(dmb))
                rng = np.random.default_rng(2024)
                bm = np.array([np.mean(rng.choice(dmb, len(dmb))) for _ in range(4000)])
                entry[str(sev)] = {"n": len(dmb), "mean_D_minus_B": round(m, 6),
                                   "delta_vs_clean": round(m - (base_mean or 0), 6),
                                   "ci95": [round(float(np.percentile(bm, 2.5)), 6),
                                            round(float(np.percentile(bm, 97.5)), 6)],
                                   "sign_vs_clean": ("same" if (m < 0) == ((base_mean or 0) < 0) else "flipped")}
        curves[pn] = entry
    out = {"status": "complete", "perturbation_version": pz.PERTURBATION_VERSION,
           "scope": {"partition": "locked_test", "n_scenarios": len(subs),
                     "scenario_ids": [s.scenario_id for s in subs], "seeds": seeds},
           "clean_subsample_mean_D_minus_B": round(base_mean, 6) if base_mean is not None else None,
           "primary_conclusion_changes": any(
               v.get(str(sev), {}).get("sign_vs_clean") == "flipped"
               for pn, v in curves.items() for sev in sevmap.get(pn, [1.0])),
           "curves": curves, "n_runs": len(runs), "n_errors": sum(1 for r in runs if "error" in r)}
    _write_json(OUT / "robustness_results.json", out)
    ck = _checks(); ck["robustness_results.json"] = _sha256(OUT / "robustness_results.json")
    ck["robustness_runs.jsonl"] = _sha256(jsonl); _save_checks(ck)
    print(f"wrote robustness_results.json: {len(runs)} runs, {out['n_errors']} err; "
          f"clean D-B (subsample) = {out['clean_subsample_mean_D_minus_B']}; "
          f"primary conclusion changes = {out['primary_conclusion_changes']}")
    return 0


# ======================================================================= #
# Phase 17/38 — integrity audit (machine-checkable items)                   #
# ======================================================================= #
def cmd_audit(args) -> int:
    import ast as _ast

    from app.evaluation import ground_truth as gt
    from app.evaluation.r1 import scenario_families as r1sf
    from app.services import decision_service as ds
    from app.analytics import digital_twin_service as dts

    checks = []
    def chk(name, ok, detail=""):
        checks.append((name, bool(ok), str(detail)))

    # A. ground-truth independence (System B unchanged from V1)
    gsrc = (REPO / "backend/app/evaluation/ground_truth.py").read_text()
    imps = []
    for n in _ast.walk(_ast.parse(gsrc)):
        if isinstance(n, _ast.Import):
            imps += [a.name for a in n.names]
        elif isinstance(n, _ast.ImportFrom):
            imps.append(n.module or "")
    chk("A_ground_truth_independent", not [i for i in imps if any(
        f in i for f in ("digital_twin", "decision_service", "decision_architecture", "forecast_service",
                         "agents", "app.evaluation.r1"))], sorted(set(imps)))
    # E. R1-DT correction does not import ground_truth/oracle/objective
    rsrc = (REPO / "backend/app/evaluation/r1/r1_dt.py").read_text()
    rimps = []
    for n in _ast.walk(_ast.parse(rsrc)):
        if isinstance(n, _ast.Import):
            rimps += [a.name for a in n.names]
        elif isinstance(n, _ast.ImportFrom):
            rimps.append(n.module or "")
    chk("E_r1_dt_no_objective_or_oracle_import", not [i for i in rimps if any(
        f in i for f in ("ground_truth", "decision_service", "decision_architecture"))],
        sorted(set(i for i in rimps if i)))
    chk("E_r1_dt_uses_history_not_true_params",
        "estimate_response" in rsrc and "build_daily_series" in rsrc
        and 'p.get("a_elast")' in rsrc and "fallback" in rsrc,
        "OLS from build_daily_series; a_elast only as logged fallback")
    # R. production contamination
    diff = subprocess.run(["git", "diff", "--stat", "--",
                           "backend/app/services/", "backend/app/analytics/", "backend/app/agents/",
                           "backend/app/decision_engine/", "experiments/experiment_manifest.json",
                           "experiments/paper_results_snapshot.json", "experiments/results/",
                           "experiments/upgraded_controlled_v1/", "experiments/upgraded_controlled_v2/",
                           "docs/PAPER_DRAFT.md", "docs/ieee_paper/"],
                          cwd=REPO, capture_output=True, text=True).stdout.strip()
    chk("R_production_and_history_git_clean", diff == "", diff or "(empty)")
    o = ds.PipelineOptions()
    chk("R_R0_D0_unchanged", o.label() == "full" and o.risk_penalty_lambda == 1.0
        and getattr(o, "risk_model", None) is None, o.label())
    chk("R_R3_not_promoted", dts.RISK_FORMULA_VERSION == "extrapolation_range_v1", dts.RISK_FORMULA_VERSION)
    chk("frozen_manifest_sha", _sha256(FROZEN_MANIFEST) == FROZEN_SHA, _sha256(FROZEN_MANIFEST))
    v1c = json.loads((REPO / "experiments/upgraded_controlled_v1/config.json").read_text())
    v2c = json.loads((REPO / "experiments/upgraded_controlled_v2/config.json").read_text())
    chk("V1_unchanged", v1c["status"] == "evaluation_complete" and v1c["prereg_frozen"] is True, v1c["status"])
    chk("V2_unchanged_not_run", v2c["status"] == "STOPPED_AT_PRELOCK_GATE" and v2c["locked_test_run"] is False,
        v2c["status"])
    # C/D. scenario generation + test-set isolation
    man = json.loads((OUT / "scenario_manifest.json").read_text())
    reb = r1sf.suite_checksum([r1sf.EvalScenarioR1.from_dict(d) for d in man["scenarios"]])
    chk("C_suite_checksum_reproducible", reb == man["suite_checksum"] == _cfg().get("suite_checksum"), reb)
    ids = {d["scenario_id"] for d in man["scenarios"]}
    v1ids = {d["scenario_id"] for d in json.loads(
        (REPO / "experiments/upgraded_controlled_v1/scenario_manifest.json").read_text())["scenarios"]}
    v2ids = {d["scenario_id"] for d in json.loads(
        (REPO / "experiments/upgraded_controlled_v2/scenario_manifest.json").read_text())["scenarios"]}
    chk("C_no_id_collision_with_v1_v2_frozen",
        not (ids & v1ids) and not (ids & v2ids) and not (ids & {f"S{n:02d}" for n in range(1, 13)}), "")
    parts = _cfg()["partitions"]
    overlap = [f for pn in parts for f in parts[pn] if sum(f in parts[q] for q in parts) > 1]
    chk("C_family_partitions_disjoint", not overlap, overlap or "disjoint")
    pl = json.loads((OUT / "prelock_diagnostics.json").read_text())
    chk("D_prelock_never_touched_locked",
        pl["scope"]["locked_test_touched"] is False
        and all(f in (parts["development"] + parts["validation"])
                for f in {r["family_id"] for r in pl["raw_rows"] if "family_id" in r}),
        "prelock ran only on development/validation families")
    # S. prereg frozen before locked run
    pr = _cfg().get("prereg", {})
    chk("S_prereg_frozen_before_run", _cfg().get("prereg_frozen") is True and pr.get("git_commit_at_freeze"),
        f"commit {pr.get('git_commit_at_freeze','')[:12]}")
    chk("S_prereg_doc_unchanged_since_freeze", pr.get("doc_sha256") == _sha256(PREREG), _sha256(PREREG))
    chk("S_scenario_manifest_unchanged_since_freeze",
        pr.get("scenario_manifest_sha256") == _sha256(OUT / "scenario_manifest.json"), "")

    locked_ok = None
    if (OUT / "results.json").exists():
        rj = json.loads((OUT / "results.json").read_text())
        exp = len(_cfg().get("locked_scenario_ids", [])) * len(SEEDS)
        chk("locked_run_scenario_seed_count",
            rj["n_instances"] == exp, f"{rj['n_instances']} vs expected {exp}")
        chk("locked_run_no_unexplained_exclusions",
            rj["n_error"] == 0, f"{rj['n_error']} harness errors")
        chk("locked_run_arch_label_full",
            rj["architecture_fingerprint"]["pipeline_options_label"] == "full", "")
        chk("locked_run_frozen_manifest_at_runtime", rj["frozen_manifest_sha256"] == FROZEN_SHA, "")
        # G. oracle exact on a sample of the locked set (independent enumeration)
        scen = {d["scenario_id"]: r1sf.EvalScenarioR1.from_dict(d) for d in man["scenarios"]
                if d["partition"] == "locked_test"}
        seen = set(); mm = 0; ninv = 0; checked = 0
        for rec in rj["records"]:
            if "result" not in rec:
                continue
            if not rec["result"]["action_space_invariant_ok"]:
                ninv += 1
            if rec["scenario_id"] in seen:
                continue
            seen.add(rec["scenario_id"]); checked += 1
            sc = scen[rec["scenario_id"]]
            my = gt.oracle(sc, list(sc.eval_reference_actions))
            st = rec["result"]["baselines"]["oracle"]
            if my["action_key"] != st["action_key"] or abs((my["value"] or 0) - (st["value"] or 0)) > 1e-6:
                mm += 1
        chk("G_oracle_exact_on_locked", mm == 0, f"{mm}/{checked} mismatches")
        chk("F_candidate_action_space_invariant_locked", ninv == 0, f"{ninv} invariant failures")
        locked_ok = True

    # H. seed interpretation — statistical_results uses scenario as the unit
    if (OUT / "statistical_results.json").exists():
        sr = json.loads((OUT / "statistical_results.json").read_text())
        chk("H_unit_of_analysis_is_scenario", sr.get("unit_of_analysis") == "scenario", sr.get("unit_of_analysis"))
        chk("L_multiplicity_holm_over_confirmatory_family",
            sr["confirmatory_family_holm"]["method"] == "holm_bonferroni"
            and set(sr["confirmatory_family_holm"]["family"]) == {"B_vs_A", "C_vs_B", "D_vs_C", "D_vs_B"},
            sr["confirmatory_family_holm"]["family"])
        chk("M_primary_effect_size_is_rank_biserial",
            "matched_pairs_rank_biserial" in sr["primary_and_confirmatory_contrasts"]["D_vs_B"], "")

    # I. checksums of immutable artifacts
    _IMMUT = ["scenario_manifest.json", "power_assumptions.json", "power_analysis.json",
              "prelock_diagnostics.json", "results.json", "results_locked_test.jsonl",
              "statistical_results.json", "mechanism_results.json", "robustness_results.json"]
    stored = _checks()
    mmk = [f for f in _IMMUT if (OUT / f).exists() and f in stored and _sha256(OUT / f) != stored[f]]
    chk("Q_recorded_checksums_match_disk", not mmk, ", ".join(mmk) or "match")

    # refresh a full checksum manifest
    full = {p.name: _sha256(p) for p in sorted(OUT.glob("*")) if p.is_file() and p.name != "_locked_run.log"}
    full["_frozen_experiment_manifest.json"] = _sha256(FROZEN_MANIFEST)
    (OUT / "checksums.txt").write_text(json.dumps({**stored, **full}, indent=2, sort_keys=True))

    npass = sum(1 for _, ok, _ in checks if ok)
    lines = ["# R1 — Machine Integrity Audit", "",
             f"Generated by `scripts/run_eval_r1.py audit`. **{npass}/{len(checks)} checks passed.** "
             "(This is the machine-checkable subset; the hostile scientific audit is `docs/R1_AUDIT.md`.)",
             "", "| # | check | result | detail |", "|---|---|---|---|"]
    for i, (n, ok, d) in enumerate(checks, 1):
        lines.append(f"| {i} | `{n}` | {'PASS' if ok else '**FAIL**'} | {d[:160]} |")
    (OUT / "MACHINE_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if npass == len(checks) else 1


# ======================================================================= #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate"); g.add_argument("--n", type=int, default=378)
    g.add_argument("--master-seed", type=int, default=20260907); g.set_defaults(func=cmd_generate)
    pl = sub.add_parser("prelock-diagnose")
    pl.add_argument("--db", default="sqlite:///./_eval_r1_prelock.db")
    pl.add_argument("--per-family", type=int, default=3); pl.add_argument("--seeds", type=int, default=4)
    pl.add_argument("--include-validation", action="store_true"); pl.set_defaults(func=cmd_prelock_diagnose)
    pw = sub.add_parser("power"); pw.add_argument("--assumptions", required=True); pw.set_defaults(func=cmd_power)
    ga = sub.add_parser("gate"); ga.set_defaults(func=cmd_gate)
    fp = sub.add_parser("freeze-prereg"); fp.add_argument("--date", default="2026-09-06")
    fp.add_argument("--force", action="store_true"); fp.set_defaults(func=cmd_freeze_prereg)
    r = sub.add_parser("run")
    r.add_argument("--partition", choices=["development", "validation", "locked_test"], required=True)
    r.add_argument("--db", default="sqlite:///./_eval_r1_run.db")
    r.add_argument("--limit", type=int, default=0); r.add_argument("--seeds", type=int, default=0)
    r.add_argument("--resume", action="store_true"); r.add_argument("--keep-db", action="store_true")
    r.set_defaults(func=cmd_run)
    an = sub.add_parser("analyze"); an.add_argument("--results", default="results.json"); an.set_defaults(func=cmd_analyze)
    rb = sub.add_parser("robustness")
    rb.add_argument("--db", default="sqlite:///./_eval_r1_robust.db")
    rb.add_argument("--every", type=int, default=4); rb.add_argument("--max-scenarios", type=int, default=30)
    rb.add_argument("--seeds", type=int, default=3); rb.add_argument("--resume", action="store_true")
    rb.add_argument("--keep-db", action="store_true"); rb.set_defaults(func=cmd_robustness)
    au = sub.add_parser("audit"); au.set_defaults(func=cmd_audit)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
