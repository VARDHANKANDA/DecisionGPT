"""Read-only status of the POS LLM evaluation for the Research Console.

Reads files under ``research/llm_evaluation/`` and the process LLM settings. It never runs anything and never
fabricates: with no research run it reports "not evaluated" (no zeros, no sample numbers).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "research" / "llm_evaluation"
SPEC_PATH = EVAL_DIR / "tasks" / "tasks_v1.json"
GT_DIR = EVAL_DIR / "ground_truth"
RUNS_DIR = EVAL_DIR / "runs"
RAW_ZIP = ROOT / "data" / "external" / "india_pos_register" / "raw" / "retail-sales-register-data.zip"

AUDIT_PATH = EVAL_DIR / "audit" / "architecture_audit.json"

LABELS = {
    "blocked_production_path": "Blocked — production chat path not LLM-powered",
    "blocked_provider_not_configured": "Blocked — OPENAI_API_KEY not configured",
    "not_configured": "Not configured",
    "ready_to_run": "Ready to run",
    "running": "Running",
    "completed": "Completed",
    "partial": "Partially completed",
    "failed": "Failed",
}


def _json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _active_provider() -> str | None:
    return "openai" if get_settings().llm_enabled else None


def _price_for(model: str | None) -> dict | None:
    if not model:
        return None
    models = (_json(EVAL_DIR / "pricing.json") or {}).get("models") or {}
    if model in models:
        return models[model]
    fam = [k for k in models if model.startswith(k + "-")]
    return models[max(fam, key=len)] if fam else None


def _spec_hash(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _runs() -> list[dict]:
    out = []
    if RUNS_DIR.exists():
        for d in sorted(RUNS_DIR.iterdir()):
            meta = _json(d / "metadata.json") if d.is_dir() else None
            if meta:
                out.append(meta)
    return out


VERIFY_DIR = EVAL_DIR / "live_verification"
GATE_PATH = EVAL_DIR / "audit" / "readiness_gate.json"
# Published list price of the provider that produced the run (input tokens only for Jev). An ESTIMATE input - the provider console is the
# billing record, and the provider's "credit" unit is not defined in its public documentation.


def _run_kind(m: dict) -> str:
    if m.get("status") == "BLOCKED":
        return "blocked"
    if m.get("mock"):
        return "mock_validation"
    if m.get("mode") == "smoke":
        return "plumbing_check"
    if m.get("research_result"):
        return "live_evaluation"
    return "other"


def _run_history(runs: list[dict]) -> list[dict]:
    """Every stored run, newest first, labelled by what it actually is. Read from metadata.json only."""
    rows = []
    for m in runs:
        llm = m.get("llm") or {}
        rows.append({
            "run_id": m.get("run_id"), "kind": _run_kind(m), "status": m.get("status"), "mode": m.get("mode"),
            "research_result": bool(m.get("research_result")), "mock": bool(m.get("mock")),
            "created_utc": m.get("created_utc"), "finished_utc": m.get("finished_utc"),
            "planned_attempts": m.get("planned_attempts"), "completed_attempts": m.get("completed_attempts"),
            "n_tasks": m.get("n_tasks"), "repeats": m.get("repeats"),
            "run_type": m.get("run_type"),
            "tasks_attempted": len((m.get("selection") or {}).get("task_ids_attempted") or []) or m.get("n_tasks"),
            "tasks_in_spec": (m.get("selection") or {}).get("tasks_in_frozen_spec"),
            "provider": llm.get("provider"), "model": llm.get("model") or llm.get("model_requested"),
            "errors": m.get("n_attempt_errors"), "note": m.get("note") or m.get("reason"),
        })
    return sorted(rows, key=lambda r: r["created_utc"] or "", reverse=True)


def _live_verification() -> dict | None:
    """The stored connectivity check(s): real requests, but NOT an evaluation. Absent -> None (nothing is implied)."""
    recs = []
    if VERIFY_DIR.exists():
        for p in sorted(VERIFY_DIR.glob("*.json")):
            d = _json(p)
            if d and d.get("record_type") == "connectivity_verification":
                recs.append(d)
    if not recs:
        return None
    reqs = [r for rec in recs for r in rec.get("requests", [])]
    return {
        "records": len(recs), "requests_total": len(reqs), "latest_date": recs[-1].get("date"), "provider": recs[-1].get("provider"),
        "all_http_200": all(r.get("http_status") == 200 for r in reqs) if reqs else None,
        "requests": reqs, "does_not_show": recs[-1].get("does_not_show", []), "summary": recs[-1].get("summary"),
    }


def _run_plan(spec: dict | None, runs: list[dict], runnable: bool) -> dict:
    """What a full frozen run would involve. Token and cost figures come only from a previous run of the ACTIVE provider and model;
    with none, they are reported as not available instead of being borrowed from another provider."""
    tasks = (spec or {}).get("tasks", [])
    repeats = (spec or {}).get("repeats_per_task") or 0
    attempts = len(tasks) * repeats
    primary = sum(1 for t in tasks if t["track"] == "primary") * repeats
    s = get_settings()
    provider, model = _active_provider(), (s.openai_model if s.llm_enabled else None)
    in_per = out_per = None
    basis_run = None
    for m in sorted(runs, key=lambda x: x.get("created_utc") or "", reverse=True):
        if _run_kind(m) != "live_evaluation" or (m.get("llm") or {}).get("provider") != provider:
            continue
        sm = _run_summary(m["run_id"], m)
        done = m.get("completed_attempts") or 0
        if done and sm.get("input_tokens") is not None and sm.get("output_tokens") is not None:
            # per ATTEMPT (all of its requests: classification plus any explanation), because the plan is expressed in attempts
            in_per, out_per, basis_run = sm["input_tokens"] / done, sm["output_tokens"] / done, m["run_id"]
            break
    price = _price_for(model)
    est_in = round(in_per * attempts) if in_per else None
    est_cost = None
    if in_per is not None and price and attempts:
        est_cost = round(attempts * (in_per * price["input_per_million_usd"] + out_per * price["output_per_million_usd"]) / 1_000_000, 4)
    return {
        "provider": provider, "model": model,
        "tasks": len(tasks), "repeats_per_task": repeats, "planned_attempts": attempts, "primary_attempts": primary,
        "provider_requests_per_attempt": 2 if get_settings().analytics_explain_enabled else 1,  # classification (+ one explanation)
        "measured_input_tokens_per_attempt": round(in_per, 1) if in_per else None,
        "measured_input_tokens_per_request": round(in_per, 1) if in_per else None,  # kept for older clients: now per attempt
        "estimated_input_tokens": est_in,
        "estimated_cost_usd_at_list_price": est_cost,
        "estimate_basis": (f"attempts x the mean tokens per ATTEMPT (all its requests) measured in {basis_run} x the published price of {model}" if basis_run else
                           "no live run of the active provider exists yet, so no token or cost estimate is made"),
        "runnable_now": runnable,
    }


def _baselines() -> list[dict]:
    gate = _json(GATE_PATH) or {}
    b = gate.get("baseline") or {}
    return [{
        "id": "B2", "name": "Reference tool-use system (a model writing pandas code over the same data)",
        "runs_on_provider": bool(b.get("runs_on_provider", b.get("runs_on_jev", False))),
        "reason": ("Not implemented for the current provider. It is reported as not run - no score is shown or implied."
                   if not b.get("runs_on_provider", b.get("runs_on_jev", False)) else "Runnable."),
    }]


def _per_task(run_id: str) -> list[dict]:
    """Per-task outcomes aggregated from a stored run's task_results.jsonl (only used for non-mock research runs)."""
    path = RUNS_DIR / run_id / "task_results.jsonl"
    agg: dict[str, dict] = {}
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                t = agg.setdefault(r.get("task_id"), {"task_id": r.get("task_id"), "category": r.get("category"), "track": r.get("track"),
                                                     "question": r.get("question"), "attempts": 0, "correct": 0, "excluded": 0, "errors": 0,
                                                     "outcomes": {}, "paths": {}, "path_classes": {}, "_lat": [], "answer_excerpt": None, "ground_truth": r.get("truth"),
                                                     "failure_category": None})
                t["attempts"] += 1
                sc = r.get("score") or {}
                t["correct"] += 1 if sc.get("correct") else 0
                t["excluded"] += 1 if r.get("excluded_from_accuracy") else 0
                t["errors"] += 1 if r.get("error") else 0
                oc = sc.get("outcome") or ("error" if r.get("error") else "unscored")
                t["outcomes"][oc] = t["outcomes"].get(oc, 0) + 1
                t["paths"][str(r.get("path"))] = t["paths"].get(str(r.get("path")), 0) + 1
                pc = str(r.get("path_class"))
                t["path_classes"][pc] = t["path_classes"].get(pc, 0) + 1
                t["failure_category"] = r.get("failure_category") or t["failure_category"]
                if isinstance(r.get("answer"), str):
                    t["answer_excerpt"] = " ".join(r["answer"].split())[:200]
                if isinstance(r.get("latency_s"), (int, float)):
                    t["_lat"].append(r["latency_s"])
    except OSError:
        return []
    out = []
    for t in agg.values():
        lat = sorted(t.pop("_lat"))
        t["median_latency_s"] = round(lat[len(lat) // 2], 2) if lat else None
        out.append(t)
    return sorted(out, key=lambda x: str(x["task_id"]))


def _run_summary(run_id: str, meta: dict) -> dict:
    """Counts straight from the stored per-attempt rows and metadata (never from prose). Safe for any stored run."""
    path = RUNS_DIR / run_id / "task_results.jsonl"
    rows = []
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass

    def block(sub: list[dict]) -> dict:
        outcomes: dict[str, int] = {}
        for r in sub:
            oc = (r.get("score") or {}).get("outcome") or ("error" if r.get("error") else "unscored")
            outcomes[oc] = outcomes.get(oc, 0) + 1
        return {"attempts": len(sub), "correct": sum(1 for r in sub if (r.get("score") or {}).get("correct")),
                "excluded": sum(1 for r in sub if r.get("excluded_from_accuracy")), "errors": sum(1 for r in sub if r.get("error")),
                "outcomes": outcomes}

    sel = meta.get("selection") or {}
    ident = meta.get("model_identity") or {}
    calls = [r.get("llm_summary") or {} for r in rows]
    tin = sum(c.get("input_tokens") or 0 for c in calls)
    tout = sum(c.get("output_tokens") or 0 for c in calls)
    priced = [r.get("cost_usd") for r in rows if isinstance(r.get("cost_usd"), (int, float))]
    return {
        "run_type": meta.get("run_type") or ("full" if not meta.get("mock") and meta.get("research_result") else None),
        "note": meta.get("note"),
        "tasks_in_spec": sel.get("tasks_in_frozen_spec") or meta.get("n_tasks"),
        "task_ids_attempted": sel.get("task_ids_attempted"),
        "task_ids_not_attempted": sel.get("task_ids_not_attempted"),
        "repeats_used": sel.get("repeats_used") or meta.get("repeats"),
        "repeats_frozen": sel.get("repeats_frozen"),
        "primary": block([r for r in rows if r.get("track") == "primary"]),
        "supplementary": block([r for r in rows if r.get("track") == "supplementary"]),
        "answer_paths": meta.get("decisiongpt_answer_paths"),
        "provider_requests": ident.get("n_provider_calls_recorded"),
        "attempt_errors": meta.get("n_attempt_errors"),
        "models_returned": ident.get("models_returned_by_provider"),
        "input_tokens": tin if calls else None,
        "output_tokens": tout if calls else None,
        "estimated_cost_usd_at_list_price": round(sum(priced), 6) if priced and len(priced) == len(rows) else None,
        "spec_sha256": meta.get("spec_sha256"),
        "manifest_sha256": meta.get("manifest_sha256"),
    }


def _live_coverage(runs: list[dict], spec: dict | None) -> list[dict] | None:
    """Coverage of the frozen tasks by genuine (non-mock) research runs, GROUPED BY PROVIDER. Results from different providers are never
    pooled: each provider is reported on its own. Reads each run's stored metadata and rows; nothing is merged into a new record."""
    live = [m for m in runs if _run_kind(m) == "live_evaluation"]
    if not live:
        return None
    all_ids = [t["task_id"] for t in (spec or {}).get("tasks", [])]
    groups: dict[str, list[dict]] = {}
    for m in live:
        groups.setdefault((m.get("llm") or {}).get("provider") or "unknown", []).append(m)
    out = []
    for provider, ms in groups.items():
        attempted: set[str] = set()
        per_run = []
        repeats_max = 0
        prim_c = prim_n = 0
        for m in sorted(ms, key=lambda x: x.get("created_utc") or ""):
            sm = _run_summary(m["run_id"], m)
            ids = sm.get("task_ids_attempted") or []
            attempted |= set(ids)
            repeats_max = max(repeats_max, sm.get("repeats_used") or 0)
            prim_c += sm["primary"]["correct"]
            prim_n += sm["primary"]["attempts"]
            per_run.append({"run_id": m["run_id"], "run_type": sm.get("run_type"), "tasks": len(ids), "repeats": sm.get("repeats_used"),
                            "primary_correct": sm["primary"]["correct"], "primary_attempts": sm["primary"]["attempts"],
                            "provider_requests": sm.get("provider_requests"), "input_tokens": sm.get("input_tokens"),
                            "model": ", ".join(sm.get("models_returned") or []) or None,
                            "estimated_cost_usd_at_list_price": sm.get("estimated_cost_usd_at_list_price")})
        costs = [r["estimated_cost_usd_at_list_price"] for r in per_run]
        out.append({
            "provider": provider,
            "is_active_provider": provider == _active_provider(),
            "runs": per_run,
            "tasks_in_spec": len(all_ids),
            "tasks_attempted_at_least_once": len(attempted),
            "task_ids_never_attempted": [i for i in all_ids if i not in attempted],
            "repeats_frozen": (spec or {}).get("repeats_per_task"),
            "max_repeats_any_run": repeats_max,
            "primary_correct_sum": prim_c,
            "primary_attempts_sum": prim_n,
            "provider_requests_sum": sum(r["provider_requests"] or 0 for r in per_run),
            "estimated_cost_usd_sum": round(sum(costs), 6) if all(isinstance(c, (int, float)) for c in costs) else None,
            "note": "Arithmetic over this provider's separate stored runs (each is its own record). Providers are never pooled. "
                    "One repeat per task is not the frozen five-repeat protocol.",
        })
    return sorted(out, key=lambda c: (not c["is_active_provider"], c["provider"]))


def build_status() -> dict[str, Any]:
    s = get_settings()
    llm = {"enabled": bool(s.llm_enabled), "provider": "openai" if s.llm_enabled else None, "model": s.openai_model if s.llm_enabled else None}

    spec = _json(SPEC_PATH)
    gt = None
    if spec:
        gt = _json(GT_DIR / f"ground_truth_{_spec_hash(spec)[:12]}.json")
    infra = {
        "task_spec": bool(spec),
        "ground_truth": bool(gt and gt.get("spec_sha256") == _spec_hash(spec or {})),
        "dataset_present": RAW_ZIP.exists(),
    }
    infra["ready"] = all(infra.values())

    runs = _runs()
    research_runs = [m for m in runs if m.get("research_result")]
    latest = research_runs[-1] if research_runs else None
    blocked = [m for m in runs if m.get("status") == "BLOCKED"]
    mocks = [m for m in runs if m.get("mock") and m.get("run_type") != "partial_pilot"] or [m for m in runs if m.get("mock")]
    mock_validation = None
    if mocks:
        mv = mocks[-1]
        mock_validation = {"run_id": mv["run_id"], "status": mv.get("status"), "completed_attempts": mv.get("completed_attempts"),
                           "planned_attempts": mv.get("planned_attempts"), "finished_utc": mv.get("finished_utc"),
                           "note": "Mock infrastructure validation with a fake provider - NOT research results."}

    # Two different conditions: "the production chat has no available LLM analytics path" vs "no LLM provider is configured".
    audit = _json(AUDIT_PATH)
    prod_path = {"status": "unknown", "detail": "No architecture audit file found."}
    if audit:
        path_audit = audit.get("llm_analytics_path") or {}
        implemented = bool(path_audit.get("implemented"))
        enabled = bool(s.analytics_llm_enabled)
        status = "available" if (implemented and enabled) else ("disabled" if implemented else "not_connected_to_analytics_chat")
        routing = audit.get("frozen_question_routing") or {}
        total = routing.get("n_total")
        prod_path = {
            "status": status,
            "detail": {
                "available": ("Business questions are classified by the OpenAI model (schema-constrained labels) and assembled with deterministic value extraction "
                              "into a validated structured request, calculated by the deterministic query engine, and answered from the verified "
                              "result. It needs an OPENAI_API_KEY; without one the standard (fixed-intent) assistant answers."),
                "disabled": "The LLM analytics path is implemented but switched off (ANALYTICS_LLM_ENABLED=false); the standard assistant answers.",
                "not_connected_to_analytics_chat": "Business-analytics chat is a fixed-intent router with template answers; the LLM only rephrases a few intents.",
            }[status],
            "frozen_questions_total": total,
            "frozen_questions_that_reach_the_llm_interpreter_when_configured": (audit.get("frozen_questions_that_reach_the_llm_interpreter_when_configured") if status == "available" else 0),
            "legacy_router_recognizes": (total or 0) - (routing.get("n_unrecognized") or 0),
            "audit_date": audit.get("audit_date"),
        }
    path_available = prod_path["status"] == "available"
    blockers = ([] if path_available else ["production_path_not_llm_powered"] if prod_path["status"] != "unknown" else []) + ([] if llm["enabled"] else ["provider_not_configured"])

    if latest:
        state = {"RUNNING": "running", "COMPLETED": "completed", "PARTIAL": "partial", "PARTIALLY_COMPLETED": "partial", "FAILED": "failed"}.get(latest["status"], "failed")
    elif prod_path["status"] in ("not_connected_to_analytics_chat", "disabled"):
        state = "blocked_production_path"
    elif path_available and not llm["enabled"]:
        state = "blocked_provider_not_configured"
    elif llm["enabled"] and infra["ready"]:
        state = "ready_to_run"
    else:
        state = "not_configured"

    latest_block = None
    if latest:
        metrics = _json(RUNS_DIR / latest["run_id"] / "metrics.json")
        latest_block = {
            "run_id": latest["run_id"], "status": latest["status"], "created_utc": latest.get("created_utc"), "finished_utc": latest.get("finished_utc"),
            "completed_attempts": latest.get("completed_attempts"), "planned_attempts": latest.get("planned_attempts"),
            "llm": latest.get("llm"), "systems": latest.get("systems"), "conditions": latest.get("conditions"), "repeats": latest.get("repeats"),
            "metrics": (metrics or {}).get("metrics"),
            "per_task": _per_task(latest["run_id"]),
            "summary": _run_summary(latest["run_id"], latest),
        }

    verification = _live_verification()
    return {
        "run_history": _run_history(runs),
        "live_coverage": _live_coverage(runs, spec),
        "live_verification": verification,
        "run_plan": _run_plan(spec, runs, runnable=(not blockers) and infra["ready"]),
        "baselines": _baselines(),
        "state": state,
        "label": LABELS[state],
        "evaluation": "run" if latest else "not_run",
        "evaluated": bool(latest and latest_block and latest_block.get("metrics")),
        "llm": llm,
        "production_llm_path": prod_path,
        "blockers": blockers,
        "infrastructure": infra,
        "dataset": (spec or {}).get("dataset"),
        "tasks": {
            "n": len((spec or {}).get("tasks", [])),
            "n_primary": sum(1 for t in (spec or {}).get("tasks", []) if t["track"] == "primary"),
            "n_supplementary": sum(1 for t in (spec or {}).get("tasks", []) if t["track"] == "supplementary"),
            "repeats_per_task": (spec or {}).get("repeats_per_task"),
            "categories": sorted({t["category"] for t in (spec or {}).get("tasks", [])}),
        },
        "view_rules": (spec or {}).get("view_rules"),
        "latest_run": latest_block,
        "mock_validation": mock_validation,
        "last_blocked_attempt": ({"run_id": blocked[-1]["run_id"], "created_utc": blocked[-1].get("created_utc"), "reason": blocked[-1].get("reason")} if blocked else None),
        "class_counts": ((audit or {}).get("task_compatibility") or {}).get("class_counts"),
        "limitations": [
            "Provenance of the POS data is not independently verified; it is presented as real Indian POS data only on the basis of its observed structure and content.",
            "Licence CC BY-NC-SA 4.0. One store, 89 days: not representative of Indian SMEs or Indian retail generally.",
            "Scope: objective descriptive analytics questions only - not churn, causal, pricing, forecasting validity, or business outcomes.",
        ],
    }


def run_detail(run_id: str) -> dict | None:
    """One stored run, attempt by attempt, for the question / answer / expected table. Read-only; None for an unknown or malformed id."""
    import re

    if not re.fullmatch(r"[A-Za-z0-9_]{6,80}", run_id or ""):
        return None
    d = RUNS_DIR / run_id
    meta = _json(d / "metadata.json")
    if not meta:
        return None
    rows = []
    try:
        with (d / "task_results.jsonl").open(encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                sc = r.get("score") or {}
                rows.append({
                    "task_id": r.get("task_id"), "repeat": r.get("repeat"), "track": r.get("track"), "category": r.get("category"),
                    "question": r.get("question"), "answer": r.get("answer"), "expected": r.get("truth"),
                    "outcome": sc.get("outcome") or ("error" if r.get("error") else "unscored"), "correct": bool(sc.get("correct")),
                    "path": r.get("path"), "path_class": r.get("path_class"), "failure_category": r.get("failure_category"),
                    "excluded_from_accuracy": bool(r.get("excluded_from_accuracy")), "error": r.get("error"),
                    "latency_s": r.get("latency_s"), "input_tokens": (r.get("llm_summary") or {}).get("input_tokens"),
                    "output_tokens": (r.get("llm_summary") or {}).get("output_tokens"), "cost_usd": r.get("cost_usd"),
                })
    except OSError:
        pass
    kind = _run_kind(meta)
    ident = meta.get("model_identity") or {}
    return {"run_id": run_id, "kind": kind, "status": meta.get("status"), "is_live_result": kind == "live_evaluation",
            "created_utc": meta.get("created_utc"), "finished_utc": meta.get("finished_utc"),
            "provider": (meta.get("llm") or {}).get("provider"), "model_requested": (meta.get("llm") or {}).get("model_configured"),
            "models_returned": ident.get("models_returned_by_provider"),
            "summary": _run_summary(run_id, meta), "attempts": rows,
            "technical": {"spec_sha256": meta.get("spec_sha256"), "manifest_sha256": meta.get("manifest_sha256"), "scorer_version": meta.get("scorer_version"),
                          "ground_truth_version": meta.get("ground_truth_version"), "conditions": meta.get("conditions"), "repeats": meta.get("repeats"),
                          "retry_policy": ident.get("retry_policy"), "view": meta.get("view"), "errors": meta.get("errors")}}
