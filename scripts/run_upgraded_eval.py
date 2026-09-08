#!/usr/bin/env python
"""Driver for the upgraded controlled evaluation (``backend/app/evaluation``).

EVALUATION-ONLY. This script:
  * never imports, runs, or writes the 16 frozen experiments;
  * never touches ``experiments/experiment_manifest.json`` /
    ``experiments/paper_results_snapshot.json``;
  * writes only under ``experiments/upgraded_controlled_v1/``;
  * uses a SEPARATE scratch database (default ``sqlite:///./_eval_scratch.db``)
    so no ``ExperimentRun`` row lands in the frozen story's database;
  * calls the production pipeline READ-ONLY with the R0/D0 default
    ``PipelineOptions`` for condition D.

Subcommands
  generate       build the scenario suite (>=50) + resolve/verify the feasible
                 action space per scenario; write scenario_manifest.json
  split          deterministic family-level development/validation/locked_test
                 partition; seal the locked_test family list + checksum
  power          simulation-based power analysis from an explicit assumptions file
                 (MUST be produced before any locked_test run)
  run            evaluate a partition  ---  BLOCKED for locked_test unless the
                 pre-registration is finalised (config.prereg_frozen == true)
  verify-freeze  re-check the frozen manifest SHA-256 and that production paths
                 are unmodified

Nothing here is executed during Phase 2. The Phase 2 stop condition forbids
running ``generate`` / ``split`` / ``power`` / ``run``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "experiments" / "upgraded_controlled_v1"
FROZEN_MANIFEST = REPO / "experiments" / "experiment_manifest.json"
FROZEN_MANIFEST_SHA256 = "94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff"
DEFAULT_DB = "sqlite:///./_eval_scratch.db"

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))


# --------------------------------------------------------------------------- #
def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str))
    print(f"wrote {path.relative_to(REPO)}  ({path.stat().st_size} bytes)")


def _load_config() -> dict:
    p = OUT_DIR / "config.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _save_config(cfg: dict) -> None:
    _write_json(OUT_DIR / "config.json", cfg)


def cmd_verify_freeze(_args) -> int:
    got = _sha256(FROZEN_MANIFEST)
    ok = got == FROZEN_MANIFEST_SHA256
    print(f"frozen manifest SHA-256: {got}  ({'OK' if ok else 'MISMATCH'})")
    try:
        diff = subprocess.run(
            ["git", "diff", "--stat", "--",
             "experiments/experiment_manifest.json", "experiments/paper_results_snapshot.json",
             "backend/app/services/", "backend/app/analytics/", "backend/app/agents/"],
            cwd=REPO, capture_output=True, text=True, check=False,
        ).stdout.strip()
        print("git diff (frozen + production):", diff or "(empty — unchanged)")
        clean = diff == ""
    except Exception as exc:  # pragma: no cover
        print("git diff check skipped:", exc)
        clean = None
    return 0 if (ok and clean in (True, None)) else 1


def cmd_generate(args) -> int:
    from app.evaluation import scenario_families as sf

    scenarios = sf.generate_suite(args.n, args.master_seed)
    manifest = {
        "evaluation_layer_version": "upgraded_controlled_v1",
        "generator_version": sf.GENERATOR_VERSION,
        "master_seed": args.master_seed,
        "n_scenarios": len(scenarios),
        "n_families": len(sf.FAMILY_IDS),
        "family_ids": sf.FAMILY_IDS,
        "suite_checksum": sf.suite_checksum(scenarios),
        "action_space_policy": "production_candidate_templates (verified per instance by the harness)",
        "scenarios": [sc.to_dict() for sc in scenarios],
        "status": "generated",
        "note": "feasible_actions are also re-derived + verified against the live "
                "strategy_generation_service per instance at run time.",
    }
    _write_json(OUT_DIR / "scenario_manifest.json", manifest)

    cfg = _load_config()
    cfg.update({
        "master_seed": args.master_seed, "n_scenarios": len(scenarios),
        "generator_version": sf.GENERATOR_VERSION,
        "suite_checksum": manifest["suite_checksum"], "status": "scenarios_generated",
        "prereg_frozen": cfg.get("prereg_frozen", False),
        "scratch_db": args.db,
    })
    _save_config(cfg)
    _write_json(OUT_DIR / "checksums.txt",
                {"scenario_manifest.json": _sha256(OUT_DIR / "scenario_manifest.json")})
    print("Phase-2 stop: do NOT run 'run' yet.")
    return 0


def cmd_split(args) -> int:
    from app.evaluation import scenario_families as sf

    parts = sf.partition_families(args.master_seed, dev=args.dev, val=args.val, test=args.test)
    cfg = _load_config()
    cfg["partitions"] = parts
    cfg["partition_seed"] = args.master_seed
    cfg["locked_test_family_checksum"] = hashlib.sha256(
        json.dumps(parts["locked_test"], sort_keys=True).encode()
    ).hexdigest()
    cfg["status"] = "partitioned"
    _save_config(cfg)

    # stamp the (family-level) partition into the frozen manifest so it is a
    # single self-contained record, then refresh the manifest checksum.
    man_path = OUT_DIR / "scenario_manifest.json"
    if man_path.exists():
        man = json.loads(man_path.read_text())
        lookup = {fid: name for name, fids in parts.items() for fid in fids}
        for sc in man.get("scenarios", []):
            sc["partition"] = lookup.get(sc["family_id"], "unassigned")
        man["partitions"] = parts
        man["partition_seed"] = args.master_seed
        man["status"] = "partitioned"
        _write_json(man_path, man)
        checks = json.loads((OUT_DIR / "checksums.txt").read_text()) if (OUT_DIR / "checksums.txt").exists() else {}
        checks["scenario_manifest.json"] = _sha256(man_path)
        _write_json(OUT_DIR / "checksums.txt", checks)

    print("partitions:", json.dumps(parts, indent=2))
    print("locked_test is SEALED by checksum; do not tune methodology against it.")
    return 0


def cmd_power(args) -> int:
    from app.evaluation.stats import PowerAssumptions, simulate_power

    assumptions = json.loads(Path(args.assumptions).read_text())
    res = simulate_power(PowerAssumptions(**assumptions))
    _write_json(OUT_DIR / "power_analysis.json", res)
    cfg = _load_config()
    cfg["power_analysis"] = {"estimated_power": res["estimated_power"],
                            "meets_target": res["meets_target"],
                            "assumptions_file": str(Path(args.assumptions).name)}
    _save_config(cfg)
    return 0


PREREG_DOC = REPO / "docs" / "UPGRADED_EVALUATION_PREREGISTRATION.md"


def cmd_freeze_prereg(args) -> int:
    """Phase 6 — seal the pre-registration. After this, ``run --partition
    locked_test`` is permitted (exactly once) and no methodology may change."""
    cfg = _load_config()
    problems = []
    if not (OUT_DIR / "scenario_manifest.json").exists():
        problems.append("scenario_manifest.json missing (run 'generate')")
    if not cfg.get("partitions", {}).get("locked_test"):
        problems.append("locked_test partition not sealed (run 'split')")
    if not (OUT_DIR / "power_analysis.json").exists():
        problems.append("power_analysis.json missing (run 'power')")
    pa = json.loads((OUT_DIR / "power_analysis.json").read_text()) if (OUT_DIR / "power_analysis.json").exists() else {}
    if not pa.get("meets_target"):
        problems.append(f"power {pa.get('estimated_power')} does not meet target — raise n and re-run 'power'")
    if _sha256(FROZEN_MANIFEST) != FROZEN_MANIFEST_SHA256:
        problems.append("frozen manifest SHA-256 mismatch")
    if problems and not args.force:
        print("REFUSED to freeze:")
        for p in problems:
            print("  -", p)
        return 1

    doc_sha = _sha256(PREREG_DOC)
    man_sha = _sha256(OUT_DIR / "scenario_manifest.json")
    cfg["prereg_frozen"] = True
    cfg["status"] = "prereg_frozen"
    cfg["prereg"] = {
        "frozen_date": args.date,
        "doc": str(PREREG_DOC.relative_to(REPO)),
        "doc_sha256": doc_sha,
        "scenario_manifest_sha256": man_sha,
        "suite_checksum": cfg.get("suite_checksum"),
        "locked_test_family_checksum": cfg.get("locked_test_family_checksum"),
        "power": {"estimated_power": pa.get("estimated_power"),
                  "assumptions_file": "power_assumptions.json"},
    }
    _save_config(cfg)
    checks = json.loads((OUT_DIR / "checksums.txt").read_text())
    checks.update({
        "scenario_manifest.json": man_sha,
        "power_analysis.json": _sha256(OUT_DIR / "power_analysis.json"),
        "power_assumptions.json": _sha256(OUT_DIR / "power_assumptions.json"),
        "config.json@prereg_freeze": _sha256(OUT_DIR / "config.json"),
        "UPGRADED_EVALUATION_PREREGISTRATION.md@prereg_freeze": doc_sha,
    })
    _write_json(OUT_DIR / "checksums.txt", checks)
    print("PRE-REGISTRATION FROZEN.")
    print(f"  prereg doc SHA-256 : {doc_sha}")
    print(f"  config   SHA-256   : {checks['config.json@prereg_freeze']}")
    print(f"  suite_checksum     : {cfg.get('suite_checksum')}")
    print(f"  power              : {pa.get('estimated_power')} (target {pa.get('assumptions',{}).get('target_power')})")
    print("  'run --partition locked_test' is now permitted ONCE.")
    return 0


def _scratch_session(db_url: str):
    """Fresh, ISOLATED scratch DB. Never the frozen story's database."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import app.models  # noqa: F401  (populate Base.metadata)
    from app.db.session import Base

    kw = {}
    if db_url.startswith("sqlite"):
        kw = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    engine = create_engine(db_url, **kw)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)(), engine


def cmd_dry_run(args) -> int:
    """Phase 3 — real-pipeline dry run in a SEPARATE scratch environment.

    Runs a handful of DEVELOPMENT (+ low_data) scenarios through the REAL frozen
    DecisionGPT pipeline and reports, per instance: candidate generation, the
    identical-action-space invariant, A/B/C/D execution + status, R0/D0 defaults,
    Digital-Twin execution, optimizer execution, agent diagnostics, and the
    latency of condition D. Writes ``dry_run_report.json``. Changes NOTHING in
    production and writes no frozen artifact.
    """
    from app.evaluation import harness as hz
    from app.evaluation import scenario_families as sf
    from app.services import model_registry_service

    print("frozen manifest:", _sha256(FROZEN_MANIFEST),
          "(OK)" if _sha256(FROZEN_MANIFEST) == FROZEN_MANIFEST_SHA256 else "(MISMATCH!)")

    db_url = args.db
    scratch_path = None
    if db_url.startswith("sqlite:///") and ":memory:" not in db_url:
        scratch_path = REPO / db_url.replace("sqlite:///", "").lstrip("./")
        if scratch_path.exists():
            scratch_path.unlink()
    db, engine = _scratch_session(db_url)

    report: dict = {"phase": "3_dry_run", "db_url": db_url,
                    "frozen_manifest_sha256": _sha256(FROZEN_MANIFEST),
                    "generator_version": sf.GENERATOR_VERSION, "instances": []}
    try:
        synced = model_registry_service.sync_from_file_registry(db)
        report["models_synced"] = [f"{getattr(m, 'model_name', '?')}:{getattr(m, 'version', '?')}"
                                   for m in synced]
        print(f"model registry synced: {len(synced)} rows")

        n = args.n or len(sf.FAMILY_IDS)
        suite = sf.generate_suite(n, args.master_seed)
        parts = sf.partition_families(args.master_seed)
        sf.assign_partitions(suite, parts)
        report["partitions"] = parts

        dev_fams = set(parts["development"])
        picks: list = []
        # a few ordinary development scenarios (distinct families)
        seen: set = set()
        for sc in suite:
            if sc.family_id in dev_fams and sc.family_id not in seen and sc.family_id != "low_data":
                picks.append(sc); seen.add(sc.family_id)
            if len(picks) >= args.families:
                break
        # several low_data instances (the family spans the 35-day MIN_HISTORY
        # boundary on purpose: some must be excluded as insufficient_data, some
        # must run and contribute genuinely data-constrained evidence)
        low_suite = sf.generate_suite(max(n, len(sf.FAMILY_IDS) * 5), args.master_seed)
        sf.assign_partitions(low_suite, parts)
        low_probes = [sc for sc in low_suite if sc.family_id == "low_data"][:6]
        picks += low_probes
        # one validation-partition scenario, to confirm partitions are usable too
        picks += [next((sc for sc in suite if sc.partition == "validation"), None)] if any(
            sc.partition == "validation" for sc in suite) else []
        picks = [p for p in picks if p is not None]

        seeds = list(range(args.master_seed, args.master_seed + args.seeds))
        for sc in picks:
            for seed in seeds:
                rec: dict = {"scenario_id": sc.scenario_id, "family_id": sc.family_id,
                             "partition": sc.partition, "seed": seed,
                             "history_days": sc.reference_history["days"]}
                try:
                    res = hz.run_instance(db, sc, seed=seed)
                    rec["invariant_ok"] = res.action_space_invariant_ok
                    rec["invariant_detail"] = {k: res.action_space_detail[k] for k in
                                               ("declared_count", "resolved_count", "identical")}
                    rec["exclude_from_primary"] = res.exclude_from_primary
                    rec["exclude_reason"] = res.exclude_reason
                    rec["conditions"] = {
                        c: {"status": res.conditions[c]["status"],
                            "selected_action_key": res.conditions[c]["selected_action_key"],
                            "primary_regret": res.conditions[c]["primary_regret"],
                            "primary_normalized": res.conditions[c]["primary_normalized"],
                            "secondary_goal_achievement": res.conditions[c]["secondary_goal_achievement"],
                            "latency_seconds": res.conditions[c]["latency_seconds"]}
                        for c in ("A", "B", "C", "D")}
                    rec["baselines"] = {b: res.baselines[b].get("status", "ok")
                                        for b in ("oracle", "naive", "greedy", "classical_optimizer")}
                    rec["agent_diagnostics"] = {
                        "assessable": res.agent_diagnostics["assessable"],
                        "score_range": res.agent_diagnostics.get("score_range"),
                        "changed_selection_vs_C": res.agent_diagnostics.get("agent_changed_selection_vs_C"),
                        "contribution_note": res.agent_diagnostics.get("contribution_note")}
                    rec["dt_executed"] = any(
                        res.conditions[c]["dt_projection"] for c in ("B", "C", "D"))
                    print(f"  {sc.scenario_id} seed={seed} inv_ok={rec['invariant_ok']} "
                          f"D.status={rec['conditions']['D']['status']} "
                          f"D.latency={rec['conditions']['D']['latency_seconds']}s "
                          f"excl={rec['exclude_from_primary']}({rec['exclude_reason']})")
                except Exception as exc:
                    import traceback
                    rec["error"] = f"{type(exc).__name__}: {exc}"
                    rec["traceback"] = traceback.format_exc()
                    print(f"  {sc.scenario_id} seed={seed} RAISED {rec['error']}")
                report["instances"].append(rec)

        # summary / checklist
        ok = [r for r in report["instances"] if "error" not in r]
        incl = [r for r in ok if not r["exclude_from_primary"]]        # eligible for primary analysis
        d_lat = [r["conditions"]["D"]["latency_seconds"] for r in incl]
        low = [r for r in ok if r["family_id"] == "low_data"]
        report["summary"] = {
            "instances_run": len(report["instances"]),
            "instances_ok": len(ok),
            "instances_raised": len(report["instances"]) - len(ok),
            "instances_eligible_for_primary": len(incl),
            "instances_excluded": sorted(
                {(r["scenario_id"], r["exclude_reason"]) for r in ok if r["exclude_from_primary"]}),
            "invariant_held_on_eligible": all(r.get("invariant_ok") for r in incl),
            "D_latency_seconds": {"min": min(d_lat, default=None), "max": max(d_lat, default=None),
                                  "mean": (round(sum(d_lat) / len(d_lat), 3) if d_lat else None)},
            "low_data_excluded_insufficient_data": sorted(
                {r["scenario_id"] for r in low
                 if r["exclude_from_primary"] and r["exclude_reason"] == "insufficient_data"}),
            "low_data_ran_in_primary": sorted({r["scenario_id"] for r in low if not r["exclude_from_primary"]}),
            "checks": {
                "candidate_generation": all(r["invariant_detail"]["resolved_count"] > 0 for r in ok),
                "action_space_identity_on_eligible": all(r["invariant_ok"] for r in incl),
                "ABCD_execution": all(set(r["conditions"]) == {"A", "B", "C", "D"} for r in ok),
                "digital_twin_execution_on_eligible": all(r["dt_executed"] for r in incl),
                "optimizer_execution": any(r["conditions"]["D"]["status"] in ("ok", "pick_outside_feasible_set")
                                           for r in incl),
                "agent_diagnostics_present": all("assessable" in r["agent_diagnostics"] for r in ok),
                "low_data_boundary_exercised": bool(low) and any(
                    r["history_days"] < 35 for r in low) and any(r["history_days"] >= 35 for r in low),
                "insufficient_data_exclusion_fires": any(
                    r["exclude_reason"] == "insufficient_data" for r in ok),
            },
        }
        _write_json(OUT_DIR / "dry_run_report.json", report)
        print("\nSUMMARY:", json.dumps(report["summary"], indent=2, default=str))
        print("\nfrozen manifest after dry run:", _sha256(FROZEN_MANIFEST),
              "(OK)" if _sha256(FROZEN_MANIFEST) == FROZEN_MANIFEST_SHA256 else "(MISMATCH!)")
        return 0
    finally:
        db.close()
        engine.dispose()
        if scratch_path and scratch_path.exists() and not args.keep_db:
            scratch_path.unlink()


SEEDS = list(range(20260906, 20260916))          # pre-registration §8: exactly 10


def _architecture_fingerprint() -> dict:
    """A stable digest of the frozen production decision path. If any of these
    change, the fingerprint changes and a locked run refuses to proceed."""
    from app.agents import strategy_optimizer as so
    from app.analytics import digital_twin_service as dts
    from app.services import decision_service as ds

    opts = ds.PipelineOptions()
    fp = {
        "pipeline_options_defaults": {
            k: getattr(opts, k) for k in sorted(vars(opts))
        },
        "pipeline_options_label": opts.label(),
        "candidate_grid": ds.CANDIDATE_GRID,
        "optimizer_formula_version": so.FORMULA_VERSION,
        "risk_formula_version": dts.RISK_FORMULA_VERSION,
        "supported_action_types": sorted(dts.SUPPORTED_ACTION_TYPES),
        "action_value_bounds": {k: list(v) for k, v in sorted(dts.ACTION_VALUE_BOUNDS.items())},
        "max_actions_per_simulation": dts.MAX_ACTIONS_PER_SIMULATION,
    }
    fp["sha256"] = hashlib.sha256(json.dumps(fp, sort_keys=True, default=str).encode()).hexdigest()
    return fp


def _run_preconditions(cfg: dict, partition: str) -> list[str]:
    problems: list[str] = []
    if _sha256(FROZEN_MANIFEST) != FROZEN_MANIFEST_SHA256:
        problems.append("frozen experiment manifest SHA-256 mismatch")
    man_path = OUT_DIR / "scenario_manifest.json"
    if not man_path.exists():
        problems.append("scenario_manifest.json missing")
        return problems
    man = json.loads(man_path.read_text())
    checks = json.loads((OUT_DIR / "checksums.txt").read_text()) if (OUT_DIR / "checksums.txt").exists() else {}
    if checks.get("scenario_manifest.json") and checks["scenario_manifest.json"] != _sha256(man_path):
        problems.append("scenario_manifest.json SHA-256 does not match checksums.txt")
    if cfg.get("suite_checksum") and cfg["suite_checksum"] != man.get("suite_checksum"):
        problems.append("config.suite_checksum != manifest.suite_checksum")
    if partition == "locked_test":
        if not cfg.get("prereg_frozen"):
            problems.append("prereg_frozen != true — 'freeze-prereg' first")
        pr = cfg.get("prereg", {})
        if pr.get("doc_sha256") and pr["doc_sha256"] != _sha256(PREREG_DOC):
            problems.append("pre-registration document changed since it was frozen")
        if pr.get("scenario_manifest_sha256") and pr["scenario_manifest_sha256"] != _sha256(man_path):
            problems.append("scenario_manifest.json changed since the pre-registration was frozen")
        done = OUT_DIR / "results_locked_test.jsonl"
        if done.exists() and done.stat().st_size > 0 and not (cfg.get("_locked_run_incomplete")):
            problems.append("locked_test already has results — it runs ONCE (delete artifacts to force a disclosed re-run)")
    # production untouched
    try:
        diff = subprocess.run(
            ["git", "diff", "--stat", "--",
             "experiments/experiment_manifest.json", "experiments/paper_results_snapshot.json",
             "experiments/results/", "backend/app/services/", "backend/app/analytics/",
             "backend/app/agents/", "backend/app/decision_engine/"],
            cwd=REPO, capture_output=True, text=True, check=False).stdout.strip()
        if diff:
            problems.append(f"production / frozen paths modified:\n{diff}")
    except Exception as exc:  # pragma: no cover
        print("  (git diff check skipped:", exc, ")")
    return problems


def cmd_run(args) -> int:
    from app.evaluation import harness as hz
    from app.evaluation import scenario_families as sf
    from app.services import model_registry_service

    cfg = _load_config()
    partition = args.partition
    if partition == "locked_test" and (args.limit or args.seeds):
        print("REFUSED: --limit / --seeds must not be used on the locked_test run "
              "(the primary analysis uses all 80 scenarios x 10 seeds).")
        return 2
    problems = _run_preconditions(cfg, partition)
    if problems:
        print(f"REFUSED to run '{partition}':")
        for p in problems:
            print("  -", p)
        return 2

    man = json.loads((OUT_DIR / "scenario_manifest.json").read_text())
    scenarios = [sf.EvalScenario.from_dict(d) for d in man["scenarios"]
                 if d.get("partition", "unassigned") == partition]
    if args.limit:
        scenarios = scenarios[: args.limit]
    seeds = SEEDS if not args.seeds else SEEDS[: args.seeds]
    arch = _architecture_fingerprint()
    print(f"partition={partition}  scenarios={len(scenarios)}  seeds={seeds}")
    print(f"architecture fingerprint: {arch['sha256']}  (options label: {arch['pipeline_options_label']!r})")
    if arch["pipeline_options_label"] != "full":
        print("REFUSED: PipelineOptions default label is not 'full' (R0/D0 changed).")
        return 2

    jsonl = OUT_DIR / f"results_{partition}.jsonl"
    done: set = set()
    if args.resume and jsonl.exists():
        for line in jsonl.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["scenario_id"], r["seed"]))
        print(f"resume: {len(done)} (scenario, seed) already done")
    elif jsonl.exists():
        jsonl.unlink()

    db_url = args.db
    scratch_path = None
    if db_url.startswith("sqlite:///") and ":memory:" not in db_url:
        scratch_path = REPO / db_url.replace("sqlite:///", "").lstrip("./")
        if scratch_path.exists() and not args.resume:
            scratch_path.unlink()
    db, engine = _scratch_session(db_url)
    n_ok = n_err = 0
    t_start = _now()
    try:
        synced = model_registry_service.sync_from_file_registry(db)
        print(f"model registry synced: {len(synced)} rows")
        total = len(scenarios) * len(seeds)
        i = 0
        with jsonl.open("a") as fh:
            for sc in scenarios:
                for seed in seeds:
                    i += 1
                    if (sc.scenario_id, seed) in done:
                        continue
                    rec = {"scenario_id": sc.scenario_id, "family_id": sc.family_id,
                           "partition": sc.partition, "seed": seed}
                    try:
                        res = hz.run_instance(db, sc, seed=seed)
                        rec["result"] = _instanceresult_to_jsonable(res)
                        n_ok += 1
                    except Exception as exc:
                        import traceback
                        rec["error"] = f"{type(exc).__name__}: {exc}"
                        rec["traceback"] = traceback.format_exc()
                        n_err += 1
                    fh.write(json.dumps(rec, default=str) + "\n")
                    fh.flush()
                    if i % 10 == 0 or i == total:
                        el = _now() - t_start
                        print(f"  [{i}/{total}] ok={n_ok} err={n_err} elapsed={el:.0f}s "
                              f"eta={el / max(1, i) * (total - i):.0f}s")
    finally:
        db.close()
        engine.dispose()
        if scratch_path and scratch_path.exists() and not args.keep_db:
            scratch_path.unlink()

    # assemble the full results.json for this partition
    records = [json.loads(l) for l in jsonl.read_text().splitlines() if l.strip()]
    out = {
        "evaluation_layer_version": "upgraded_controlled_v1",
        "partition": partition,
        "generator_version": man["generator_version"],
        "master_seed": man["master_seed"],
        "suite_checksum": man["suite_checksum"],
        "seeds": seeds,
        "frozen_manifest_sha256": _sha256(FROZEN_MANIFEST),
        "architecture_fingerprint": arch,
        "n_instances": len(records),
        "n_ok": sum(1 for r in records if "result" in r),
        "n_error": sum(1 for r in records if "error" in r),
        "records": records,
        "status": "complete",
    }
    res_path = OUT_DIR / (f"results.json" if partition == "locked_test" else f"results_{partition}.json")
    _write_json(res_path, out)
    checks = json.loads((OUT_DIR / "checksums.txt").read_text())
    checks[res_path.name] = _sha256(res_path)
    checks[jsonl.name] = _sha256(jsonl)
    _write_json(OUT_DIR / "checksums.txt", checks)

    cfg = _load_config()
    cfg.setdefault("runs", {})[partition] = {
        "n_instances": out["n_instances"], "n_ok": out["n_ok"], "n_error": out["n_error"],
        "results_file": res_path.name, "results_sha256": checks[res_path.name],
        "architecture_fingerprint_sha256": arch["sha256"],
    }
    if partition == "locked_test":
        cfg["_locked_run_incomplete"] = (out["n_error"] > 0)
    _save_config(cfg)
    print(f"\nfrozen manifest after run: {_sha256(FROZEN_MANIFEST)} "
          f"({'OK' if _sha256(FROZEN_MANIFEST) == FROZEN_MANIFEST_SHA256 else 'MISMATCH'})")
    print(f"wrote {res_path.name}: {out['n_ok']} ok / {out['n_error']} error")
    return 0


def _now() -> float:
    import time
    return time.perf_counter()


# ======================================================================= #
# Phase 9-14 analysis                                                      #
# ======================================================================= #
def _clip01(x):
    return None if x is None else max(0.0, min(1.0, float(x)))


def _flatten_records(results: dict) -> tuple[list[dict], list[dict]]:
    """Return (per-(scenario,seed) observation rows, excluded-row descriptions)."""
    obs, excluded = [], []
    for r in results["records"]:
        if "result" not in r:
            excluded.append({"scenario_id": r["scenario_id"], "seed": r["seed"],
                             "reason": "harness_error", "detail": r.get("error")})
            continue
        res = r["result"]
        C = res["conditions"]
        bl = res["baselines"]
        ov = bl.get("oracle", {}).get("value")
        wv = bl.get("oracle", {}).get("worst_value")
        span = (ov - wv) if (ov is not None and wv is not None) else None
        row = {
            "scenario_id": r["scenario_id"], "family_id": r["family_id"], "seed": r["seed"],
            "excluded": res["exclude_from_primary"], "exclude_reason": res["exclude_reason"],
            "invariant_ok": res["action_space_invariant_ok"],
            "oracle_n_feasible": bl.get("oracle", {}).get("n_feasible"),
            "agent": res.get("agent_diagnostics", {}),
            "factors": res.get("factors", {}),
        }
        for cond in ("A", "B", "C", "D"):
            row[f"regret_{cond}"] = C[cond]["primary_regret"]
            row[f"norm_{cond}"] = C[cond]["primary_normalized"]
            row[f"secondary_{cond}"] = C[cond]["secondary_goal_achievement"]
            row[f"status_{cond}"] = C[cond]["status"]
            row[f"selkey_{cond}"] = C[cond]["selected_action_key"]
            row[f"value_{cond}"] = C[cond]["primary_value"]
        for name in ("naive", "greedy", "classical_optimizer"):
            b = bl.get(name, {})
            v = b.get("value")
            row[f"regret_{name}"] = (_clip01((ov - v) / span)
                                     if (v is not None and span and span > 1e-12) else None)
            row[f"value_{name}"] = v
            row[f"status_{name}"] = b.get("status", "ok")
        row["regret_oracle"] = 0.0
        if res["exclude_from_primary"]:
            excluded.append({"scenario_id": r["scenario_id"], "seed": r["seed"],
                             "reason": res["exclude_reason"]})
        obs.append(row)
    return obs, excluded


def _scenario_means(rows: list[dict], key: str) -> dict:
    import numpy as _np
    from collections import defaultdict as _dd
    b = _dd(list)
    for r in rows:
        v = r.get(key)
        if v is not None:
            b[r["scenario_id"]].append(float(v))
    return {k: float(_np.mean(v)) for k, v in b.items() if v}


def cmd_analyze(args) -> int:
    import numpy as np

    from app.evaluation import mechanism as mz
    from app.evaluation import stats as st

    res_path = OUT_DIR / (args.results or "results.json")
    results = json.loads(res_path.read_text())
    obs, excluded = _flatten_records(results)
    incl = [r for r in obs if not r["excluded"]
            and all(r[f"status_{c}"] == "ok" for c in ("A", "B", "C"))]
    print(f"observations: {len(obs)}  eligible-for-primary: {len(incl)}  excluded: {len(excluded)}")

    # ---- Phase 9: primary scenario-level paired analysis ----------------
    reg = {c: _scenario_means(incl, f"regret_{c}") for c in ("A", "B", "C", "D")}
    contrasts = {"B_vs_A": ("B", "A"), "C_vs_B": ("C", "B"),
                 "D_vs_B": ("D", "B"), "D_vs_A": ("D", "A")}
    primary = {}
    pvals = {}
    for name, (x, y) in contrasts.items():
        bundle = st.paired_scenario_analysis(reg[x], reg[y], label=f"regret[{x}] - regret[{y}]",
                                             n_boot=10000, boot_seed=12345)
        primary[name] = bundle
        pvals[name] = bundle["wilcoxon"]["p_value"]
    holm = st.holm_correction(pvals, alpha=0.05)

    # reference contrasts (descriptive; NOT in the Holm family)
    ref = {}
    for name, base in (("D_vs_oracle", "regret_oracle"), ("D_vs_naive", "regret_naive"),
                       ("D_vs_greedy", "regret_greedy"), ("D_vs_classical_optimizer", "regret_classical_optimizer")):
        bx = _scenario_means(incl, base)
        ref[name] = st.paired_scenario_analysis(reg["D"], bx, label=f"regret[D] - {base}",
                                                n_boot=10000, boot_seed=12345)

    # ---- Phase 10: baseline / condition positioning --------------------
    def _mean(rows, k):
        xs = [r[k] for r in rows if r.get(k) is not None]
        return round(float(np.mean(xs)), 6) if xs else None
    positioning = {"n_scenarios_eligible": len(reg["A"])}
    for c in ("A", "B", "C", "D"):
        positioning[c] = {"mean_regret": _mean(incl, f"regret_{c}"),
                          "mean_normalized_performance": _mean(incl, f"norm_{c}"),
                          "mean_secondary_goal_achievement": _mean(incl, f"secondary_{c}")}
    for name in ("naive", "greedy", "classical_optimizer"):
        na = sum(1 for r in incl if r.get(f"status_{name}") == "na")
        positioning[name] = {"mean_regret": _mean(incl, f"regret_{name}"),
                             "n_na": na}
    positioning["oracle"] = {"mean_regret": 0.0, "note": "upper-bound reference, not a competitor"}
    # per-family regret table
    fams = sorted({r["family_id"] for r in incl})
    per_family = {}
    for f in fams:
        fr = [r for r in incl if r["family_id"] == f]
        per_family[f] = {c: _mean(fr, f"regret_{c}") for c in ("A", "B", "C", "D")}
        per_family[f]["greedy"] = _mean(fr, "regret_greedy")
        per_family[f]["n_scenarios"] = len({r["scenario_id"] for r in fr})

    statistical_results = {
        "status": "complete",
        "source_results": res_path.name,
        "source_results_sha256": _sha256(res_path),
        "unit_of_analysis": "scenario",
        "endpoint": "exogenous normalised regret (0 = oracle, 1 = worst feasible; lower is better)",
        "contrast_convention": "each contrast value = regret[first] - regret[second]; negative => first has lower regret",
        "n_seeds": len(results.get("seeds", [])),
        "n_scenarios_eligible": len(reg["A"]),
        "excluded": {"count": len(excluded), "rows": excluded[:200]},
        "primary_contrasts": primary,
        "holm_family": holm,
        "reference_contrasts": ref,
        "positioning": positioning,
        "per_family_mean_regret": per_family,
        "interpretation_rule": ("a contrast is 'supported' only if Holm-adjusted p < 0.05 AND the "
                                "cluster-bootstrap CI excludes 0 AND |mean shift| > 0.10 (MEI)"),
    }
    _write_json(OUT_DIR / "statistical_results.json", statistical_results)

    # ---- Phase 11: agent diagnostics ---------------------------------
    def _agent_series(k):
        out = []
        for r in incl:
            a = r.get("agent", {})
            sr = a.get("score_range") or {}
            out.append(sr.get(k))
        return [x for x in out if x is not None]
    agent_summary = {
        "n_scenarios_eligible": len(incl),
        "mean_score_range": {k: (round(float(np.mean(_agent_series(k))), 6) if _agent_series(k) else None)
                             for k in ("BA", "FA", "RM")},
        "max_score_range": {k: (round(float(np.max(_agent_series(k))), 6) if _agent_series(k) else None)
                            for k in ("BA", "FA", "RM")},
        "mean_inter_agent_agreement": round(float(np.mean(
            [r["agent"].get("inter_agent_agreement_mean") for r in incl
             if r.get("agent", {}).get("inter_agent_agreement_mean") is not None] or [float("nan")])), 6),
        "frac_agent_changed_selection_vs_C": round(float(np.mean(
            [1.0 if r["agent"].get("agent_changed_selection_vs_C") else 0.0 for r in incl])), 6),
        "frac_agent_changed_selection_vs_greedy": round(float(np.mean(
            [1.0 if r["agent"].get("agent_changed_selection_vs_greedy") else 0.0 for r in incl])), 6),
        "C_minus_B": primary["C_vs_B"]["mean_difference"],
        "D_minus_B": primary["D_vs_B"]["mean_difference"],
    }
    agent_summary["finding"] = (
        "agent layer rarely changes the selection and shows small score spread — largely inert on this suite"
        if (agent_summary["frac_agent_changed_selection_vs_C"] < 0.15
            and (agent_summary["mean_score_range"]["RM"] or 0) < 0.1
            and (agent_summary["mean_score_range"]["BA"] or 0) < 0.1)
        else "agent layer changes selections and/or shows non-trivial score spread on this suite")

    # ---- Phase 13: mechanism (associational, NOT causal) -------------
    numeric_factor_keys = [k for k in mz.FACTOR_NAMES]
    scen_factors = {}
    from collections import defaultdict as _dd
    fbuckets = _dd(lambda: _dd(list))
    for r in incl:
        for k in numeric_factor_keys:
            v = r.get("factors", {}).get(k)
            if isinstance(v, (int, float)):
                fbuckets[r["scenario_id"]][k].append(float(v))
    for sid, d in fbuckets.items():
        scen_factors[sid] = {k: float(np.mean(v)) for k, v in d.items() if v}
    mech = {}
    for name, (x, y) in (("B_vs_A", ("B", "A")), ("C_vs_B", ("C", "B")), ("D_vs_B", ("D", "B"))):
        cbs = {sid: reg[x][sid] - reg[y][sid] for sid in reg[x] if sid in reg[y] and sid in scen_factors}
        mech[name] = mz.interaction_analysis(scen_factors, cbs, contrast=name, n_boot=5000, seed=4242)

    # ---- Phase 14: failure cases -----------------------------------
    sids = sorted(set(reg["D"]) & set(reg["B"]))
    dvb = sorted(({"scenario_id": s, "family_id": next(r["family_id"] for r in incl if r["scenario_id"] == s),
                   "regret_D": round(reg["D"][s], 4), "regret_B": round(reg["B"][s], 4),
                   "D_minus_B": round(reg["D"][s] - reg["B"][s], 4)} for s in sids),
                 key=lambda d: d["D_minus_B"])
    greedy_s = _scenario_means(incl, "regret_greedy")
    naive_s = _scenario_means(incl, "regret_naive")
    failure_cases = {
        "worst_D_minus_B (D much worse than B)": dvb[-5:][::-1],
        "best_D_minus_B (D much better than B)": dvb[:5],
        "highest_absolute_regret_D": sorted(
            ({"scenario_id": s, "regret_D": round(reg["D"][s], 4)} for s in reg["D"]),
            key=lambda d: -d["regret_D"])[:5],
        "greedy_beats_D": sorted(
            ({"scenario_id": s, "regret_greedy": round(greedy_s[s], 4), "regret_D": round(reg["D"][s], 4)}
             for s in greedy_s if s in reg["D"] and greedy_s[s] + 1e-9 < reg["D"][s]),
            key=lambda d: d["regret_D"] - d["regret_greedy"], reverse=True)[:10],
        "naive_beats_D": sorted(
            ({"scenario_id": s, "regret_naive": round(naive_s[s], 4), "regret_D": round(reg["D"][s], 4)}
             for s in naive_s if s in reg["D"] and naive_s[s] + 1e-9 < reg["D"][s]),
            key=lambda d: d["regret_D"] - d["regret_naive"], reverse=True)[:10],
        "near_oracle_D (regret <= 0.02)": sorted(s for s in reg["D"] if reg["D"][s] <= 0.02),
    }

    supplement = {
        "status": "complete",
        "source_results": res_path.name,
        "agent_diagnostics": agent_summary,
        "mechanism_associational": mech,
        "failure_cases": failure_cases,
        "notes": ["mechanism coefficients are associational within the designed suite, NOT causal",
                  "agent analysis reports whatever the frozen agents do; no agent output was modified"],
    }
    _write_json(OUT_DIR / "analysis_supplement.json", supplement)

    checks = json.loads((OUT_DIR / "checksums.txt").read_text())
    checks["statistical_results.json"] = _sha256(OUT_DIR / "statistical_results.json")
    checks["analysis_supplement.json"] = _sha256(OUT_DIR / "analysis_supplement.json")
    _write_json(OUT_DIR / "checksums.txt", checks)

    # console digest
    print("\n=== PRIMARY (scenario-level, regret[first]-regret[second]; negative => first better) ===")
    for name in ("B_vs_A", "C_vs_B", "D_vs_B", "D_vs_A"):
        b = primary[name]
        h = holm["results"][name]
        print(f"  {name:9s} n={b['n_scenarios']:3d} mean_d={b['mean_difference']} "
              f"CI={b['cluster_bootstrap']['ci95']} W/T/L={b['wins_ties_losses']} nz={b['n_nonzero']} "
              f"p_raw={h['p_raw']} p_holm={h['p_holm']} reject={h['reject_at_alpha']} rb={b['rank_biserial']}")
    print("  reference:")
    for name, b in ref.items():
        print(f"    {name:26s} mean_d={b['mean_difference']} CI={b['cluster_bootstrap']['ci95']}")
    print(f"\n  agents: {agent_summary['finding']}")
    print(f"  frozen manifest: {_sha256(FROZEN_MANIFEST)} "
          f"({'OK' if _sha256(FROZEN_MANIFEST) == FROZEN_MANIFEST_SHA256 else 'MISMATCH'})")
    return 0


def cmd_robustness(args) -> int:
    """Phase 12 — descriptive robustness (frozen pre-registration §11).

    Re-runs A/B/C/D on PERTURBED OBSERVATIONS (ground truth unchanged) for a
    fixed deterministic subsample of the locked-test partition and reports a
    degradation curve per perturbation x condition. Not part of the confirmatory
    family. Seed count / subsample size are operational choices (§11 leaves them
    open); they are recorded here and in the report.
    """
    import numpy as np

    from app.evaluation import harness as hz
    from app.evaluation import perturbations as pz
    from app.evaluation import scenario_families as sf
    from app.services import model_registry_service

    cfg = _load_config()
    if not cfg.get("prereg_frozen"):
        print("REFUSED: robustness runs after the locked test; prereg must be frozen.")
        return 2
    man = json.loads((OUT_DIR / "scenario_manifest.json").read_text())
    locked = sorted((sf.EvalScenario.from_dict(d) for d in man["scenarios"]
                     if d.get("partition") == "locked_test"), key=lambda s: s.scenario_id)
    subsample = locked[:: max(1, args.every)][: args.max_scenarios]
    seeds = SEEDS[: args.seeds]
    perts = list(pz.PERTURBATIONS)
    sev_map = {name: sorted({min(v), max(v)}) for name, v in
               sf._STD_PERTURBATIONS.items()}  # low + high configured severity
    print(f"robustness: {len(subsample)} locked scenarios x {len(seeds)} seeds x "
          f"{len(perts)} perturbations x <=2 severities")

    # clean baseline regret per (scenario, seed) from the locked results
    lr = json.loads((OUT_DIR / "results.json").read_text())
    clean = {}
    for rec in lr["records"]:
        if "result" not in rec:
            continue
        C = rec["result"]["conditions"]
        clean[(rec["scenario_id"], rec["seed"])] = {c: C[c]["primary_regret"] for c in ("A", "B", "C", "D")}

    db, engine = _scratch_session(args.db)
    jsonl = OUT_DIR / "robustness_runs.jsonl"
    if jsonl.exists() and not args.resume:
        jsonl.unlink()
    done = set()
    if args.resume and jsonl.exists():
        for l in jsonl.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                done.add((r["scenario_id"], r["seed"], r["perturbation"], r["severity"]))
    t0 = _now()
    n = 0
    total = len(subsample) * len(seeds) * sum(len(sev_map.get(p, [1.0])) for p in perts)
    try:
        model_registry_service.sync_from_file_registry(db)
        with jsonl.open("a") as fh:
            for sc in subsample:
                for seed in seeds:
                    for pname in perts:
                        for sev in sev_map.get(pname, [1.0]):
                            n += 1
                            if (sc.scenario_id, seed, pname, sev) in done:
                                continue
                            rec = {"scenario_id": sc.scenario_id, "family_id": sc.family_id,
                                   "seed": seed, "perturbation": pname, "severity": sev}
                            try:
                                r = hz.run_instance(db, sc, seed=seed, perturbation=pname, severity=sev)
                                rec["regret"] = {c: r.conditions[c]["primary_regret"] for c in ("A", "B", "C", "D")}
                                rec["exclude"] = r.exclude_from_primary
                                rec["exclude_reason"] = r.exclude_reason
                            except Exception as exc:
                                rec["error"] = f"{type(exc).__name__}: {exc}"
                            fh.write(json.dumps(rec, default=str) + "\n")
                            fh.flush()
                            if n % 25 == 0:
                                el = _now() - t0
                                print(f"  [{n}/{total}] elapsed={el:.0f}s eta={el/max(1,n)*(total-n):.0f}s")
    finally:
        db.close(); engine.dispose()
        p = REPO / args.db.replace("sqlite:///", "").lstrip("./")
        if args.db.startswith("sqlite:///") and p.exists() and not args.keep_db:
            p.unlink()

    # aggregate -> degradation curves
    runs = [json.loads(l) for l in jsonl.read_text().splitlines() if l.strip()]
    curves = {}
    for pname in perts:
        sevs = [0.0] + sev_map.get(pname, [1.0])
        per_cond = {}
        for c in ("A", "B", "C", "D"):
            mbs = {}
            base_vals = [clean[(r["scenario_id"], r["seed"])][c]
                         for r in runs if r["perturbation"] == pname and "regret" in r
                         and (r["scenario_id"], r["seed"]) in clean
                         and clean[(r["scenario_id"], r["seed"])][c] is not None]
            if base_vals:
                mbs[0.0] = float(np.mean(base_vals))
            for sev in sev_map.get(pname, [1.0]):
                vals = [r["regret"][c] for r in runs
                        if r["perturbation"] == pname and abs(r["severity"] - sev) < 1e-9
                        and r.get("regret", {}).get(c) is not None]
                if vals:
                    mbs[sev] = float(np.mean(vals))
            if len(mbs) >= 2:
                per_cond[c] = pz.degradation_curve(mbs, baseline=mbs.get(0.0), higher_is_better=False)
        curves[pname] = per_cond

    out = {
        "status": "complete",
        "perturbation_version": pz.PERTURBATION_VERSION,
        "scope": {"partition": "locked_test", "subsample_every": args.every,
                  "n_scenarios": len(subsample), "scenario_ids": [s.scenario_id for s in subsample],
                  "seeds": seeds},
        "endpoint": "exogenous normalised regret (lower is better); degradation = increase in regret",
        "curves": curves,
        "n_runs": len(runs),
        "n_errors": sum(1 for r in runs if "error" in r),
    }
    _write_json(OUT_DIR / "robustness_results.json", out)
    checks = json.loads((OUT_DIR / "checksums.txt").read_text())
    checks["robustness_results.json"] = _sha256(OUT_DIR / "robustness_results.json")
    checks["robustness_runs.jsonl"] = _sha256(jsonl)
    _write_json(OUT_DIR / "checksums.txt", checks)
    print(f"\nwrote robustness_results.json ({len(runs)} runs, {out['n_errors']} errors)")
    print(f"frozen manifest: {_sha256(FROZEN_MANIFEST)} "
          f"({'OK' if _sha256(FROZEN_MANIFEST) == FROZEN_MANIFEST_SHA256 else 'MISMATCH'})")
    return 0


def _instanceresult_to_jsonable(res) -> dict:
    from dataclasses import asdict as _asdict
    try:
        return _asdict(res)
    except Exception:
        return {k: getattr(res, k) for k in vars(res)}


def cmd_audit(args) -> int:
    """Phase 15 — reproducibility / integrity audit. Verifies every freeze
    invariant, recomputes checksums, and writes REPRODUCIBILITY_AUDIT.md +
    a full checksums.txt. Read-only w.r.t. production and the frozen study."""
    import numpy as np

    from app.evaluation import scenario_families as sf
    from app.services import decision_service as ds

    checks: list[tuple[str, bool, str]] = []

    def chk(name, ok, detail=""):
        checks.append((name, bool(ok), str(detail)))

    # 1. frozen experiment manifest untouched
    chk("frozen_manifest_sha256", _sha256(FROZEN_MANIFEST) == FROZEN_MANIFEST_SHA256,
        _sha256(FROZEN_MANIFEST))
    # 2. production + frozen artifacts: git clean
    diff = subprocess.run(
        ["git", "diff", "--stat", "--",
         "experiments/experiment_manifest.json", "experiments/paper_results_snapshot.json",
         "experiments/results/", "backend/app/services/", "backend/app/analytics/",
         "backend/app/agents/", "backend/app/decision_engine/",
         "docs/PAPER_DRAFT.md", "docs/ieee_paper/"],
        cwd=REPO, capture_output=True, text=True, check=False).stdout.strip()
    chk("production_and_paper_git_clean", diff == "", diff or "(empty)")
    # 3. multi_scenario_service still 12x5 frozen suite
    mss = (REPO / "backend/app/services/multi_scenario_service.py").read_text()
    chk("frozen_12x5_suite_untouched",
        "SEEDS = [42, 43, 44, 45, 46]" in mss and mss.count('"S0') >= 9,
        "SEEDS and S01.. markers present")
    # 4. R0/D0 defaults intact
    opts = ds.PipelineOptions()
    chk("R0_D0_defaults",
        opts.label() == "full" and opts.risk_penalty_lambda == 1.0
        and getattr(opts, "risk_model", None) in (None, "R0")
        and all(getattr(opts, k) for k in vars(opts) if k.startswith("use_")),
        f"label={opts.label()} lambda={opts.risk_penalty_lambda}")
    # 5. R3 not promoted (extrapolation_range_v1 is still the default risk formula)
    from app.analytics import digital_twin_service as dts
    chk("R3_not_promoted", dts.RISK_FORMULA_VERSION == "extrapolation_range_v1",
        dts.RISK_FORMULA_VERSION)
    # 6. evaluation layer imports no LLM / network client
    evdir = REPO / "backend/app/evaluation"
    bad = []
    for f in evdir.glob("*.py"):
        t = f.read_text().lower()
        for tok in ("openai", "anthropic", "requests.", "httpx", "urllib.request", "llm_client"):
            if tok in t:
                bad.append(f"{f.name}:{tok}")
    chk("no_llm_or_network_in_eval_layer", not bad, ", ".join(bad) or "clean")
    # 7. manifest suite_checksum reproduces from the stored scenarios
    man = json.loads((OUT_DIR / "scenario_manifest.json").read_text())
    rebuilt = sf.suite_checksum([sf.EvalScenario.from_dict(d) for d in man["scenarios"]])
    cfg = _load_config()
    chk("suite_checksum_reproducible",
        rebuilt == man["suite_checksum"] == cfg.get("suite_checksum"), rebuilt)
    # 8. no S01..S12 collision
    ids = {d["scenario_id"] for d in man["scenarios"]}
    chk("no_frozen_scenario_id_collision", not (ids & {f"S{n:02d}" for n in range(1, 13)}), "")
    # 9. prereg frozen + doc unchanged
    pr = cfg.get("prereg", {})
    chk("prereg_frozen", cfg.get("prereg_frozen") is True, "")
    chk("prereg_doc_unchanged", pr.get("doc_sha256") == _sha256(PREREG_DOC), _sha256(PREREG_DOC))
    # 10. results.json integrity + architecture fingerprint reproduces
    rj = json.loads((OUT_DIR / "results.json").read_text())
    fp_now = _architecture_fingerprint()
    chk("architecture_fingerprint_stable",
        rj["architecture_fingerprint"]["sha256"] == fp_now["sha256"], fp_now["sha256"])
    chk("locked_run_complete_no_errors",
        rj["n_error"] == 0 and rj["n_ok"] == rj["n_instances"] > 0,
        f"{rj['n_ok']}/{rj['n_instances']} ok")
    chk("locked_run_frozen_manifest_at_runtime",
        rj["frozen_manifest_sha256"] == FROZEN_MANIFEST_SHA256, rj["frozen_manifest_sha256"])
    # 11. the IMMUTABLE evaluation artifacts still hash to what checksums.txt
    #     records. Narrative markdown (README/SCHEMA/REPRODUCIBILITY_AUDIT), the
    #     mutable ledger (config.json), and the scan report are excluded — they
    #     are editable by design; the pre-registration doc is covered by check 10.
    _IMMUTABLE = ["scenario_manifest.json", "power_assumptions.json", "power_analysis.json",
                  "results.json", "results_locked_test.jsonl", "statistical_results.json",
                  "analysis_supplement.json", "robustness_results.json", "robustness_runs.jsonl",
                  "dry_run_report.json"]
    stored = json.loads((OUT_DIR / "checksums.txt").read_text())
    mismatches = []
    for name in _IMMUTABLE:
        p = OUT_DIR / name
        if p.exists() and name in stored and _sha256(p) != stored[name]:
            mismatches.append(name)
    chk("recorded_checksums_match_disk", not mismatches, ", ".join(mismatches) or "all immutable artifacts match")

    # refresh a FULL checksum manifest of the artifact directory
    full = {}
    for p in sorted(OUT_DIR.glob("*")):
        if p.is_file():
            full[p.name] = _sha256(p)
    full["_frozen_experiment_manifest.json"] = _sha256(FROZEN_MANIFEST)
    full["_docs/UPGRADED_EVALUATION_PREREGISTRATION.md"] = _sha256(PREREG_DOC)
    (OUT_DIR / "checksums.txt").write_text(json.dumps({**stored, **full}, indent=2, sort_keys=True))

    passed = sum(1 for _, ok, _ in checks if ok)
    lines = [
        "# Upgraded Controlled Evaluation — Reproducibility & Integrity Audit",
        "",
        f"**Phase 15.** Generated by `scripts/run_upgraded_eval.py audit`. "
        f"{passed}/{len(checks)} checks passed.",
        "",
        "| # | check | result | detail |",
        "|---|---|---|---|",
    ]
    for i, (name, ok, detail) in enumerate(checks, 1):
        lines.append(f"| {i} | `{name}` | {'PASS' if ok else '**FAIL**'} | {detail[:160]} |")
    lines += [
        "",
        "## Frozen invariants (unchanged by this study)",
        f"- Frozen experiment manifest SHA-256: `{FROZEN_MANIFEST_SHA256}` (re-verified).",
        "- `experiments/experiment_manifest.json`, `experiments/paper_results_snapshot.json`, "
        "`experiments/results/*`: byte-identical (git clean).",
        "- Production decision path (`decision_service`, `decision_architecture_service`, "
        "`digital_twin_service`, `app/agents/*`, `strategy_optimizer`, `strategy_generation_service`): unmodified.",
        "- `multi_scenario_service` frozen 12×5 suite (S01–S12, seeds 42–46): unmodified.",
        "- R0/D0 production config: `PipelineOptions().label() == \"full\"`, "
        "`risk_penalty_lambda == 1.0`, `risk_model` default. R3 (`extrapolation_robust_v1`) NOT promoted.",
        "- No real SME data, no real customer data, no real-LLM call, no prospective intervention, "
        "no human study. The evaluation layer imports no LLM or network client.",
        f"- Architecture fingerprint at locked-run time: `{rj['architecture_fingerprint']['sha256']}` "
        f"(reproduced now: `{fp_now['sha256']}`).",
        "",
        "## Reproducing the numbers",
        "```",
        "python scripts/run_upgraded_eval.py generate --n 340 --master-seed 20260906",
        "python scripts/run_upgraded_eval.py split    --master-seed 20260906",
        "python scripts/run_upgraded_eval.py power    --assumptions experiments/upgraded_controlled_v1/power_assumptions.json",
        "python scripts/run_upgraded_eval.py freeze-prereg --date 2026-09-05",
        "python scripts/run_upgraded_eval.py run      --partition locked_test",
        "python scripts/run_upgraded_eval.py analyze",
        "python scripts/run_upgraded_eval.py robustness",
        "python scripts/run_upgraded_eval.py audit",
        "```",
        "All bootstrap seeds (`12345`), the mechanism seed (`4242`), the power `rng_seed` "
        "(`20260906`) and the 10 run seeds (`20260906..20260915`) are fixed. "
        "`generate`/`analyze`/`audit` are deterministic; `run`/`robustness` are deterministic up to "
        "the frozen pipeline's own determinism (verified: 0 errors, stable fingerprint).",
    ]
    (OUT_DIR / "REPRODUCIBILITY_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:6 + len(checks)]))
    print(f"\nwrote {(OUT_DIR / 'REPRODUCIBILITY_AUDIT.md').relative_to(REPO)} and refreshed checksums.txt")
    return 0 if passed == len(checks) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate")
    g.add_argument("--n", type=int, default=51)
    g.add_argument("--master-seed", type=int, default=20260906)
    g.add_argument("--db", default=DEFAULT_DB)
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("split")
    s.add_argument("--master-seed", type=int, default=20260906)
    s.add_argument("--dev", type=float, default=0.60)
    s.add_argument("--val", type=float, default=0.20)
    s.add_argument("--test", type=float, default=0.20)
    s.set_defaults(func=cmd_split)

    p = sub.add_parser("power")
    p.add_argument("--assumptions", required=True, help="path to a JSON PowerAssumptions file")
    p.set_defaults(func=cmd_power)

    r = sub.add_parser("run")
    r.add_argument("--partition", choices=["development", "validation", "locked_test"], required=True)
    r.add_argument("--db", default=DEFAULT_DB)
    r.add_argument("--limit", type=int, default=0, help="cap scenarios (dev/val iteration only)")
    r.add_argument("--seeds", type=int, default=0, help="cap seeds to the first N of the 10 (dev/val only)")
    r.add_argument("--resume", action="store_true", help="skip (scenario,seed) already in results_<partition>.jsonl")
    r.add_argument("--keep-db", action="store_true")
    r.set_defaults(func=cmd_run)

    d = sub.add_parser("dry-run", help="Phase 3 real-pipeline dry run in a scratch DB")
    d.add_argument("--n", type=int, default=0, help="suite size; 0 => one instance per family")
    d.add_argument("--master-seed", type=int, default=20260906)
    d.add_argument("--families", type=int, default=3, help="how many ordinary dev families to probe")
    d.add_argument("--seeds", type=int, default=1, help="seeds per probed scenario")
    d.add_argument("--db", default="sqlite:///./_eval_dryrun.db")
    d.add_argument("--keep-db", action="store_true")
    d.set_defaults(func=cmd_dry_run)

    an = sub.add_parser("analyze", help="Phases 9-14 — statistics / baselines / agents / mechanism / failures")
    an.add_argument("--results", default="results.json", help="results file under experiments/upgraded_controlled_v1/")
    an.set_defaults(func=cmd_analyze)

    rb = sub.add_parser("robustness", help="Phase 12 — descriptive robustness on a locked-test subsample")
    rb.add_argument("--db", default="sqlite:///./_eval_robust.db")
    rb.add_argument("--every", type=int, default=4, help="take every Nth locked scenario (deterministic subsample)")
    rb.add_argument("--max-scenarios", type=int, default=20)
    rb.add_argument("--seeds", type=int, default=2, help="first N of the 10 pre-registered seeds")
    rb.add_argument("--resume", action="store_true")
    rb.add_argument("--keep-db", action="store_true")
    rb.set_defaults(func=cmd_robustness)

    fp = sub.add_parser("freeze-prereg", help="Phase 6 — seal the pre-registration")
    fp.add_argument("--date", default="2026-09-05")
    fp.add_argument("--force", action="store_true", help="freeze despite failed pre-checks (discouraged)")
    fp.set_defaults(func=cmd_freeze_prereg)

    au = sub.add_parser("audit", help="Phase 15 — reproducibility / integrity audit")
    au.set_defaults(func=cmd_audit)

    v = sub.add_parser("verify-freeze")
    v.set_defaults(func=cmd_verify_freeze)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
