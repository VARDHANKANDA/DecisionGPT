"""E-COST (decisiongpt_architecture_v1): end-to-end latency and invocation counts of the A/B/C/D workflows on the locked R1 scenarios (NEW measurement).

Uses the frozen evaluation code UNCHANGED and read-only: the R1 harness semantics (``r1_dt`` installed for the instance, same scenarios, same seed), a scratch in-memory SQLite database,
no production state. Only wrappers that time and count calls are added around existing functions (in this process only; nothing is written to the repository except the JSONL below).

    python research/decisiongpt_architecture_v1/analysis/cost_measurement.py main        # 408 locked scenarios x first locked seed
    python research/decisiongpt_architecture_v1/analysis/cost_measurement.py repeats      # 48-scenario subset, 2 more repeats

Output (append-only, resumable): research/decisiongpt_architecture_v1/results/cost_measurement.jsonl
No language-model request is possible (the AI key is removed in this process); the number of attempted requests is counted and expected to be 0.
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO), str(REPO / "backend"), str(REPO / "scripts")]

OUTDIR = REPO / "research" / "decisiongpt_architecture_v1" / "results"
OUT = OUTDIR / "cost_measurement.jsonl"
STORED = REPO / "experiments" / "r1" / "results.json"

PHASE = {"cur": "other"}
COUNTS: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
TIMES: dict[str, float] = defaultdict(float)
SIMT: dict[str, float] = defaultdict(float)      # seconds spent inside dts.simulate_strategy, by the phase that called it


def _sim_timed(fn):
    def wrapper(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            SIMT[PHASE["cur"]] += time.perf_counter() - t0
    return _counted_wrap(fn, wrapper)


def _counted_wrap(fn, wrapper):
    def w(*a, **k):
        _count("simulate_strategy_calls")
        return wrapper(*a, **k)
    return w


def _count(name):
    COUNTS[PHASE["cur"]][name] += 1


def _timed(phase, fn):
    def wrapper(*a, **k):
        prev = PHASE["cur"]
        PHASE["cur"] = phase
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            TIMES[phase] += time.perf_counter() - t0
            PHASE["cur"] = prev
    return wrapper


def _counted(name, fn):
    def wrapper(*a, **k):
        _count(name)
        return fn(*a, **k)
    return wrapper


def main(mode: str) -> int:
    import hashlib

    import run_eval_r1 as r1
    import run_upgraded_eval as v1
    from app.core.config import get_settings
    from app.evaluation import harness as base_h
    from app.evaluation.r1 import scenario_families as r1sf
    from app.evaluation.r1.r1_dt import r1_dt_active
    from app.analytics import digital_twin_service as dts
    from app.analytics import forecast_service
    from app.agents import business_analyst, financial_advisor, risk_manager, single_agent
    from app.services import decision_service, model_registry_service
    from app.services import llm_service as llm_mod
    from app.services import openai_client as oc

    get_settings().openai_api_key = None                      # no language-model request can be sent from this process
    r1._guard_frozen()
    in_hash = hashlib.sha256(STORED.read_bytes()).hexdigest()

    scen, man = r1._rebuild("locked_test")
    seeds = v1.SEEDS
    stored = {}
    for rec in json.loads(STORED.read_text(encoding="utf-8"))["records"]:
        stored[(rec["scenario_id"], rec["seed"])] = rec["result"]
    if mode == "repeats":
        by_fam: dict[str, list] = defaultdict(list)
        for s in scen:
            by_fam[s.family_id].append(s)
        subset = [s for fam in sorted(by_fam) for s in sorted(by_fam[fam], key=lambda x: x.scenario_id)[:4]]
        plan = [(s, seeds[0], rep) for rep in (1, 2) for s in subset]
    else:
        plan = [(s, seeds[0], 0) for s in scen]

    done = set()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        for ln in OUT.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                done.add((r["scenario_id"], r["seed"], r["repeat"]))

    # wrappers: times and counts only (no behavioural change)
    base_h._sim_all = _timed("shared_sim", base_h._sim_all)
    base_h._agent_scores = _timed("diagnostics", base_h._agent_scores)
    decision_service.analyze_goal = _timed("D", decision_service.analyze_goal)
    forecast_service.run_recursive_forecast = _counted("model_forecast_runs", forecast_service.run_recursive_forecast)
    for mod, key in ((business_analyst, "agent_BA"), (financial_advisor, "agent_FA"), (risk_manager, "agent_RM"), (single_agent, "agent_single")):
        mod.evaluate = _counted(key, mod.evaluate)
    oc.OpenAIClient._request = _counted("llm_requests_attempted", oc.OpenAIClient._request)
    for m in ("decide", "explain", "generate_strategy_explanation", "evaluate_agent", "generate_business_response", "parse_goal"):
        setattr(llm_mod.LLMService, m, _counted(f"llm_facade_{m}", getattr(llm_mod.LLMService, m)))

    db, engine = v1._scratch_session("sqlite://")
    t_start = time.perf_counter()
    n_new = 0
    try:
        model_registry_service.sync_from_file_registry(db)
        with OUT.open("a", encoding="utf-8") as fh:
            for i, (sc, seed, rep) in enumerate(plan, 1):
                if (sc.scenario_id, seed, rep) in done:
                    continue
                COUNTS.clear()
                TIMES.clear()
                SIMT.clear()
                PHASE["cur"] = "other"
                with r1_dt_active(sc):
                    orig_sim = dts.simulate_strategy
                    dts.simulate_strategy = _sim_timed(orig_sim)
                    t0 = time.perf_counter()
                    try:
                        res = base_h.run_instance(db, sc, seed=seed, realise_history=r1sf.realise_history)
                        err = None
                    except Exception as exc:                                   # recorded, never hidden
                        res, err = None, f"{type(exc).__name__}: {exc}"
                    total = time.perf_counter() - t0
                    dts.simulate_strategy = orig_sim
                rec = {"scenario_id": sc.scenario_id, "family_id": sc.family_id, "seed": seed, "repeat": rep, "error": err, "instance_total_s": round(total, 4),
                       "phase_seconds": {k: round(v, 5) for k, v in TIMES.items()}, "sim_seconds_by_phase": {k: round(v, 5) for k, v in SIMT.items()}, "counts": {k: dict(v) for k, v in COUNTS.items()}}
                if res is not None:
                    c = asdict(res)["conditions"]
                    rec["stage_latency_s"] = {k: c[k]["latency_seconds"] for k in c}
                    rec["regret"] = {k: c[k]["primary_regret"] for k in c}
                    rec["selected"] = {k: c[k]["selected_action_key"] for k in c}
                    rec["status"] = {k: c[k]["status"] for k in c}
                    st = stored.get((sc.scenario_id, seed))
                    rec["matches_stored_locked_run"] = bool(st is not None and all(st["conditions"][k]["primary_regret"] == c[k]["primary_regret"] and st["conditions"][k]["selected_action_key"] == c[k]["selected_action_key"] for k in c))
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                n_new += 1
                if n_new % 10 == 0:
                    el = time.perf_counter() - t_start
                    print(f"[{mode}] {i}/{len(plan)} new={n_new} elapsed={el:.0f}s eta={el / n_new * (len(plan) - i):.0f}s", flush=True)
    finally:
        db.close()
        engine.dispose()
    out_hash = hashlib.sha256(STORED.read_bytes()).hexdigest()
    assert in_hash == out_hash, "stored R1 results changed during the run"
    print(f"done {mode}: {n_new} new instances; stored R1 results hash unchanged ({in_hash[:16]})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "main"))
