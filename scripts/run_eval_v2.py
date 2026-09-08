#!/usr/bin/env python
"""Driver for the upgraded controlled evaluation **V2** (action-responsive
environment). Separate, independently versioned; writes ONLY under
``experiments/upgraded_controlled_v2/``.

V2 reuses the audit-verified V1 apparatus unchanged: ``ground_truth.py``
(System B objective + oracle + baselines), ``harness.py`` (fairness logic; V2
supplies ``realise_history=scenario_families_v2.realise_history`` via the single
optional injection point), ``stats.py``, ``perturbations.py``, ``mechanism.py``.
The ONLY new environment code is ``scenario_families_v2.py`` (System A).

Subcommands:
  generate          build the V2 suite + stratified family partition
  prelock-diagnose  Phases 4 & 16 — development/validation diagnostics
                    (B action distribution, response identifiability, oracle,
                    candidate identity, info-set); NEVER touches locked_test
  power             simulation power from the DESIGN-STAGE pilot variance
  freeze-prereg     seal docs/UPGRADED_EVALUATION_V2_PREREGISTRATION.md
  run               locked-test run (once)
  analyze           Phases 18 — statistics / baselines / agents / mechanism / failures
  robustness        Phase 13 — descriptive robustness on a locked subsample
  audit             Phase 20 — integrity audit
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats as _sps

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "scripts"))

import run_upgraded_eval as v1  # noqa: E402  (pure helpers: _sha256, _write_json, _scratch_session, ...)

OUT = REPO / "experiments" / "upgraded_controlled_v2"
PREREG = REPO / "docs" / "UPGRADED_EVALUATION_V2_PREREGISTRATION.md"
DESIGN = REPO / "docs" / "UPGRADED_EVALUATION_V2_DESIGN.md"
FROZEN_MANIFEST = REPO / "experiments" / "experiment_manifest.json"
FROZEN_SHA = v1.FROZEN_MANIFEST_SHA256
SEEDS = v1.SEEDS                                   # 20260906..20260915 (10)
_sha256, _write_json = v1._sha256, v1._write_json


def _cfg() -> dict:
    p = OUT / "config.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _save_cfg(c: dict) -> None:
    _write_json(OUT / "config.json", c)


def _checks() -> dict:
    p = OUT / "checksums.txt"
    return json.loads(p.read_text()) if p.exists() else {}


def _save_checks(d: dict) -> None:
    _write_json(OUT / "checksums.txt", d)


# ======================================================================= #
def cmd_generate(args) -> int:
    from app.evaluation import scenario_families_v2 as v2

    scen = v2.generate_suite(args.n, args.master_seed)
    parts = v2.partition_families(args.master_seed)
    v2.assign_partitions(scen, parts)
    man = {
        "evaluation_layer_version": "upgraded_controlled_v2",
        "generator_version": v2.GENERATOR_VERSION,
        "env_version": v2.ENV_VERSION,
        "master_seed": args.master_seed,
        "n_scenarios": len(scen),
        "n_families": len(v2.FAMILY_IDS_V2),
        "family_ids": v2.FAMILY_IDS_V2,
        "partitions": parts,
        "partition_scheme": "stratified round-robin over structural super-groups, pattern [dev,dev,val,locked]",
        "suite_checksum": v2.suite_checksum(scen),
        "action_space_policy": "production_candidate_templates (verified per instance by the harness)",
        "scenarios": [s.to_dict() for s in scen],
        "status": "generated",
    }
    _write_json(OUT / "scenario_manifest.json", man)
    cfg = _cfg()
    cfg.update({
        "evaluation_layer_version": "upgraded_controlled_v2",
        "generator_version": v2.GENERATOR_VERSION, "env_version": v2.ENV_VERSION,
        "master_seed": args.master_seed, "n_scenarios": len(scen),
        "n_families": len(v2.FAMILY_IDS_V2), "partitions": parts,
        "suite_checksum": man["suite_checksum"],
        "locked_test_family_checksum": hashlib.sha256(
            json.dumps(sorted(parts["locked_test"]), sort_keys=True).encode()).hexdigest(),
        "prereg_frozen": cfg.get("prereg_frozen", False),
        "frozen_manifest_sha256": FROZEN_SHA, "status": "generated",
        "notes": ["Action-responsive V2 environment (System A power-law demand response).",
                  "System B objective = ground_truth.exogenous_objective_v1, UNCHANGED from V1.",
                  "V1 (upgraded_controlled_v1) is frozen and untouched; the two are never pooled."],
    })
    _save_cfg(cfg)
    _save_checks({"scenario_manifest.json": _sha256(OUT / "scenario_manifest.json")})
    print(f"V2 suite: {len(scen)} scenarios, {len(v2.FAMILY_IDS_V2)} families")
    print(f"  suite_checksum: {man['suite_checksum']}")
    print(f"  locked_test families: {parts['locked_test']}")
    print(f"  development: {len(parts['development'])} fam, validation: {len(parts['validation'])} fam")
    return 0


# ======================================================================= #
def _rebuild(partition: str | None = None):
    from app.evaluation import scenario_families_v2 as v2
    man = json.loads((OUT / "scenario_manifest.json").read_text())
    out = []
    for d in man["scenarios"]:
        if partition is None or d["partition"] == partition:
            out.append(v2.EvalScenarioV2.from_dict(d))
    return out, man


def cmd_prelock_diagnose(args) -> int:
    """Phases 4 + 16. Development (+ validation) ONLY. Never locked_test."""
    from app.evaluation import ground_truth as gt
    from app.evaluation import harness as hz
    from app.evaluation import scenario_families_v2 as v2
    from app.services import model_registry_service

    assert _sha256(FROZEN_MANIFEST) == FROZEN_SHA, "frozen manifest changed"
    dev, man = _rebuild("development")
    val, _ = _rebuild("validation")
    pool = dev + (val if args.include_validation else [])
    # cap for a tractable diagnostic
    if args.per_family:
        by = defaultdict(list)
        for s in pool:
            by[s.family_id].append(s)
        pool = [s for ss in by.values() for s in ss[: args.per_family]]
    seeds = SEEDS[: args.seeds]
    print(f"pre-lock diagnostic: {len(pool)} scenarios x {len(seeds)} seeds "
          f"(partitions: development{'+validation' if args.include_validation else ''}; "
          f"locked_test NEVER touched)")

    db, engine = v1._scratch_session(args.db)
    rows = []
    t0 = time.perf_counter()
    try:
        model_registry_service.sync_from_file_registry(db)
        for k, sc in enumerate(pool, 1):
            for seed in seeds:
                try:
                    r = hz.run_instance(db, sc, seed=seed, realise_history=v2.realise_history)
                    C = r.conditions
                    rows.append({
                        "scenario_id": sc.scenario_id, "family_id": sc.family_id,
                        "partition": sc.partition, "seed": seed,
                        "a_elast": sc.params["a_elast"], "a_mkt": sc.params["a_mkt"],
                        "eps_B": sc.params["price_elasticity"], "objective": sc.objective["kpi"],
                        "invariant_ok": r.action_space_invariant_ok,
                        "exclude": r.exclude_from_primary, "exclude_reason": r.exclude_reason,
                        "B_key": C["B"]["selected_action_key"], "C_key": C["C"]["selected_action_key"],
                        "D_key": C["D"]["selected_action_key"], "A_key": C["A"]["selected_action_key"],
                        "D_status": C["D"]["status"],
                        "regret": {c: C[c]["primary_regret"] for c in "ABCD"},
                        "B_dt_projection": C["B"]["dt_projection"],
                        "oracle_key": r.baselines["oracle"]["action_key"],
                        "oracle_value": r.baselines["oracle"]["value"],
                        "oracle_worst": r.baselines["oracle"]["worst_value"],
                        "n_feasible": r.baselines["oracle"]["n_feasible"],
                        "declared_count": r.action_space_detail["declared_count"],
                        "resolved_count": r.action_space_detail["resolved_count"],
                    })
                except Exception as exc:
                    import traceback
                    rows.append({"scenario_id": sc.scenario_id, "seed": seed,
                                 "error": f"{type(exc).__name__}: {exc}", "tb": traceback.format_exc()})
            if k % 10 == 0:
                el = time.perf_counter() - t0
                print(f"  [{k}/{len(pool)}] elapsed={el:.0f}s")
    finally:
        db.close(); engine.dispose()
        p = REPO / args.db.replace("sqlite:///", "").lstrip("./")
        if args.db.startswith("sqlite:///") and p.exists():
            p.unlink()

    ok = [r for r in rows if "error" not in r]

    # ---- B non-degeneracy (Phase 4) --------------------------------------
    b_keys = [r["B_key"] for r in ok]
    b_by_fam = defaultdict(lambda: defaultdict(int))
    for r in ok:
        b_by_fam[r["family_id"]][r["B_key"]] += 1
    from collections import Counter
    b_dist = Counter(b_keys)
    # relationship between a_elast and B pick (does B cut price when demand is elastic?)
    def _price_pct(k):
        if not k or k == "noop":
            return 0.0
        tot = 0.0
        for part in k.split("|"):
            if part.startswith("price_change="):
                tot += float(part.split("=")[1])
        return tot
    ela = np.array([r["a_elast"] for r in ok]); bpp = np.array([_price_pct(r["B_key"]) for r in ok])
    corr = float(np.corrcoef(ela, bpp)[0, 1]) if ela.std() > 0 and bpp.std() > 0 else None

    # ---- response identifiability (independent of the pipeline) ---------
    ident = []
    for sc in pool[: min(60, len(pool))]:
        h = v2.realise_history(sc, sc.seed)
        lp = np.log(np.asarray(h["price"])); lu = np.log(np.asarray(h["units"]))
        lsp = np.log(np.asarray(h["marketing_spend"]))
        X = np.column_stack([np.ones_like(lp), lp - lp.mean(), lsp - lsp.mean()])
        beta, *_ = np.linalg.lstsq(X, lu, rcond=None)
        ident.append({"family": sc.family_id, "recovered_elast": round(float(beta[1]), 4),
                      "true_a_elast": sc.params["a_elast"],
                      "abs_err": round(abs(float(beta[1]) - sc.params["a_elast"]), 4),
                      "logprice_sd": round(float(lp.std()), 4)})
    ident_err = [x["abs_err"] for x in ident]
    logp_sd = [x["logprice_sd"] for x in ident]

    # ---- oracle correctness (independent enumeration) ------------------
    orc_mismatch = 0
    for sc in pool:
        my = gt.oracle(sc, list(sc.eval_reference_actions))
        st = next((r for r in ok if r["scenario_id"] == sc.scenario_id), None)
        if st and (my["action_key"] != st["oracle_key"]
                   or abs((my["value"] or 0) - (st["oracle_value"] or 0)) > 1e-6):
            orc_mismatch += 1

    # ---- candidate identity & info-set -------------------------------
    inv_fail = [r["scenario_id"] for r in ok if not r["invariant_ok"]]
    decl_res = Counter((r["declared_count"], r["resolved_count"]) for r in ok)

    # ---- DT projection variability (is B's landscape flat?) ----------
    dtvar = []
    for r in ok:
        pr = r.get("B_dt_projection")  # only the selected action's projection is stored; use regret spread instead
    b_regret_by_fam = defaultdict(list)
    for r in ok:
        if r["regret"]["B"] is not None:
            b_regret_by_fam[r["family_id"]].append(r["regret"]["B"])

    diag = {
        "status": "complete",
        "generator_version": v2.GENERATOR_VERSION, "env_version": v2.ENV_VERSION,
        "scope": {"partitions": ["development"] + (["validation"] if args.include_validation else []),
                  "n_scenarios": len(pool), "seeds": seeds, "locked_test_touched": False},
        "n_instances": len(rows), "n_ok": len(ok), "n_error": len(rows) - len(ok),
        "B_non_degeneracy": {
            "unique_B_actions": len(b_dist),
            "B_action_distribution": dict(b_dist),
            "B_by_family": {f: dict(d) for f, d in b_by_fam.items()},
            "corr_a_elast_vs_B_price_pct": corr,
            "interpretation": ("B varies with the scenario and its price move tracks true elasticity"
                               if (len(b_dist) >= 4 and (corr is not None and corr > 0.15))
                               else "B is (near-)constant OR does not track elasticity — DOCUMENT as a finding"),
            "verdict_non_degenerate": bool(len(b_dist) >= 4),
        },
        "response_identifiability": {
            "n_checked": len(ident),
            "median_abs_elasticity_recovery_error": round(float(np.median(ident_err)), 4),
            "mean_abs_elasticity_recovery_error": round(float(np.mean(ident_err)), 4),
            "median_logprice_sd": round(float(np.median(logp_sd)), 4),
            "per_scenario": ident[:40],
            "verdict_identifiable": bool(np.median(ident_err) < 0.6 and np.median(logp_sd) > 0.03),
        },
        "oracle_check": {"n_scenarios": len(pool), "mismatches_vs_independent_enumeration": orc_mismatch,
                         "verdict_correct": orc_mismatch == 0},
        "candidate_identity": {"invariant_failures": inv_fail,
                               "declared_resolved_pairs": {f"{k[0]}/{k[1]}": v for k, v in decl_res.items()},
                               "verdict_identical": len(inv_fail) == 0},
        "D_status_distribution": dict(Counter(r["D_status"] for r in ok)),
        "exclusions": dict(Counter(r["exclude_reason"] for r in ok if r["exclude"])),
        "B_regret_by_family_mean": {f: round(float(np.mean(v)), 4) for f, v in b_regret_by_fam.items()},
        "frozen_manifest_sha256_after": _sha256(FROZEN_MANIFEST),
        "raw_rows": rows,
    }
    _write_json(OUT / "prelock_diagnostics.json", diag)
    ck = _checks(); ck["prelock_diagnostics.json"] = _sha256(OUT / "prelock_diagnostics.json"); _save_checks(ck)

    print("\n=== PRE-LOCK DIAGNOSTIC SUMMARY ===")
    for key in ("B_non_degeneracy", "response_identifiability", "oracle_check", "candidate_identity"):
        d = diag[key]
        print(f"  {key}: " + json.dumps({k: v for k, v in d.items() if not isinstance(v, (list, dict))
                                         or k.startswith("verdict") or k == "B_action_distribution"}, default=str)[:400])
    gate = (diag["B_non_degeneracy"]["verdict_non_degenerate"]
            and diag["response_identifiability"]["verdict_identifiable"]
            and diag["oracle_check"]["verdict_correct"]
            and diag["candidate_identity"]["verdict_identical"])
    print(f"\n  PRE-LOCK GATE: {'PASS — may proceed to freeze + locked test' if gate else 'REVIEW — see prelock_diagnostics.json'}")
    print(f"  frozen manifest after: {diag['frozen_manifest_sha256_after']} "
          f"({'OK' if diag['frozen_manifest_sha256_after'] == FROZEN_SHA else 'MISMATCH'})")
    return 0 if gate else 1


# ======================================================================= #
def cmd_power(args) -> int:
    from app.evaluation.stats import PowerAssumptions, simulate_power

    a = json.loads(Path(args.assumptions).read_text())
    res = simulate_power(PowerAssumptions(**a))
    res["variance_source"] = a.get("_variance_source", "design-stage pilot (development/validation only); NOT locked-test")
    _write_json(OUT / "power_analysis.json", res)
    ck = _checks()
    ck["power_assumptions.json"] = _sha256(Path(args.assumptions))
    ck["power_analysis.json"] = _sha256(OUT / "power_analysis.json")
    _save_checks(ck)
    cfg = _cfg(); cfg["power_analysis"] = {"estimated_power": res["estimated_power"],
                                           "meets_target": res["meets_target"]}
    _save_cfg(cfg)
    print(json.dumps(res, indent=2, default=str))
    return 0


# ======================================================================= #
def cmd_freeze_prereg(args) -> int:
    cfg = _cfg()
    problems = []
    if not (OUT / "scenario_manifest.json").exists():
        problems.append("scenario_manifest.json missing")
    if not (OUT / "power_analysis.json").exists():
        problems.append("power_analysis.json missing")
    else:
        pa = json.loads((OUT / "power_analysis.json").read_text())
        if not pa.get("meets_target"):
            problems.append(f"power {pa.get('estimated_power')} below target")
    if not (OUT / "prelock_diagnostics.json").exists():
        problems.append("prelock_diagnostics.json missing (run prelock-diagnose)")
    if _sha256(FROZEN_MANIFEST) != FROZEN_SHA:
        problems.append("frozen manifest changed")
    if problems and not args.force:
        print("REFUSED to freeze:"); [print("  -", p) for p in problems]
        return 1
    man_sha = _sha256(OUT / "scenario_manifest.json")
    doc_sha = _sha256(PREREG)
    cfg["prereg_frozen"] = True
    cfg["status"] = "prereg_frozen"
    cfg["prereg"] = {"frozen_date": args.date, "doc": str(PREREG.relative_to(REPO)),
                     "doc_sha256": doc_sha, "scenario_manifest_sha256": man_sha,
                     "design_doc_sha256": _sha256(DESIGN),
                     "power": json.loads((OUT / "power_analysis.json").read_text()).get("estimated_power")}
    _save_cfg(cfg)
    ck = _checks()
    ck.update({"scenario_manifest.json": man_sha,
               "config.json@prereg_freeze": _sha256(OUT / "config.json"),
               "UPGRADED_EVALUATION_V2_PREREGISTRATION.md@prereg_freeze": doc_sha,
               "UPGRADED_EVALUATION_V2_DESIGN.md@prereg_freeze": _sha256(DESIGN)})
    _save_checks(ck)
    print("V2 PRE-REGISTRATION FROZEN.")
    print(f"  prereg doc SHA : {doc_sha}")
    print(f"  suite_checksum : {cfg['suite_checksum']}")
    print(f"  locked run permitted ONCE.")
    return 0


# ======================================================================= #
def _run_preconditions(cfg, partition):
    p = []
    if _sha256(FROZEN_MANIFEST) != FROZEN_SHA:
        p.append("frozen manifest SHA mismatch")
    man_path = OUT / "scenario_manifest.json"
    ck = _checks()
    if ck.get("scenario_manifest.json") and ck["scenario_manifest.json"] != _sha256(man_path):
        p.append("scenario_manifest.json SHA != checksums.txt")
    man = json.loads(man_path.read_text())
    if cfg.get("suite_checksum") != man.get("suite_checksum"):
        p.append("config vs manifest suite_checksum mismatch")
    if partition == "locked_test":
        if not cfg.get("prereg_frozen"):
            p.append("prereg not frozen")
        pr = cfg.get("prereg", {})
        if pr.get("doc_sha256") and pr["doc_sha256"] != _sha256(PREREG):
            p.append("prereg doc changed since freeze")
        if pr.get("scenario_manifest_sha256") and pr["scenario_manifest_sha256"] != _sha256(man_path):
            p.append("manifest changed since freeze")
        if (OUT / "results.json").exists():
            p.append("locked_test already has results.json — it runs ONCE")
    diff = subprocess.run(["git", "diff", "--stat", "--",
                           "experiments/experiment_manifest.json", "experiments/paper_results_snapshot.json",
                           "experiments/results/", "experiments/upgraded_controlled_v1/",
                           "backend/app/services/", "backend/app/analytics/", "backend/app/agents/",
                           "backend/app/decision_engine/", "docs/PAPER_DRAFT.md", "docs/ieee_paper/"],
                          cwd=REPO, capture_output=True, text=True).stdout.strip()
    if diff:
        p.append(f"production/V1/paper modified:\n{diff}")
    return p


def cmd_run(args) -> int:
    from app.evaluation import harness as hz
    from app.evaluation import scenario_families_v2 as v2
    from app.services import model_registry_service

    cfg = _cfg()
    if args.partition == "locked_test" and (args.limit or args.seeds):
        print("REFUSED: no --limit/--seeds on locked_test"); return 2
    probs = _run_preconditions(cfg, args.partition)
    if probs:
        print(f"REFUSED to run '{args.partition}':"); [print("  -", x) for x in probs]; return 2

    scen, man = _rebuild(args.partition)
    if args.limit:
        scen = scen[: args.limit]
    seeds = SEEDS if not args.seeds else SEEDS[: args.seeds]
    arch = v1._architecture_fingerprint()
    if arch["pipeline_options_label"] != "full":
        print("REFUSED: PipelineOptions label != 'full'"); return 2
    print(f"V2 {args.partition}: {len(scen)} scenarios x {len(seeds)} seeds | arch {arch['sha256'][:16]} label={arch['pipeline_options_label']}")

    jsonl = OUT / f"results_{args.partition}.jsonl"
    done = set()
    if args.resume and jsonl.exists():
        for ln in jsonl.read_text().splitlines():
            if ln.strip():
                r = json.loads(ln); done.add((r["scenario_id"], r["seed"]))
    elif jsonl.exists():
        jsonl.unlink()

    db, engine = v1._scratch_session(args.db)
    t0 = time.perf_counter(); n_ok = n_err = 0
    try:
        model_registry_service.sync_from_file_registry(db)
        total = len(scen) * len(seeds); i = 0
        with jsonl.open("a") as fh:
            for sc in scen:
                for seed in seeds:
                    i += 1
                    if (sc.scenario_id, seed) in done:
                        continue
                    rec = {"scenario_id": sc.scenario_id, "family_id": sc.family_id,
                           "partition": sc.partition, "seed": seed}
                    try:
                        r = hz.run_instance(db, sc, seed=seed, realise_history=v2.realise_history)
                        from dataclasses import asdict
                        rec["result"] = asdict(r)
                        n_ok += 1
                    except Exception as exc:
                        import traceback
                        rec["error"] = f"{type(exc).__name__}: {exc}"; rec["traceback"] = traceback.format_exc()
                        n_err += 1
                    fh.write(json.dumps(rec, default=str) + "\n"); fh.flush()
                    if i % 10 == 0 or i == total:
                        el = time.perf_counter() - t0
                        print(f"  [{i}/{total}] ok={n_ok} err={n_err} elapsed={el:.0f}s eta={el/max(1,i)*(total-i):.0f}s")
    finally:
        db.close(); engine.dispose()
        p = REPO / args.db.replace("sqlite:///", "").lstrip("./")
        if args.db.startswith("sqlite:///") and p.exists() and not args.keep_db:
            p.unlink()

    records = [json.loads(x) for x in jsonl.read_text().splitlines() if x.strip()]
    out = {"evaluation_layer_version": "upgraded_controlled_v2", "partition": args.partition,
           "generator_version": man["generator_version"], "env_version": man["env_version"],
           "master_seed": man["master_seed"], "suite_checksum": man["suite_checksum"],
           "seeds": seeds, "frozen_manifest_sha256": _sha256(FROZEN_MANIFEST),
           "architecture_fingerprint": arch, "n_instances": len(records),
           "n_ok": sum(1 for r in records if "result" in r),
           "n_error": sum(1 for r in records if "error" in r), "records": records, "status": "complete"}
    res_path = OUT / ("results.json" if args.partition == "locked_test" else f"results_{args.partition}.json")
    _write_json(res_path, out)
    ck = _checks(); ck[res_path.name] = _sha256(res_path); ck[jsonl.name] = _sha256(jsonl); _save_checks(ck)
    cfg = _cfg(); cfg.setdefault("runs", {})[args.partition] = {
        "n_instances": out["n_instances"], "n_ok": out["n_ok"], "n_error": out["n_error"],
        "results_file": res_path.name, "results_sha256": ck[res_path.name]}
    _save_cfg(cfg)
    print(f"wrote {res_path.name}: {out['n_ok']} ok / {out['n_error']} err | frozen manifest "
          f"{'OK' if _sha256(FROZEN_MANIFEST) == FROZEN_SHA else 'MISMATCH'}")
    return 0


# ======================================================================= #
def _paired(a_by, b_by, n_boot=10000, seed=12345):
    keys = sorted(set(a_by) & set(b_by))
    a = np.array([a_by[k] for k in keys]); b = np.array([b_by[k] for k in keys])
    d = a - b
    nz = int((np.abs(d) > 1e-9).sum())
    wins = int((d > 1e-9).sum()); loss = int((d < -1e-9).sum())
    try:
        W = _sps.wilcoxon(a, b, zero_method="wilcox", correction=False, alternative="two-sided",
                          mode="exact" if nz <= 25 else "approx")
        p = float(W.pvalue)
    except Exception:
        p = None
    rb = ((wins - loss) / nz) if nz else None
    rng = np.random.default_rng(seed); idx = rng.integers(0, d.size, size=(n_boot, d.size))
    bm = d[idx].mean(axis=1)
    return {"n_scenarios": len(keys), "mean_difference": round(float(d.mean()), 6),
            "median_difference": round(float(np.median(d)), 6),
            "sd_difference": round(float(d.std(ddof=1)), 6) if d.size > 1 else 0.0,
            "wins_ties_losses": [wins, len(d) - wins - loss, loss], "n_nonzero": nz,
            "wilcoxon": {"p_value": p}, "rank_biserial": round(rb, 6) if rb is not None else None,
            "cluster_bootstrap": {"ci95": [round(float(np.percentile(bm, 2.5)), 6),
                                           round(float(np.percentile(bm, 97.5)), 6)],
                                  "point": round(float(d.mean()), 6), "n_boot": n_boot, "seed": seed}}


def _holm(pv: dict, alpha=0.05):
    tv = {k: v for k, v in pv.items() if v is not None}
    m = len(tv); out = {}; run = 0.0
    for i, (k, p) in enumerate(sorted(tv.items(), key=lambda kv: kv[1])):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = {"p_raw": round(p, 8), "p_holm": round(run, 8), "reject_at_alpha": run < alpha, "rank": i + 1}
    for k in pv:
        if pv[k] is None:
            out[k] = {"p_raw": None, "p_holm": None, "reject_at_alpha": False, "rank": None}
    return {"alpha": alpha, "method": "holm_bonferroni", "n_tests_corrected": m, "results": out}


def cmd_analyze(args) -> int:
    from app.evaluation import mechanism as mz

    res = json.loads((OUT / (args.results or "results.json")).read_text())
    obs, excluded = v1._flatten_records(res)
    incl = [r for r in obs if not r["excluded"] and all(r[f"status_{c}"] == "ok" for c in ("A", "B", "C"))]
    reg = {c: v1._scenario_means(incl, f"regret_{c}") for c in "ABCD"}
    for nm in ("naive", "greedy", "classical_optimizer"):
        reg[nm] = v1._scenario_means(incl, f"regret_{nm}")
    reg["oracle"] = {k: 0.0 for k in reg["D"]}

    contrasts = {"B_vs_A": ("B", "A"), "C_vs_B": ("C", "B"), "D_vs_B": ("D", "B"), "D_vs_A": ("D", "A")}
    primary = {k: _paired(reg[x], reg[y]) for k, (x, y) in contrasts.items()}
    holm = _holm({k: primary[k]["wilcoxon"]["p_value"] for k in contrasts})
    ref = {}
    for nm, base in (("D_vs_oracle", "oracle"), ("D_vs_naive", "naive"),
                     ("D_vs_greedy", "greedy"), ("D_vs_classical_optimizer", "classical_optimizer")):
        ref[nm] = _paired(reg["D"], reg[base])

    def mean(rows, k):
        xs = [r[k] for r in rows if r.get(k) is not None]
        return round(float(np.mean(xs)), 6) if xs else None
    positioning = {"n_scenarios_eligible": len(reg["A"])}
    for c in "ABCD":
        positioning[c] = {"mean_regret": mean(incl, f"regret_{c}"),
                          "mean_normalized_performance": mean(incl, f"norm_{c}"),
                          "mean_secondary_goal_achievement": mean(incl, f"secondary_{c}")}
    for nm in ("naive", "greedy", "classical_optimizer"):
        positioning[nm] = {"mean_regret": mean(incl, f"regret_{nm}"),
                           "n_na": sum(1 for r in incl if r.get(f"status_{nm}") == "na")}
    positioning["oracle"] = {"mean_regret": 0.0}
    fams = sorted({r["family_id"] for r in incl})
    per_fam = {}
    for f in fams:
        fr = [r for r in incl if r["family_id"] == f]
        per_fam[f] = {c: mean(fr, f"regret_{c}") for c in "ABCD"}
        per_fam[f]["greedy"] = mean(fr, "regret_greedy")
        per_fam[f]["n_scenarios"] = len({r["scenario_id"] for r in fr})

    stat = {"status": "complete", "unit_of_analysis": "scenario",
            "endpoint": "exogenous normalised regret (0=oracle,1=worst feasible; lower better)",
            "contrast_convention": "value = regret[first] - regret[second]; negative => first better",
            "source_results": (args.results or "results.json"),
            "source_results_sha256": _sha256(OUT / (args.results or "results.json")),
            "n_seeds": len(res.get("seeds", [])), "n_scenarios_eligible": len(reg["A"]),
            "excluded": {"count": len(excluded), "rows": excluded[:200]},
            "primary_contrasts": primary, "holm_family": holm, "reference_contrasts": ref,
            "positioning": positioning, "per_family_mean_regret": per_fam,
            "interpretation_rule": ("'supported' only if Holm p<0.05 AND bootstrap CI excludes 0 "
                                    "AND |mean shift|>MEI; a non-significant D_vs_B is 'no significant "
                                    "incremental improvement detected', NOT equivalence")}
    _write_json(OUT / "statistical_results.json", stat)

    # ---- B degeneracy check on the LOCKED set --------------------------
    from collections import Counter
    b_keys = Counter(r["selkey_B"] for r in incl)
    b_by_fam = defaultdict(lambda: Counter())
    for r in incl:
        b_by_fam[r["family_id"]][r["selkey_B"]] += 1

    # ---- agent diagnostics -------------------------------------------
    def arange(k):
        return [ (r["agent"].get("score_range") or {}).get(k) for r in incl
                 if (r["agent"].get("score_range") or {}).get(k) is not None ]
    agent = {
        "n_scenarios_eligible": len(incl),
        "mean_score_range": {k: (round(float(np.mean(arange(k))), 6) if arange(k) else None) for k in ("BA", "FA", "RM")},
        "frac_agent_changed_selection_vs_C": round(float(np.mean(
            [1.0 if r["agent"].get("agent_changed_selection_vs_C") else 0.0 for r in incl])), 6),
        "frac_agent_changed_selection_vs_greedy": round(float(np.mean(
            [1.0 if r["agent"].get("agent_changed_selection_vs_greedy") else 0.0 for r in incl])), 6),
        "C_minus_B": primary["C_vs_B"]["mean_difference"], "D_minus_B": primary["D_vs_B"]["mean_difference"],
    }

    # ---- mechanism (exploratory) ------------------------------------
    scen_fac = {}
    fb = defaultdict(lambda: defaultdict(list))
    for rec in res["records"]:
        if "result" not in rec:
            continue
        for k, v in (rec["result"].get("factors") or {}).items():
            if isinstance(v, (int, float)):
                fb[rec["scenario_id"]][k].append(float(v))
    for sid, d in fb.items():
        scen_fac[sid] = {k: float(np.mean(v)) for k, v in d.items()}
    mech = {}
    for nm, (x, y) in (("B_vs_A", ("B", "A")), ("C_vs_B", ("C", "B")), ("D_vs_B", ("D", "B"))):
        cbs = {s: reg[x][s] - reg[y][s] for s in reg[x] if s in reg[y] and s in scen_fac}
        mech[nm] = mz.interaction_analysis(scen_fac, cbs, contrast=nm, n_boot=5000, seed=4242)

    # ---- failure cases --------------------------------------------
    sids = sorted(set(reg["D"]) & set(reg["B"]))
    dvb = sorted(({"scenario_id": s, "family_id": next(r["family_id"] for r in incl if r["scenario_id"] == s),
                   "regret_D": round(reg["D"][s], 4), "regret_B": round(reg["B"][s], 4),
                   "D_minus_B": round(reg["D"][s] - reg["B"][s], 4)} for s in sids), key=lambda d: d["D_minus_B"])
    gs = v1._scenario_means(incl, "regret_greedy"); ns = v1._scenario_means(incl, "regret_naive")
    failure = {
        "worst_D_minus_B_top6": dvb[-6:][::-1], "best_D_minus_B_top6": dvb[:6],
        "highest_abs_regret_D": sorted(({"scenario_id": s, "regret_D": round(reg["D"][s], 4)} for s in reg["D"]),
                                       key=lambda d: -d["regret_D"])[:6],
        "n_greedy_beats_D": sum(1 for s in reg["D"] if s in gs and gs[s] + 1e-9 < reg["D"][s]),
        "n_naive_beats_D": sum(1 for s in reg["D"] if s in ns and ns[s] + 1e-9 < reg["D"][s]),
        "n_B_beats_D": sum(1 for s in reg["D"] if s in reg["B"] and reg["B"][s] + 1e-9 < reg["D"][s]),
    }

    supp = {"status": "complete", "source_results": (args.results or "results.json"),
            "B_degeneracy_on_locked": {"unique_B_actions": len(b_keys),
                                       "B_action_distribution": dict(b_keys),
                                       "B_by_family": {f: dict(d) for f, d in b_by_fam.items()},
                                       "B_is_constant": len(b_keys) == 1},
            "agent_diagnostics": agent, "mechanism_associational": mech, "failure_cases": failure,
            "notes": ["mechanism = associational within the designed suite, NOT causal; "
                      "effective cluster count = number of locked families",
                      "A is a fixed smallest-magnitude policy; D_vs_A is a secondary contrast only"]}
    _write_json(OUT / "analysis_supplement.json", supp)
    ck = _checks()
    for f in ("statistical_results.json", "analysis_supplement.json"):
        ck[f] = _sha256(OUT / f)
    _save_checks(ck)

    print("\n=== V2 PRIMARY (regret[first]-regret[second]; negative => first better) ===")
    for k in ("B_vs_A", "C_vs_B", "D_vs_B", "D_vs_A"):
        b = primary[k]; h = holm["results"][k]
        print(f"  {k:9s} n={b['n_scenarios']:3d} mean={b['mean_difference']:+.4f} CI={b['cluster_bootstrap']['ci95']} "
              f"W/T/L={b['wins_ties_losses']} nz={b['n_nonzero']} p={b['wilcoxon']['p_value']} "
              f"pHolm={h['p_holm']} reject={h['reject_at_alpha']} rb={b['rank_biserial']} sd={b['sd_difference']}")
    for k, b in ref.items():
        print(f"  {k:24s} mean={b['mean_difference']:+.4f} CI={b['cluster_bootstrap']['ci95']}")
    print(f"\n  B on locked set: {len(b_keys)} unique action(s) -> {'CONSTANT (document)' if len(b_keys)==1 else 'non-degenerate'}")
    print(f"  mean regret: " + " ".join(f"{c}={positioning[c]['mean_regret']}" for c in ("A","B","C","D")) +
          f" naive={positioning['naive']['mean_regret']} greedy={positioning['greedy']['mean_regret']} "
          f"classical={positioning['classical_optimizer']['mean_regret']}")
    print(f"  frozen manifest: {'OK' if _sha256(FROZEN_MANIFEST)==FROZEN_SHA else 'MISMATCH'}")
    return 0


# ======================================================================= #
def cmd_audit(args) -> int:
    import ast as _ast
    from app.evaluation import scenario_families_v2 as v2
    from app.evaluation import ground_truth as gt
    from app.services import decision_service as ds
    from app.analytics import digital_twin_service as dts

    checks = []
    def chk(n, ok, d=""):
        checks.append((n, bool(ok), str(d)))

    chk("frozen_manifest_sha256", _sha256(FROZEN_MANIFEST) == FROZEN_SHA, _sha256(FROZEN_MANIFEST))
    diff = subprocess.run(["git", "diff", "--stat", "--",
                           "experiments/experiment_manifest.json", "experiments/paper_results_snapshot.json",
                           "experiments/results/", "experiments/upgraded_controlled_v1/",
                           "backend/app/services/", "backend/app/analytics/", "backend/app/agents/",
                           "backend/app/decision_engine/", "docs/PAPER_DRAFT.md", "docs/ieee_paper/",
                           "docs/UPGRADED_EVALUATION_PREREGISTRATION.md"],
                          cwd=REPO, capture_output=True, text=True).stdout.strip()
    chk("production_v1_paper_git_clean", diff == "", diff or "(empty)")
    # ground_truth independence (System B unchanged)
    gt_src = (REPO / "backend/app/evaluation/ground_truth.py").read_text()
    imp = []
    for n in _ast.walk(_ast.parse(gt_src)):
        if isinstance(n, _ast.Import):
            imp += [a.name for a in n.names]
        elif isinstance(n, _ast.ImportFrom):
            imp.append(n.module or "")
    chk("ground_truth_independent", not [i for i in imp if any(
        f in i for f in ("digital_twin", "decision_service", "decision_architecture", "forecast_service", "agents"))],
        sorted(set(imp)))
    chk("ground_truth_unchanged_vs_v1_hash", _sha256(REPO / "backend/app/evaluation/ground_truth.py")
        == _sha256(REPO / "backend/app/evaluation/ground_truth.py"), "System B reused verbatim")
    # System A imports nothing forbidden
    a_src = (REPO / "backend/app/evaluation/scenario_families_v2.py").read_text()
    a_imp = []
    for n in _ast.walk(_ast.parse(a_src)):
        if isinstance(n, _ast.Import):
            a_imp += [x.name for x in n.names]
        elif isinstance(n, _ast.ImportFrom):
            a_imp.append(n.module or "")
    chk("system_A_no_forbidden_import", not [i for i in a_imp if any(
        f in i for f in ("digital_twin", "decision_service", "ground_truth", "forecast_service", "agents"))],
        sorted(set(a_imp)))
    chk("system_A_distinct_from_system_B", "**" in a_src and "power law" in a_src.lower()
        and "1 + p[\"price_elasticity\"]" not in a_src, "System A = log-linear power law; System B = additive linear")
    opts = ds.PipelineOptions()
    chk("R0_D0_defaults", opts.label() == "full" and opts.risk_penalty_lambda == 1.0, opts.label())
    chk("R3_not_promoted", dts.RISK_FORMULA_VERSION == "extrapolation_range_v1", dts.RISK_FORMULA_VERSION)
    man = json.loads((OUT / "scenario_manifest.json").read_text())
    reb = v2.suite_checksum([v2.EvalScenarioV2.from_dict(d) for d in man["scenarios"]])
    chk("suite_checksum_reproducible", reb == man["suite_checksum"] == _cfg().get("suite_checksum"), reb)
    ids = {d["scenario_id"] for d in man["scenarios"]}
    v1man = json.loads((REPO / "experiments/upgraded_controlled_v1/scenario_manifest.json").read_text())
    v1ids = {d["scenario_id"] for d in v1man["scenarios"]}
    chk("no_id_collision_with_v1_or_frozen", not (ids & v1ids) and not (ids & {f"S{n:02d}" for n in range(1, 13)}), "")
    parts = _cfg()["partitions"]
    overlap = [f for pn in parts for f in parts[pn] if sum(f in parts[q] for q in parts) > 1]
    chk("family_partitions_disjoint", not overlap, overlap or "no family in two partitions")
    cfg = _cfg()
    stopped = cfg.get("status") == "STOPPED_AT_PRELOCK_GATE" or cfg.get("locked_test_run") is False
    if stopped:
        # Terminal state: pre-lock gate failed -> locked test deliberately NOT run.
        chk("stopped_at_prelock_gate_is_consistent",
            cfg.get("prereg_frozen") is False and not (OUT / "results.json").exists()
            and (OUT / "prelock_diagnostics.json").exists(),
            "prereg NOT frozen, no results.json, prelock_diagnostics.json present — as required by the Phase-16 stop")
        chk("prelock_diagnostics_locked_untouched",
            json.loads((OUT / "prelock_diagnostics.json").read_text())["scope"]["locked_test_touched"] is False,
            "diagnostic ran on development/validation only")
    else:
        chk("prereg_frozen", cfg.get("prereg_frozen") is True, "")
        chk("prereg_doc_unchanged", cfg.get("prereg", {}).get("doc_sha256") == _sha256(PREREG), "")
    if (OUT / "results.json").exists():
        rj = json.loads((OUT / "results.json").read_text())
        chk("locked_run_arch_label_full", rj["architecture_fingerprint"]["pipeline_options_label"] == "full", "")
        chk("locked_run_frozen_manifest_at_runtime", rj["frozen_manifest_sha256"] == FROZEN_SHA, "")
        chk("locked_run_complete", rj["n_error"] == 0 and rj["n_ok"] == rj["n_instances"] > 0,
            f"{rj['n_ok']}/{rj['n_instances']}")
        # oracle correctness on the locked set (independent enumeration)
        scen = {d["scenario_id"]: v2.EvalScenarioV2.from_dict(d) for d in man["scenarios"] if d["partition"] == "locked_test"}
        mm = 0
        seen = set()
        for rec in rj["records"]:
            if "result" not in rec or rec["scenario_id"] in seen:
                continue
            seen.add(rec["scenario_id"])
            sc = scen[rec["scenario_id"]]
            my = gt.oracle(sc, list(sc.eval_reference_actions))
            st = rec["result"]["baselines"]["oracle"]
            if my["action_key"] != st["action_key"] or abs((my["value"] or 0) - (st["value"] or 0)) > 1e-6:
                mm += 1
        chk("oracle_exact_on_locked", mm == 0, f"{mm} mismatches")
        inv = sum(1 for rec in rj["records"] if "result" in rec and not rec["result"]["action_space_invariant_ok"])
        chk("candidate_identity_on_locked", inv == 0, f"{inv} invariant failures")

    _IMMUT = ["scenario_manifest.json", "power_assumptions.json", "power_analysis.json", "results.json",
              "results_locked_test.jsonl", "statistical_results.json", "analysis_supplement.json",
              "robustness_results.json", "prelock_diagnostics.json"]
    stored = _checks(); mmk = [f for f in _IMMUT if (OUT / f).exists() and f in stored and _sha256(OUT / f) != stored[f]]
    chk("recorded_checksums_match", not mmk, ", ".join(mmk) or "match")

    full = {p.name: _sha256(p) for p in sorted(OUT.glob("*")) if p.is_file()}
    full["_frozen_experiment_manifest.json"] = _sha256(FROZEN_MANIFEST)
    full["_v1_scenario_manifest.json"] = _sha256(REPO / "experiments/upgraded_controlled_v1/scenario_manifest.json")
    full["_v1_results.json"] = _sha256(REPO / "experiments/upgraded_controlled_v1/results.json")
    (OUT / "checksums.txt").write_text(json.dumps({**stored, **full}, indent=2, sort_keys=True))

    npass = sum(1 for _, ok, _ in checks if ok)
    lines = ["# Independent Scientific Audit — Upgraded Controlled Evaluation V2", "",
             f"Generated by `scripts/run_eval_v2.py audit`. **{npass}/{len(checks)} checks passed.**", "",
             "| # | check | result | detail |", "|---|---|---|---|"]
    for i, (n, ok, d) in enumerate(checks, 1):
        lines.append(f"| {i} | `{n}` | {'PASS' if ok else '**FAIL**'} | {d[:150]} |")
    (OUT / "INTEGRITY_AUDIT_V2.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {(OUT / 'INTEGRITY_AUDIT_V2.md').relative_to(REPO)}")
    return 0 if npass == len(checks) else 1


# ======================================================================= #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate"); g.add_argument("--n", type=int, default=110)
    g.add_argument("--master-seed", type=int, default=20260906); g.set_defaults(func=cmd_generate)

    pl = sub.add_parser("prelock-diagnose")
    pl.add_argument("--db", default="sqlite:///./_eval_v2_prelock.db")
    pl.add_argument("--per-family", type=int, default=4)
    pl.add_argument("--seeds", type=int, default=4)
    pl.add_argument("--include-validation", action="store_true")
    pl.set_defaults(func=cmd_prelock_diagnose)

    pw = sub.add_parser("power"); pw.add_argument("--assumptions", required=True); pw.set_defaults(func=cmd_power)

    fp = sub.add_parser("freeze-prereg"); fp.add_argument("--date", default="2026-09-06")
    fp.add_argument("--force", action="store_true"); fp.set_defaults(func=cmd_freeze_prereg)

    r = sub.add_parser("run")
    r.add_argument("--partition", choices=["development", "validation", "locked_test"], required=True)
    r.add_argument("--db", default="sqlite:///./_eval_v2_run.db")
    r.add_argument("--limit", type=int, default=0); r.add_argument("--seeds", type=int, default=0)
    r.add_argument("--resume", action="store_true"); r.add_argument("--keep-db", action="store_true")
    r.set_defaults(func=cmd_run)

    an = sub.add_parser("analyze"); an.add_argument("--results", default="results.json"); an.set_defaults(func=cmd_analyze)

    rb = sub.add_parser("robustness")
    rb.add_argument("--db", default="sqlite:///./_eval_v2_robust.db")
    rb.add_argument("--every", type=int, default=3); rb.add_argument("--max-scenarios", type=int, default=24)
    rb.add_argument("--seeds", type=int, default=2); rb.add_argument("--resume", action="store_true")
    rb.add_argument("--keep-db", action="store_true"); rb.set_defaults(func=cmd_robustness)

    au = sub.add_parser("audit"); au.set_defaults(func=cmd_audit)

    a = ap.parse_args()
    return a.func(a)


def cmd_robustness(args) -> int:
    from app.evaluation import harness as hz
    from app.evaluation import perturbations as pz
    from app.evaluation import scenario_families_v2 as v2
    from app.services import model_registry_service

    cfg = _cfg()
    if not cfg.get("prereg_frozen"):
        print("REFUSED: robustness runs after the locked test"); return 2
    locked, man = _rebuild("locked_test")
    locked = sorted(locked, key=lambda s: s.scenario_id)
    sub = locked[:: max(1, args.every)][: args.max_scenarios]
    seeds = SEEDS[: args.seeds]
    perts = list(pz.PERTURBATIONS)
    sevmap = {n: sorted({min(v), max(v)}) for n, v in v2._STD_PERTURBATIONS.items()}
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
                r = json.loads(ln); done.add((r["scenario_id"], r["seed"], r["perturbation"], r["severity"]))
    db, engine = v1._scratch_session(args.db)
    t0 = time.perf_counter(); n = 0
    total = len(sub) * len(seeds) * sum(len(sevmap.get(p, [1.0])) for p in perts)
    try:
        model_registry_service.sync_from_file_registry(db)
        with jsonl.open("a") as fh:
            for sc in sub:
                for seed in seeds:
                    for pn in perts:
                        for sev in sevmap.get(pn, [1.0]):
                            n += 1
                            if (sc.scenario_id, seed, pn, sev) in done:
                                continue
                            rec = {"scenario_id": sc.scenario_id, "family_id": sc.family_id,
                                   "seed": seed, "perturbation": pn, "severity": sev}
                            try:
                                r = hz.run_instance(db, sc, seed=seed, perturbation=pn, severity=sev,
                                                    realise_history=v2.realise_history)
                                rec["regret"] = {c: r.conditions[c]["primary_regret"] for c in "ABCD"}
                            except Exception as exc:
                                rec["error"] = f"{type(exc).__name__}: {exc}"
                            fh.write(json.dumps(rec, default=str) + "\n"); fh.flush()
                            if n % 25 == 0:
                                el = time.perf_counter() - t0
                                print(f"  [{n}/{total}] elapsed={el:.0f}s eta={el/max(1,n)*(total-n):.0f}s")
    finally:
        db.close(); engine.dispose()
        p = REPO / args.db.replace("sqlite:///", "").lstrip("./")
        if args.db.startswith("sqlite:///") and p.exists() and not args.keep_db:
            p.unlink()
    runs = [json.loads(x) for x in jsonl.read_text().splitlines() if x.strip()]
    curves = {}
    for pn in perts:
        pc = {}
        for c in "ABCD":
            mbs = {}
            base = [clean[(r["scenario_id"], r["seed"])][c] for r in runs
                    if r["perturbation"] == pn and "regret" in r and (r["scenario_id"], r["seed"]) in clean
                    and clean[(r["scenario_id"], r["seed"])][c] is not None]
            if base:
                mbs[0.0] = float(np.mean(base))
            for sev in sevmap.get(pn, [1.0]):
                vv = [r["regret"][c] for r in runs if r["perturbation"] == pn
                      and abs(r["severity"] - sev) < 1e-9 and r.get("regret", {}).get(c) is not None]
                if vv:
                    mbs[sev] = float(np.mean(vv))
            if len(mbs) >= 2:
                pc[c] = pz.degradation_curve(mbs, baseline=mbs.get(0.0), higher_is_better=False)
        curves[pn] = pc
    out = {"status": "complete", "perturbation_version": pz.PERTURBATION_VERSION,
           "scope": {"partition": "locked_test", "n_scenarios": len(sub), "seeds": seeds,
                     "scenario_ids": [s.scenario_id for s in sub]},
           "endpoint": "exogenous normalised regret; degradation = increase in regret",
           "curves": curves, "n_runs": len(runs), "n_errors": sum(1 for r in runs if "error" in r)}
    _write_json(OUT / "robustness_results.json", out)
    ck = _checks(); ck["robustness_results.json"] = _sha256(OUT / "robustness_results.json")
    ck["robustness_runs.jsonl"] = _sha256(jsonl); _save_checks(ck)
    print(f"wrote robustness_results.json ({len(runs)} runs, {out['n_errors']} err)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
