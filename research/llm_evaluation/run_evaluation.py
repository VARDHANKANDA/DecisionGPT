"""Evaluation runner.

    python -m research.llm_evaluation.run_evaluation check     # verify data/spec/ground truth/scoring; no LLM needed
    python -m research.llm_evaluation.run_evaluation run       # the real evaluation; REFUSES (BLOCKED) unless OPENAI_API_KEY is configured
    python -m research.llm_evaluation.run_evaluation smoke     # plumbing check of the DecisionGPT path with NO LLM; never a research result
    python -m research.llm_evaluation.run_evaluation mock      # MOCK infrastructure validation (wire-level fake provider); never a research result
    python -m research.llm_evaluation.run_evaluation report RUN_ID

Run from the repository root with PYTHONPATH containing `backend` and `.` (see README).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import secrets
import subprocess
import sys
import time
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from research.llm_evaluation import prompts
from research.llm_evaluation.data_view import build_view, verify_raw_provenance
from research.llm_evaluation.ground_truth import compute_all, spec_sha256, write_ground_truth
from research.llm_evaluation import attempt_accounting, isolation
from research.llm_evaluation.llm_instrument import LLMRecorder, compact_calls, cost_usd
from research.llm_evaluation.metrics import summarize
from research.llm_evaluation.scoring import SCORER_VERSION, score_answer

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "tasks" / "tasks_v1.json"
GT_DIR = HERE / "ground_truth"
RUNS_DIR = HERE / "runs"
PRICING_PATH = HERE / "pricing.json"
ASOF = date(2025, 3, 31)
ROOT = HERE.parents[1]

# The frozen artefacts. If either differs the evaluation refuses to start (fail closed); nothing is "updated" to make it pass.
FROZEN_SPEC_SHA256 = "98f370377280c730938ccfd2db2d848335e98ce3419f149f4769c0a638f30146"
FROZEN_MANIFEST_SHA256 = "94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff"
MANIFEST_PATH = ROOT / "experiments" / "experiment_manifest.json"
SUPPORTED_PROVIDERS = ("openai",)
DEFAULT_CONDITIONS = "asof"  # the primary, reproducible condition. 'realclock' (real current date) is an explicit, non-reproducible opt-in.

# Every result must name the exact system under test. A research adapter is never "production DecisionGPT".
SYSTEM_LABELS = {
    "decisiongpt": ("DecisionGPT production chat, AI analytics path (the OpenAI model classifies the question into closed labels; deterministic code extracts "
                    "periods/products/limits -> validated structured request -> deterministic query engine -> verified result -> templated answer); any answer "
                    "served by the legacy fixed-intent router is flagged path=legacy_router and is NOT an AI answer - Target B (OpenAI)"),
    "llm_code_baseline": ("Reference tool-use system: a model writing pandas code; NOT executed by this harness (not implemented for the OpenAI provider); retained for the record "
                          "(NOT a simpler baseline, NOT DecisionGPT)"),
}

EXIT_OK, EXIT_FAIL, EXIT_BLOCKED = 0, 1, 3


# ----------------------------------------------------------------------------- configuration / preflight
def llm_status() -> dict:
    """What is ACTUALLY configured. Never filled in from defaults; the key itself is never reported, only its presence."""
    from app.core.config import get_settings

    s = get_settings()
    return {
        "enabled": bool(s.llm_enabled),
        "provider": "openai" if s.llm_enabled else None,
        "model_configured": s.openai_model if s.llm_enabled else None,
        "model_note": "the provider echoes the exact model snapshot that ran (recorded per call as model_returned)",
        "base_url": "https://api.openai.com" if s.llm_enabled else None,
        "api_key_present": bool(s.openai_api_key),
        "provider_supported": True if s.llm_enabled else None,
        "timeout_s": s.openai_timeout_seconds,
        "temperature": None,
        "temperature_note": "not set: requests carry no sampling parameter, so repeats are independent samples and no seed is supported",
    }


def load_spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def load_or_make_ground_truth(spec: dict) -> dict:
    h = spec_sha256(spec)[:12]
    p = GT_DIR / f"ground_truth_{h}.json"
    if not p.exists():
        p = write_ground_truth(SPEC_PATH, GT_DIR)
    gt = json.loads(p.read_text(encoding="utf-8"))
    if gt["spec_sha256"] != spec_sha256(spec):
        raise RuntimeError("ground truth was computed from a different spec")
    return gt


def preflight() -> dict:
    spec = load_spec()
    view, info = build_view()
    gt = load_or_make_ground_truth(spec)
    fresh = compute_all(spec, view, info)
    gt_matches = all(fresh["answers"][k]["answer"] == gt["answers"][k]["answer"] for k in gt["answers"])
    checks = {
        "raw_provenance": verify_raw_provenance(),
        "spec_sha256": spec_sha256(spec),
        "n_tasks": len(spec["tasks"]),
        "n_primary": sum(t["track"] == "primary" for t in spec["tasks"]),
        "n_supplementary": sum(t["track"] == "supplementary" for t in spec["tasks"]),
        "view": info.as_dict(),
        "view_matches_ground_truth_file": gt["view"]["view_sha256"] == info.view_sha256,
        "ground_truth_reproduces": gt_matches,
        "scorer_version": SCORER_VERSION,
        "prompt_version": prompts.PROMPT_VERSION,
    }
    problems = []
    checks["frozen_spec_unchanged"] = checks["spec_sha256"] == FROZEN_SPEC_SHA256
    if not checks["frozen_spec_unchanged"]:
        problems.append("FROZEN TASK SPECIFICATION CHANGED \u2014 EVALUATION BLOCKED.")
    manifest_sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest() if MANIFEST_PATH.exists() else None
    checks["manifest_sha256"] = manifest_sha
    checks["frozen_manifest_unchanged"] = manifest_sha == FROZEN_MANIFEST_SHA256
    if not checks["frozen_manifest_unchanged"]:
        problems.append("EXPERIMENT MANIFEST CHANGED \u2014 EVALUATION BLOCKED.")
    checks["evaluation_clock"] = _clock_self_test()
    if not checks["evaluation_clock"]["ok"]:
        problems.append("evaluation clock is not deterministic or leaks outside its scope")
    checks["retry_environment"] = _retry_environment()
    if not checks["retry_environment"]["ok"]:
        problems.append("the provider client no longer makes exactly one attempt per call; the pre-registered retry policy would be false")
    checks["adapter_available"] = _adapter_available()
    if not checks["adapter_available"]["ok"]:
        problems.append(f"DecisionGPT adapter unavailable: {checks['adapter_available']['error']}")
    if not checks["raw_provenance"]["ok"]:
        problems.append("raw POS file hash does not match the audited file")
    if not checks["view_matches_ground_truth_file"]:
        problems.append("evaluation view differs from the one the ground truth was computed on")
    if not gt_matches:
        problems.append("ground truth recomputation differs from the stored file")
    llm = llm_status()
    from research.llm_evaluation.audit import architecture as arch

    routed = arch.route_frozen_questions()
    path = arch.analytics_llm_path_status()
    from app.core.config import get_settings

    kill_switch_on = bool(get_settings().analytics_llm_enabled)
    available = bool(path["implemented"] and kill_switch_on)
    production_llm = {
        "frozen_questions_total": len(routed),
        "analytics_llm_path_implemented": path["implemented"],
        "analytics_llm_path_enabled": kill_switch_on,
        "frozen_questions_that_reach_the_llm_interpreter_when_configured": sum(1 for r in routed if len(r["question"]) <= 1000) if available else 0,
        "legacy_router_recognizes": sum(1 for r in routed if r["intent"] != "unrecognized"),
        "chat_path_llm_powered_for_evaluated_questions": available,
        "statement": ("The production chat has an AI analytics path (question -> model classification + deterministic extraction -> validated structured request -> "
                      "deterministic query engine -> verified result -> validated explanation); it needs OPENAI_API_KEY. Without one the legacy router answers." if available else
                      "The LLM analytics path is not available (not implemented or switched off): the legacy fixed-intent router answers, and no frozen question can reach an LLM call."),
    }
    blockers = []
    if not production_llm["chat_path_llm_powered_for_evaluated_questions"]:
        blockers.append("production_path_not_llm_powered")
    if not llm["enabled"]:
        blockers.append("provider_not_configured")
    else:
        if llm.get("provider_supported") is False:
            blockers.append("provider_not_supported")
        if not llm.get("model_configured"):
            blockers.append("model_not_configured")  # the exact model must be named and recorded
    return {"checks": checks, "llm": llm, "production_llm_path": production_llm, "blockers": blockers, "problems": problems,
            "ready_infrastructure": not problems, "ready_to_execute": (not problems) and not blockers}


def _clock_self_test() -> dict:
    """The evaluation clock must be deterministic and scoped: pinned inside the block, real outside, restored after an error."""
    from app.core import clock

    real = date.today()
    ok = True
    detail = []
    with clock.reference_date(ASOF):
        inside = clock.today()
        pinned_inside = clock.is_pinned()
    if inside != ASOF or not pinned_inside:
        ok = False
        detail.append("pin not applied")
    if clock.today() != real or clock.is_pinned():
        ok = False
        detail.append("pin leaked outside its block")
    try:
        with clock.reference_date(ASOF):
            raise RuntimeError("x")
    except RuntimeError:
        pass
    if clock.is_pinned():
        ok = False
        detail.append("pin not released after an exception")
    return {"ok": ok, "reference_date": ASOF.isoformat(), "mechanism": "app.core.clock.reference_date (ContextVar, scoped)", "detail": detail}


def _retry_environment() -> dict:
    """The OpenAI client has ONE request seam (``_request``), disables the SDK's own retries, and retries only errors that cannot
    have been processed (rate limit, connection failure), at most ``openai_max_retries`` (<= 2) times; a timeout is never retried.
    Verified structurally so the pre-registered policy cannot silently change."""
    import inspect

    from app.core.config import get_settings
    from app.services import openai_client

    src = inspect.getsource(openai_client.OpenAIClient)
    single_seam = src.count("self._request(") == 1 and "max_retries=0" in src and "tenacity" not in inspect.getsource(openai_client)
    timeout_not_retried = '"timeout", False' in src
    cap_ok = 0 <= int(get_settings().openai_max_retries) <= 2
    ok = bool(single_seam and timeout_not_retried and cap_ok)
    return {"ok": ok, "retry_policy": f"bounded: at most {int(get_settings().openai_max_retries)} retry for rate-limit / connection errors; timeouts and server errors are never retried",
            "single_request_seam": single_seam, "timeout_not_retried": timeout_not_retried, "retry_cap_ok": cap_ok}


def _adapter_available() -> dict:
    try:
        from research.llm_evaluation.audit import architecture as arch
        from research.llm_evaluation.systems.decisiongpt import DecisionGPTSystem  # noqa: F401

        st = arch.analytics_llm_path_status()
        return {"ok": bool(st["implemented"]), "error": None if st["implemented"] else "analytics path not structurally complete", "checks": st["checks"]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}


def _git_state() -> dict:
    def run(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()

    try:
        return {"commit": run("rev-parse", "HEAD"), "uncommitted_files": len([l for l in run("status", "--porcelain").splitlines() if l.strip()])}
    except Exception as exc:  # noqa: BLE001
        return {"commit": None, "error": f"{type(exc).__name__}"}


def _prompt_hashes() -> dict:
    import json as _json

    from research.llm_evaluation.isolation import expected_questions_payload

    h = lambda t: hashlib.sha256(t.encode("utf-8")).hexdigest()  # noqa: E731
    return {"interpreter_questions_sha256": h(_json.dumps(expected_questions_payload(), sort_keys=True, ensure_ascii=False)),
            "explainer_system_sha256": hashlib.sha256(__import__("app.services.openai_client", fromlist=["x"]).SYSTEM_EXPLAIN.encode("utf-8")).hexdigest(), "baseline_prompt_version": prompts.PROMPT_VERSION}


# ----------------------------------------------------------------------------- run
def _new_run_id(prefix: str = "run") -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{secrets.token_hex(4)}"


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _load_pricing() -> dict | None:
    if PRICING_PATH.exists():
        return json.loads(PRICING_PATH.read_text(encoding="utf-8")).get("models")
    return None


def _blocked_reason(pre: dict) -> str:
    parts = []
    if "production_path_not_llm_powered" in pre["blockers"]:
        parts.append("The production DecisionGPT chat has no available AI analytics path (not implemented or switched off), so the legacy fixed-intent router would answer")
    if "provider_not_configured" in pre["blockers"]:
        parts.append("OPENAI_API_KEY is not configured (the AI analytics path is implemented but cannot run without it)")
    return "; ".join(parts) + ". The evaluation was NOT executed and no results exist."


def blocked_run(pre: dict) -> Path:
    run_id = _new_run_id("blocked")
    d = RUNS_DIR / run_id
    _write_json(d / "metadata.json", {
        "run_id": run_id, "status": "BLOCKED", "research_result": False,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reason": _blocked_reason(pre),
        "blockers": pre["blockers"], "llm": pre["llm"], "production_llm_path": pre["production_llm_path"],
        "needed": (["An available LLM analytics path in DecisionGPT (check ANALYTICS_LLM_ENABLED and the implementation audit)"] if "production_path_not_llm_powered" in pre["blockers"] else [])
                  + (["OPENAI_API_KEY (server-side environment variable; never committed)"] if "provider_not_configured" in pre["blockers"] else []),
        "spec_sha256": pre["checks"]["spec_sha256"], "infrastructure_ready": pre["ready_infrastructure"], "problems": pre["problems"],
    })
    return d


def execute(*, mode: str, systems: list[str], conditions: list[str], limit_tasks: int | None = None, repeats_override: int | None = None,
            task_ids: list[str] | None = None, selection: dict | None = None, max_requests: int | None = None) -> Path:
    """mode: 'research' (needs a real LLM) | 'smoke' (no LLM; plumbing only) | 'mock' (wire-level MOCK provider; infrastructure validation only).
    smoke and mock are never research results."""
    if mode == "mock":
        from research.llm_evaluation import mock_llm

        spec = load_spec()
        q2t = {t["natural_language_question"]: t["task_id"] for t in spec["tasks"]}
        with mock_llm.mock_provider_active(q2t) as prov:
            return _execute(mode=mode, systems=["decisiongpt"], conditions=["asof"], limit_tasks=limit_tasks, repeats_override=repeats_override, mock=prov,
                            task_ids=task_ids, selection=selection, max_requests=max_requests)
    return _execute(mode=mode, systems=systems, conditions=conditions, limit_tasks=limit_tasks, repeats_override=repeats_override, mock=None,
                    task_ids=task_ids, selection=selection, max_requests=max_requests)


def _execute(*, mode: str, systems: list[str], conditions: list[str], limit_tasks: int | None, repeats_override: int | None, mock,
             task_ids: list[str] | None = None, selection: dict | None = None, max_requests: int | None = None) -> Path:
    from app.core.config import get_settings

    pre = preflight()
    if pre["blockers"] and mode in ("research", "mock"):
        raise SystemExit(f"blocked: {pre['blockers']}")
    if mode == "research" and "realclock" in conditions:
        print("NOTE: 'realclock' depends on today's date and is not reproducible; it is reported only as a secondary condition.")
    if pre["problems"]:
        raise SystemExit(f"preflight failed: {pre['problems']}")
    spec = load_spec()
    gt = load_or_make_ground_truth(spec)
    view, info = build_view()
    if task_ids:
        known = {t["task_id"] for t in spec["tasks"]}
        unknown = [i for i in task_ids if i not in known]
        if unknown or len(set(task_ids)) != len(task_ids):
            raise SystemExit(f"invalid --task-ids (unknown {unknown}, duplicates {len(set(task_ids)) != len(task_ids)})")
        tasks = [t for t in spec["tasks"] if t["task_id"] in set(task_ids)]  # frozen spec order; the spec itself is never edited
    else:
        tasks = spec["tasks"][:limit_tasks] if limit_tasks else spec["tasks"]
    repeats = repeats_override or spec["repeats_per_task"]
    is_subset = len(tasks) < len(spec["tasks"]) or repeats != spec["repeats_per_task"]
    if max_requests is not None and len(tasks) * repeats * max(1, len(conditions)) > max_requests:
        raise SystemExit(f"refused: the plan needs {len(tasks) * repeats * max(1, len(conditions))} requests but --max-requests is {max_requests}")
    products = sorted(view["product"].unique(), key=len, reverse=True)
    pricing = _load_pricing()
    if mode == "mock":
        from research.llm_evaluation import mock_llm

        pricing = mock_llm.MOCK_PRICING  # MOCK prices: exercises the cost plumbing; never real

    run_id = _new_run_id({"smoke": "smoke", "mock": "mock"}.get(mode, "run"))
    run_dir = RUNS_DIR / run_id
    (run_dir / "raw_outputs").mkdir(parents=True, exist_ok=True)
    meta = {
        "run_id": run_id, "mode": mode, "research_result": mode == "research", "mock": mode == "mock",
        "status": "RUNNING", "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": platform.python_version(), "platform": platform.platform(),
        "spec_sha256": spec_sha256(spec), "ground_truth_version": gt["ground_truth_version"], "scorer_version": SCORER_VERSION, "prompt_version": prompts.PROMPT_VERSION,
        "llm": pre["llm"], "production_llm_path": pre["production_llm_path"], "system_labels": SYSTEM_LABELS, "systems": systems, "conditions": conditions, "repeats": repeats, "n_tasks": len(tasks),
        "view": info.as_dict(), "dataset_disclosure": spec["dataset"],
        "pricing_supplied": bool(pricing), "pricing_is_mock": mode == "mock",
        "frozen_spec_sha256_expected": FROZEN_SPEC_SHA256, "manifest_sha256": pre["checks"]["manifest_sha256"],
        "git": _git_state(), "prompts": _prompt_hashes(),
        "evaluation_clock": {"conditions": {c: (ASOF.isoformat() if c == "asof" else "real current date (not reproducible; secondary)") for c in conditions},
                             "mechanism": "app.core.clock.reference_date (ContextVar, scoped to the condition)"},
        "repeat_design": {"repeats_per_task": repeats, "task_set_fixed_for_all_repeats": True, "task_loop": "for task: for repeat (same frozen tasks every repeat)"},
        "planned_attempts": len(tasks) * repeats * (len([s for s in systems if s != "decisiongpt"]) + (len(conditions) if "decisiongpt" in systems else 0)),
        "completed_attempts": 0, "errors": [],
        "run_type": "partial_pilot" if is_subset else "full",
        "selection": {
            "tasks_in_frozen_spec": len(spec["tasks"]), "task_ids_attempted": [t["task_id"] for t in tasks],
            "task_ids_not_attempted": [t["task_id"] for t in spec["tasks"] if t["task_id"] not in {x["task_id"] for x in tasks}],
            "repeats_frozen": spec["repeats_per_task"], "repeats_used": repeats, "conditions": conditions,
            "max_requests_cap": max_requests, **({"record": selection} if selection else {}),
        },
    }
    if is_subset:
        meta["note"] = ("PARTIAL / PILOT EVALUATION: " + f"{len(tasks)} of {len(spec['tasks'])} frozen tasks x {repeats} repeat(s) (frozen protocol: {spec['repeats_per_task']}). "
                        "Frozen spec, ground truth, scorer and tolerances are unchanged. Not the full benchmark; small-sample figures are indicative only.")
    if mode == "smoke":
        meta["note"] = "PLUMBING CHECK ONLY (LLM disabled, DecisionGPT in deterministic template mode). Not a research result; metrics must not be reported."
    if mode == "mock":
        meta["note"] = ("MOCK INFRASTRUCTURE VALIDATION - NOT RESEARCH RESULTS. A wire-level fake provider replaced the network; token counts, model id, prices and "
                        "injected failures are MOCK values that exist only to exercise the measurement and accounting plumbing. Nothing here measures any model.")
        meta["mock_injections"] = {t: {f"{r}#{o}": k for (r, o), k in d.items()} for t, d in mock.injections.items()}
    _write_json(run_dir / "metadata.json", meta)

    recorder = LLMRecorder().install()
    recorder.max_calls = max_requests  # strict per-request cap (the attempt-level check below is the second line)
    if mode in ("research", "mock"):
        frozen_q = {t["natural_language_question"] for t in spec["tasks"]}
        forbidden = isolation.forbidden_fragments(gt)
        expected_q = isolation.expected_questions_payload()

        def _guard(role: str, payload: dict) -> list[str]:
            if role == "interpreter":
                return isolation.check_interpreter_payload(payload, frozen_q, expected_q, forbidden)
            if role == "explainer":
                return isolation.check_explainer_payload(payload, frozen_q)
            blob = json.dumps(payload, ensure_ascii=False)  # any other request (not expected in this evaluation) is still scanned
            return [f"request contains ground-truth fragment {f!r}" for f in forbidden if f in blob][:1]

        recorder.payload_guard = _guard
        meta["ground_truth_isolation"] = {"guard": "whitelist check of every interpreter request + ground-truth fragment scan; a violating request is never sent and aborts the run",
                                          "forbidden_fragment_count": len(forbidden)}
    results_path = run_dir / "task_results.jsonl"
    errors: list[dict] = []
    systems_live = []
    try:
        dgpt = base = None
        if "decisiongpt" in systems:
            from research.llm_evaluation.systems.decisiongpt import DecisionGPTSystem

            dgpt = DecisionGPTSystem(run_dir, recorder)
            meta["decisiongpt_ingestion"] = dgpt.setup(view)
            systems_live.append(dgpt)
        if "llm_code_baseline" in systems:
            from research.llm_evaluation.systems.llm_code_baseline import LLMCodeBaseline

            base = LLMCodeBaseline(recorder)
            meta["baseline_setup"] = base.setup(view)
            systems_live.append(base)
        _write_json(run_dir / "metadata.json", meta)

        plan: list[tuple[str, str]] = []
        if dgpt:
            plan += [("decisiongpt", c) for c in conditions]
        if base:
            plan += [("llm_code_baseline", "tool")]

        for system_name, condition in plan:
            if system_name == "decisiongpt":
                dgpt.set_clock(ASOF if condition == "asof" else None)
            for task in tasks:
                for rep in range(1, repeats + 1):
                    if max_requests is not None and len(recorder.calls) >= max_requests:
                        raise RuntimeError(f"request cap reached ({max_requests}); remaining attempts were not executed")
                    truth = gt["answers"][task["task_id"]]["answer"]
                    try:
                        out = dgpt.ask(task["natural_language_question"]) if system_name == "decisiongpt" else base.ask(task)
                    except Exception as exc:  # noqa: BLE001 - never aborts the whole run silently
                        out = {"system": system_name, "error": f"{type(exc).__name__}: {exc}"[:300], "latency_s": None, "llm_calls": [], "llm_summary": {"n_calls": 0}}
                    leaks = [c for c in out.get("llm_calls", []) if c.get("leak_violations")]
                    if leaks:
                        meta["status"] = "FAILED"
                        meta["errors"].append(f"GROUND-TRUTH ISOLATION VIOLATION on {task['task_id']} (request not sent): {leaks[0]['leak_violations']}")
                        raise RuntimeError("ground-truth isolation violation - run aborted")
                    sys_err = out.get("error") or (None if out.get("tool_ok", True) else "baseline data tool failed twice")
                    score = score_answer(task, truth, out.get("answer"), system_error=sys_err, view_products=products)
                    cost = cost_usd(out.get("llm_calls", []), pricing)
                    audit = out.get("audit") or {}
                    acct = attempt_accounting.classify(system_name, task["track"], out, audit)
                    row = {
                        "run_id": run_id, "system": system_name, "condition": condition, "task_id": task["task_id"], "repeat": rep,
                        "track": task["track"], "category": task["category"], "question": task["natural_language_question"],
                        "answer": out.get("answer"), "error": out.get("error"), "intent": out.get("intent"), "path": out.get("path"),
                        "latency_s": out.get("latency_s"), "llm_summary": out.get("llm_summary"), "cost_usd": cost,
                        "truth": truth, "score": score, "task": {k: task[k] for k in ("task_id", "track", "category", "expected_answer_type")},
                        "llm_calls": compact_calls(out.get("llm_calls", [])),
                        "stages": {"interpreter_s": (audit.get("interpreter_call") or {}).get("latency_s"), "engine_s": audit.get("tool_latency_s"),
                                   "explainer_s": (audit.get("explanation_call") or {}).get("latency_s"), "server_total_s": audit.get("total_latency_s")},
                        "audit_summary": {"route": audit.get("route"), "outcome": audit.get("outcome"), "fallback_reason": audit.get("fallback_reason"),
                                          "validation_ok": (audit.get("validation") or {}).get("ok"), "validation_errors": (audit.get("validation") or {}).get("errors"),
                                          "explanation_source": audit.get("explanation_source"), "explanation_rejected": audit.get("explanation_rejected"),
                                          "explanation_error": audit.get("explanation_error"), "explanation_skipped": audit.get("explanation_skipped"),
                                          "query_error": audit.get("query_error"),
                                          "resolved_period": (audit.get("verified_result") or {}).get("period"), "reference_date": audit.get("reference_date")},
                    }
                    attempt_accounting.apply(row, acct)
                    with open(results_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                    _write_json(run_dir / "raw_outputs" / f"{system_name}__{condition}__{task['task_id']}__{rep}.json", out)
                    if out.get("error"):
                        errors.append({"system": system_name, "condition": condition, "task_id": task["task_id"], "repeat": rep, "error": out["error"]})
                    meta["completed_attempts"] += 1
                    if meta["completed_attempts"] % 10 == 0:
                        _write_json(run_dir / "metadata.json", meta)
        meta["status"] = "COMPLETED" if (meta["completed_attempts"] == meta["planned_attempts"] and not is_subset) else "PARTIALLY_COMPLETED"
        if spec_sha256(load_spec()) != FROZEN_SPEC_SHA256:
            meta["status"] = "FAILED"
            meta["errors"].append("FROZEN TASK SPECIFICATION CHANGED DURING THE RUN - results invalid")
    except KeyboardInterrupt:
        meta["status"] = "PARTIALLY_COMPLETED"
        meta["errors"].append("interrupted")
    except Exception as exc:  # noqa: BLE001
        meta["status"] = "FAILED" if "isolation violation" in str(exc) else ("PARTIALLY_COMPLETED" if meta["completed_attempts"] else "FAILED")
        meta["errors"].append(f"{type(exc).__name__}: {exc}"[:500])
    finally:
        for s in systems_live:
            try:
                s.teardown()
            except Exception:  # noqa: BLE001
                pass
        recorder.uninstall()
        by_role: dict[str, dict] = {}
        for c in recorder.calls:
            r = by_role.setdefault(c.get("role") or "other", {"max_tokens": set(), "temperature": set()})
            r["max_tokens"].add(c.get("max_tokens"))
            r["temperature"].add(c.get("temperature"))
        meta["model_identity"] = {
            "provider": meta["llm"].get("provider"), "model_requested": meta["llm"].get("model_configured"),
            "models_returned_by_provider": sorted({c.get("model_returned") for c in recorder.calls if c.get("model_returned")}),
            "base_url_host": sorted({c.get("url_host") for c in recorder.calls if c.get("url_host")}),
            "request_parameters_by_role": {k: {"max_tokens": sorted(map(str, v["max_tokens"])), "temperature": sorted(map(str, v["temperature"]))} for k, v in by_role.items()},
            "seed": None, "seed_note": "no sampling parameter or seed is set; repeats are independent requests",
            "retry_policy": (f"bounded: at most {int(get_settings().openai_max_retries)} retry, only for rate-limit / connection errors that cannot have been "
                             "processed; a timeout or server error is never re-sent, so an ambiguous failure cannot spend more; per-request timeout from "
                             "OPENAI_TIMEOUT_SECONDS; attempt counts are recorded per call"),
            "timeout_s": meta["llm"].get("timeout_s"),
            "n_provider_calls_recorded": len(recorder.calls),
        }
        meta["finished_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        meta["errors"] += [f"{e['system']}/{e['condition']}/{e['task_id']}#{e['repeat']}: {e['error']}" for e in errors][:200]
        meta["n_attempt_errors"] = len(errors)
        _write_json(run_dir / "metadata.json", meta)
        _write_json(run_dir / "errors.json", errors)

    rows = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines()] if results_path.exists() else []
    if rows:
        paths: dict[str, int] = {}
        for r in rows:
            if r["system"] == "decisiongpt":
                paths[str(r.get("path"))] = paths.get(str(r.get("path")), 0) + 1
        meta["decisiongpt_answer_paths"] = paths
        meta["decisiongpt_attempts_not_served_by_llm_analytics_path"] = sum(v for k, v in paths.items() if k != "llm_analytics")
        meta["decisiongpt_path_groups"] = dict(sorted(Counter(r.get("path_group") for r in rows if r["system"] == "decisiongpt").items(), key=lambda kv: str(kv[0])))
        if mock is not None:
            meta["mock_injected_events"] = mock.injected_events
        _write_json(run_dir / "metadata.json", meta)
    if mode in ("research", "mock") and rows:
        _write_json(run_dir / "metrics.json", {"run_id": run_id, "metrics": summarize(rows)})
        from research.llm_evaluation.report import write_report

        write_report(run_dir)
    return run_dir


# ----------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    r = sub.add_parser("run")
    r.add_argument("--systems", default="decisiongpt", help="the reference tool-use system needs text/code generation and is not run by this harness")
    r.add_argument("--conditions", default=DEFAULT_CONDITIONS, help="default: asof (reproducible). 'asof,realclock' adds a non-reproducible secondary condition")
    r.add_argument("--limit-tasks", type=int, default=None, help="debug only; a limited run is labelled PARTIAL by design")
    r.add_argument("--task-ids", default=None, help="comma-separated frozen task ids (a subset is labelled PARTIAL / pilot and records the selection)")
    r.add_argument("--repeats", type=int, default=None, help="repeats per task; fewer than the frozen count makes the run a partial pilot")
    r.add_argument("--max-requests", type=int, default=None, help="hard cap on provider requests; the run is refused if the plan exceeds it and stops if it is reached")
    r.add_argument("--selection-file", default=None, help="JSON written BEFORE the run recording the selection rule and ids; embedded in the run metadata")
    sub.add_parser("smoke")
    sub.add_parser("mock")
    rep = sub.add_parser("report")
    rep.add_argument("run_id")
    a = ap.parse_args(argv)

    if a.cmd == "check":
        pre = preflight()
        print(json.dumps(pre, indent=2, ensure_ascii=False, default=str))
        return EXIT_OK if pre["ready_infrastructure"] else EXIT_FAIL
    if a.cmd == "run":
        pre = preflight()
        if pre["problems"]:
            print("PREFLIGHT FAILED:", pre["problems"])
            return EXIT_FAIL
        if "llm_code_baseline" in a.systems.split(","):
            print("BLOCKED: the reference tool-use system (llm_code_baseline) needs a text/code-generating model; "
                  "It was not executed. Run with --systems decisiongpt.")
            return EXIT_BLOCKED
        if pre["blockers"]:
            d = blocked_run(pre)
            print(f"BLOCKED ({', '.join(pre['blockers'])}) -> nothing executed, no results. Record: {d}")
            return EXIT_BLOCKED
        selection = json.loads(Path(a.selection_file).read_text(encoding="utf-8")) if a.selection_file else None
        task_ids = [x.strip() for x in a.task_ids.split(",") if x.strip()] if a.task_ids else (selection or {}).get("task_ids")
        d = execute(mode="research", systems=a.systems.split(","), conditions=a.conditions.split(","), limit_tasks=a.limit_tasks,
                    repeats_override=a.repeats, task_ids=task_ids, selection=selection, max_requests=a.max_requests)
        print(f"run directory: {d}")
        return EXIT_OK
    if a.cmd == "smoke":
        pre = preflight()
        if pre["llm"]["enabled"]:
            print("an LLM is configured: use `run` for the research evaluation; smoke is for the no-LLM plumbing check only")
            return EXIT_FAIL
        d = execute(mode="smoke", systems=["decisiongpt"], conditions=["asof"], repeats_override=1)
        print(f"smoke run (NOT a research result): {d}")
        return EXIT_OK
    if a.cmd == "mock":
        d = execute(mode="mock", systems=["decisiongpt"], conditions=["asof"])
        print(f"MOCK infrastructure validation (NOT research results): {d}")
        return EXIT_OK
    if a.cmd == "report":
        from research.llm_evaluation.report import write_report

        print(write_report(RUNS_DIR / a.run_id))
        return EXIT_OK
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
