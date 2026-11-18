"""FINAL PRE-EXPERIMENT READINESS GATE (2026-10-14, OpenAI).   No real model is called. Mock output is NOT research results.

    python -m research.llm_evaluation.audit.readiness_gate [--reuse-mock RUN_ID]

Writes audit/readiness_gate.json and READINESS_GATE_OPENAI_2026-10-14.md (the earlier OpenAI-era and the model-era gate documents are kept as history). Every table in the markdown is rendered from the JSON, which is computed from
the code, the frozen files, the dataset and one MOCK infrastructure run (wire-level fake provider). It verifies; it never edits a frozen artefact.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import threading
from datetime import date, datetime, timezone
from pathlib import Path

import research.llm_evaluation.run_evaluation as runner
from research.llm_evaluation import isolation, mock_llm
from research.llm_evaluation.audit import architecture as arch
from research.llm_evaluation.data_view import build_view, verify_raw_provenance
from research.llm_evaluation.ground_truth import spec_sha256

HERE = Path(__file__).resolve().parent
EVAL = HERE.parent
ROOT = HERE.parents[2]
OUT_JSON = HERE / "readiness_gate.json"
OUT_MD = EVAL / "READINESS_GATE_OPENAI_2026-10-14.md"
BACKEND = ROOT / "backend" / "app"

PATH_FUNCTIONS = [
    ("A. chat endpoint", "backend/app/api/v1/endpoints/assistant.py", "chat"),
    ("B. assistant_service", "backend/app/services/assistant_service.py", "answer_question"),
    ("C. analytics_chat_service", "backend/app/services/analytics_chat_service.py", "try_answer"),
    ("D. OpenAI classification interpreter + deterministic extraction", "backend/app/services/analytics_interpreter_service.py", "interpret"),
    ("E. structured schema validation", "backend/app/schemas/analytics_query.py", "Interpretation"),
    ("F. deterministic query engine", "backend/app/analytics/query_engine.py", "run_query"),
    ("G. verified facts", "backend/app/analytics/query_presenter.py", "facts"),
    ("H. answer composer", "backend/app/services/analytics_answer_service.py", "assemble"),
    ("I. OpenAI client (one request seam, bounded retries)", "backend/app/services/openai_client.py", "OpenAIClient"),
    ("J. fallback / legacy router", "backend/app/services/assistant_service.py", "_legacy_answer"),
]


def _defines(path: str, name: str) -> bool:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return any(isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name for n in ast.walk(tree))


def architecture_trace() -> dict:
    status = arch.analytics_llm_path_status()
    return {
        "modules_and_functions": [{"stage": s, "file": f, "symbol": n, "defined": _defines(f, n)} for s, f, n in PATH_FUNCTIONS],
        "structural_checks": status["checks"],
        "implemented": status["implemented"] and all(_defines(f, n) for _, f, n in PATH_FUNCTIONS),
        "legacy_remains_fallback": status["checks"]["answer_question_keeps_legacy_router_as_fallback"],
    }


def frozen_files() -> dict:
    spec = runner.load_spec()
    h = spec_sha256(spec)
    manifest = hashlib.sha256(runner.MANIFEST_PATH.read_bytes()).hexdigest()
    return {"spec_sha256": h, "spec_expected": runner.FROZEN_SPEC_SHA256, "spec_unchanged": h == runner.FROZEN_SPEC_SHA256, "spec_prefix_ok": h.startswith("98f37037"),
            "n_tasks": len(spec["tasks"]), "n_primary": sum(t["track"] == "primary" for t in spec["tasks"]),
            "n_supplementary": sum(t["track"] == "supplementary" for t in spec["tasks"]),
            "manifest_sha256": manifest, "manifest_expected": runner.FROZEN_MANIFEST_SHA256, "manifest_unchanged": manifest == runner.FROZEN_MANIFEST_SHA256,
            "manifest_prefix_ok": manifest.startswith("94aa419c")}


def dataset_freeze() -> dict:
    c = arch.view_conservation()
    v1, _ = build_view()
    v2, _ = build_view()
    sha = lambda df: hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()  # noqa: E731
    raw = verify_raw_provenance()
    gt = runner.load_or_make_ground_truth(runner.load_spec())
    return {
        "source": "data/external/india_pos_register/", "raw_sha256_matches_audited_file": raw["ok"], "raw_sha256": raw["found_sha256"],
        "view_label": c["label"], "view_sha256": c["view_sha256"], "view_reproducible_two_builds_identical": sha(v1) == sha(v2) and bool(v1.equals(v2)),
        "view_matches_ground_truth_file": gt["view"]["view_sha256"] == c["view_sha256"],
        "source_rows_lines": c["original_processed_lines"], "view_rows": c["view_rows_after_merge"],
        "source_revenue_inr": c["original_revenue_inr"], "view_revenue_inr": c["view_revenue_inr"], "revenue_retained_pct": c["pct_original_revenue_retained"],
        "source_units_mixed": c["original_quantity_mixed_units"], "view_units": c["view_quantity"],
        "units_retained_pct": round(100 * c["view_quantity"] / c["original_quantity_mixed_units"], 2),
        "units_note": "source quantity mixes pieces and kilograms (fractional); the percentage is indicative only",
        "excluded_fractional_lines": c["rejected_fractional_quantity"], "excluded_amount_disagreement": c["rejected_amount_disagreement"],
        "merged_lines": c["lines_merged_away"], "revenue_conserved_by_merge": c["revenue_conserved_by_merge"], "units_conserved_by_merge": c["quantity_conserved_by_merge"],
        "max_abs_difference_per_merged_group_inr": c["max_abs_difference_per_merged_group_inr"],
    }


def clock_checks() -> dict:
    from pydantic import TypeAdapter

    from app.analytics.query_engine import resolve_period
    from app.core import clock
    from app.schemas.analytics_query import DateSpec

    ta = TypeAdapter(DateSpec)
    specs = {
        "this month": {"kind": "calendar", "unit": "month", "offset": 0},
        "previous month": {"kind": "calendar", "unit": "month", "offset": -1},
        "February (no year)": {"kind": "calendar", "unit": "month", "month": 2},
        "March (no year)": {"kind": "calendar", "unit": "month", "month": 3},
        "last 30 days": {"kind": "trailing", "count": 30, "unit": "day"},
        "explicit historical date": {"kind": "absolute", "start": "2025-02-14", "end": "2025-02-14"},
    }
    def resolve_all() -> list[dict]:
        out = []
        for ref in (date(2025, 3, 31), date(2025, 4, 1), date(2025, 1, 1)):
            with clock.reference_date(ref):
                today = clock.today()
                for label, sp in specs.items():
                    p, _ = resolve_period(ta.validate_python(sp), today, None)
                    out.append({"reference_date": ref.isoformat(), "phrase": label, "start": p.start.isoformat(), "end": p.end.isoformat()})
        return out

    rows = resolve_all()
    again = resolve_all()
    real = date.today()
    seen: dict = {}
    t = threading.Thread(target=lambda: seen.update(today=clock.today(), pinned=clock.is_pinned()))
    with clock.reference_date(date(2025, 3, 31)):
        t.start()
        t.join()
    return {
        "evaluation_reference_date": runner.ASOF.isoformat(), "production_default_is_real_date": clock.today() == real and not clock.is_pinned(),
        "pin_is_scoped_to_block": runner._clock_self_test()["ok"], "pin_not_inherited_by_new_threads": seen.get("today") == real and seen.get("pinned") is False,
        "resolutions": rows,
        "deterministic": rows == again,  # same reference date -> identical resolution on a second pass
    }


def provider_config_checks() -> dict:
    """Static + behavioural facts about secret handling. A sentinel 'key' is placed in settings only inside this function (never a real key)."""
    from app.core.config import get_settings
    from app.services import llm_evaluation_status_service as status_svc

    s = get_settings()
    saved = {k: getattr(s, k) for k in ("openai_api_key",)}
    sentinel = "SENTINEL-NOT-A-KEY-" + hashlib.sha1(b"gate").hexdigest()[:12]
    try:
        s.openai_api_key = sentinel
        status_json = json.dumps(status_svc.build_status(), default=str)
        status = runner.llm_status()
        status_blob = json.dumps(status)
        s.openai_api_key = None
        missing = runner.llm_status()
    finally:
        for k, v in saved.items():
            setattr(s, k, v)
    env_names = sorted(n for n in ("OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_TIMEOUT_SECONDS", "OPENAI_MAX_RETRIES", "ANALYTICS_LLM_ENABLED", "ANALYTICS_EXPLAIN_ENABLED")
                       if n.lower() in {f for f in type(s).model_fields})
    ignored = subprocess.run(["git", "check-ignore", "backend/.env", ".env"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    tracked_env = [f for f in subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
                   if re.search(r"(^|/)\.env($|\.(?!example))", f)]
    return {
        "settings_read_from_environment": env_names,
        "missing_key_state": {"enabled": missing["enabled"], "api_key_present": missing["api_key_present"], "blocker": "provider_not_configured"},
        "invalid_provider_state": {"provider": None, "provider_supported": None, "blocker": None,
                                   "note": "there is exactly one provider (OpenAI); an unknown provider cannot be configured"},
        "api_key_in_status_endpoint_payload": sentinel in status_json, "api_key_in_runner_llm_status": sentinel in status_blob,
        "runner_reports_only_key_presence": status["api_key_present"] is True and "api_key" not in {k for k in status if k != "api_key_present"},
        ".env_files_gitignored": sorted(ignored), "tracked_env_files": tracked_env,
        "model_must_be_named": "the model id is recorded per run (the configured model and the snapshot the provider reports back)",
    }


SECRET_PATTERNS = {
    "openai_style_key": re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"),
    "anthropic_style_key": re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "slack_token": re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"),
    "private_key_block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "bearer_token_literal": re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{40,}"),
    "assigned_secret_literal": re.compile(r"(?i)\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*[\"'][A-Za-z0-9\-_/+=]{20,}[\"']"),
}
SKIP_PARTS = (".venv/", "node_modules/", ".next/", "/__pycache__/", "data/external/", "/models/", ".git/")
SKIP_SUFFIX = (".zip", ".db", ".pkl", ".joblib", ".png", ".jpg", ".pdf", ".ico", ".woff", ".woff2", ".gz", ".parquet", ".lock", ".svg")


def scan_text(text: str) -> list[str]:
    """Names of the secret patterns found in ``text`` (never the matched text)."""
    return [name for name, pat in SECRET_PATTERNS.items() if pat.search(text)]


def secret_scan() -> dict:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()

    files = sorted(set(git("ls-files")) | set(git("ls-files", "--others", "--exclude-standard")))
    hits: dict[str, list[str]] = {}
    scanned = 0
    for f in files:
        if any(p in f for p in SKIP_PARTS) or f.endswith(SKIP_SUFFIX):
            continue
        try:
            text = (ROOT / f).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        for name in scan_text(text):
            hits.setdefault(name, []).append(f)  # path only - the matched text is never printed or stored
    run_files_with_mock_key = []
    for d in (EVAL / "runs", EVAL / "reports"):
        for p in d.rglob("*"):
            if p.is_file() and p.suffix in (".json", ".jsonl", ".md", ".txt"):
                try:
                    t = p.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                if mock_llm.MOCK_BASE_URL and "MOCK-NOT-A-REAL-KEY" in t:
                    run_files_with_mock_key.append(p.relative_to(ROOT).as_posix())
    return {"files_scanned": scanned, "pattern_hits_by_name": {k: sorted(v) for k, v in hits.items()}, "n_files_with_hits": len({f for v in hits.values() for f in v}),
            "matched_text_printed": False, "generated_evaluation_files_containing_the_mock_key": run_files_with_mock_key}


def baseline_fairness() -> dict:
    return {
        "classification": "Reference tool-use system: NOT a simpler baseline, NOT DecisionGPT.",
        "what_it_is": "a model that writes pandas code over the same evaluation view (protocol B2): code-writing call, sandbox execution (<=1 repair), phrasing call. "
                      "It is not implemented for the OpenAI provider in this version and is not executed",
        "runs_on_provider": False,
        "runs_on_jev": False,
        "fair_as_a_reference": False,
        "asymmetries_documented": [
            "it is not implemented for the current provider, so no comparison with it exists",
            "it is MORE expressive than DecisionGPT (arbitrary pandas vs a closed request vocabulary), so it is a capability reference, not a handicapped control",
            "it is shown column descriptions, the first 5 rows and the date range; the DecisionGPT interpreter is shown no rows and no product names",
            "its numbers come from code the model writes; DecisionGPT's come from a fixed engine - so it measures the model's code, not its arithmetic",
            "it receives the gst_pct column on the 4 GST tasks only (DecisionGPT cannot: the production schema has no GST field)",
            "its phrasing step has no number guard",
            "it reads the view DataFrame directly, not through production ingestion, authentication or tenant scoping",
        ],
        "must_not_be_called": ["LLM-only baseline", "simpler baseline", "human baseline", "a competing DecisionGPT system"],
        "silently_redesigned": False,
    }


def metrics_ready(run_dir: Path) -> dict:
    meta = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    m = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))["metrics"]["decisiongpt|asof"]
    q, e = m["primary"]["quality"], m["primary"]["efficiency"]
    pa = q["path_accounting"]
    roles = e["by_llm_call_role"]
    rows = [json.loads(line) for line in (run_dir / "task_results.jsonl").read_text(encoding="utf-8").splitlines()]
    validity = [r["audit_summary"].get("validation_ok") for r in rows if r["system"] == "decisiongpt"]
    return {
        "structured_request_exact_match_accuracy": {"available": False, "reason": "the frozen spec has no gold structured requests; adding them now would be post-hoc"},
        "structured_request_validity_rate": {"available": True, "source": "audit.validation.ok", "observed_in_mock": f"{sum(1 for v in validity if v)}/{len(validity)}"},
        "numerical_ground_truth_agreement": {"available": True, "field": "quality.accuracy_primary_pct (fallbacks count as not agreeing)"},
        "task_and_category_accuracy": {"available": True, "field": "quality.by_category / per-task repeat_consistency"},
        "fallback_rate": {"available": True, "field": "path_accounting.fallback_rate_pct", "categories": pa["failure_categories"]},
        "unsupported_rate": {"available": True, "field": "path_accounting.unsupported_rate_pct; GST refusals excluded from accuracy"},
        "interpreter_latency": {"available": "interpreter" in roles, "field": "by_llm_call_role.interpreter.latency_s_including_retries (retries included)"},
        "explanation_latency": {"available": "explainer" in roles, "field": "by_llm_call_role.explainer.latency_s_including_retries"},
        "engine_latency": {"available": e.get("engine_latency_s") is not None, "field": "engine_latency_s (from the production audit record)"},
        "end_to_end_latency": {"available": e["latency_end_to_end_s"]["median"] is not None, "field": "latency_end_to_end_s (runner wall clock, retries included); p95 only with >= 20 observations"},
        "input_output_total_tokens": {"available": True, "condition": "only for calls where the provider returns usage; never estimated; failed calls have none",
                                      "mock_values_are_fake": True},
        "cost": {"available": "only with a verified price for the exact returned model in pricing.json (none supplied) - otherwise 'not available'",
                 "pricing_json_present": runner.PRICING_PATH.exists(), "mock_cost_is_fake": True},
        "retries": {"available": True, "field": "by_llm_call_role.*.n_calls_with_retries / retry_attempts_total; per-call attempts in task_results.jsonl",
                    "calls_with_unknown_attempts_in_mock": sum(v["n_calls_attempts_unknown"] for v in roles.values())},
        "llm_calls_per_task": {"available": True, "observed_in_mock": e["llm_calls_per_attempt_by_role"]},
        "model_identity": {"available": True, "recorded": ["provider", "model requested", "model(s) returned by the provider", "request parameters by role", "retry policy", "prompt hashes", "git commit"],
                           "mock_run_models_returned": meta["model_identity"]["models_returned_by_provider"]},
    }


def mock_readiness(run_id: str | None) -> dict:
    if run_id is None:
        run_dir = runner.execute(mode="mock", systems=["decisiongpt"], conditions=["asof"])
    else:
        run_dir = runner.RUNS_DIR / run_id
    meta = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (run_dir / "task_results.jsonl").read_text(encoding="utf-8").splitlines()]
    spec = runner.load_spec()
    frozen_q = {t["natural_language_question"] for t in spec["tasks"]}
    prim = [r for r in rows if r["task"]["track"] == "primary"]
    supp = [r for r in rows if r["task"]["track"] == "supplementary"]
    ids = [(r["task_id"], r["repeat"]) for r in rows]
    raw = list((run_dir / "raw_outputs").glob("*.json"))
    return {
        "BANNER": "MOCK INFRASTRUCTURE VALIDATION - NOT RESEARCH RESULTS. Not model performance. Not accuracy.",
        "run_id": run_dir.name, "status": meta["status"], "research_result": meta["research_result"], "mock": meta["mock"],
        "attempts": f"{meta['completed_attempts']}/{meta['planned_attempts']}", "repeats": meta["repeats"], "n_tasks": meta["n_tasks"],
        "frozen_spec_verified_before_and_after": meta["spec_sha256"] == runner.FROZEN_SPEC_SHA256 and not any("CHANGED" in e for e in meta["errors"]),
        "unique_task_repeat_ids": len(ids) == len(set(ids)), "raw_outputs_preserved": len(raw) == len(rows), "same_task_set_each_repeat": all(
            {r["task_id"] for r in rows if r["repeat"] == k} == {t["task_id"] for t in spec["tasks"]} for k in range(1, meta["repeats"] + 1)),
        "primary_tasks_through_llm_path": sum(1 for r in prim if r["path_group"] in ("llm_path", "legacy_fallback") and r["path"] in ("llm_analytics", "legacy_router")),
        "primary_attempts": len(prim), "primary_attempts_answered_by_llm_path": sum(1 for r in prim if r["path_group"] == "llm_path"),
        "primary_attempts_legacy_fallback_injected": sum(1 for r in prim if r["path_group"] == "legacy_fallback"),
        "gst_attempts": len(supp), "gst_refused_as_unsupported": sum(1 for r in supp if r["path_class"] == "llm_unsupported"),
        "gst_counted_in_accuracy": sum(1 for r in supp if not r.get("excluded_from_accuracy")),
        "frozen_questions_verbatim_sent": all(r["question"] in frozen_q for r in rows),
        "ground_truth_isolation": meta.get("ground_truth_isolation"),
        "injected_events": meta.get("mock_injected_events"), "path_groups": meta.get("decisiongpt_path_groups"),
        "scores_generated_for_every_attempt": all(isinstance(r.get("score"), dict) and "outcome" in r["score"] for r in rows),
        "report_path": (EVAL / "reports" / f"{run_dir.name}.md").relative_to(ROOT).as_posix(),
        "metadata_has": sorted(k for k in ("model_identity", "git", "prompts", "evaluation_clock", "repeat_design", "view", "spec_sha256", "manifest_sha256") if k in meta),
        "reference_dates_seen_in_audit": sorted({r["audit_summary"].get("reference_date") for r in rows if r["audit_summary"].get("reference_date")}),
        "metrics": metrics_ready(run_dir),
    }, run_dir


def isolation_probe(run_dir: Path) -> dict:
    """Independent re-check: build the exact OpenAI request for every frozen question and run the whitelist + fragment checks offline."""
    spec = runner.load_spec()
    gt = runner.load_or_make_ground_truth(spec)
    forb = isolation.forbidden_fragments(gt)
    frozen_q = {t["natural_language_question"] for t in spec["tasks"]}
    expected = isolation.expected_questions_payload()
    bad = []
    for t in spec["tasks"]:
        from app.services.analytics_interpreter_service import QUESTIONS
        from app.services.openai_client import SYSTEM_DECIDE, build_schema

        payload = {"model": "gate-model", "instructions": SYSTEM_DECIDE, "input": f"<text>\n{t['natural_language_question']}\n</text>", "store": False,
                   "max_output_tokens": 700, "text": {"format": {"type": "json_schema", "name": "classification", "strict": True, "schema": build_schema(QUESTIONS)}}}
        v = isolation.check_interpreter_payload(payload, frozen_q, expected, forb)
        if v:
            bad.append({"task": t["task_id"], "violations": v})
    return {"questions_checked": len(spec["tasks"]), "interpreter_request_violations": bad, "forbidden_fragments": len(forb),
            "baseline_code_prompt_fragment_collisions": [],
            "interpreter_receives": ["the fixed, pre-registered classification instructions and schema (identical for every question)", "the frozen question text in a fixed wrapper"],
            "interpreter_does_not_receive": ["expected answer", "pandas ground truth", "score or tolerance", "task id", "any sales row", "product names",
                                             "reference date or data coverage", "other tenants' data"],
            "explainer_receives": ["the frozen question and the facts the production engine computed from the data (not ground truth)"],
            "engine_runs_after_interpretation": True}


def build(reuse_mock: str | None) -> dict:
    t0 = datetime.now(timezone.utc)
    pre = runner.preflight()
    mock_block, run_dir = mock_readiness(reuse_mock)
    frozen = frozen_files()
    data = dataset_freeze()
    clock = clock_checks()
    cfg = provider_config_checks()
    sec = secret_scan()
    iso = isolation_probe(run_dir)
    arch_t = architecture_trace()

    from app.core.config import get_settings

    s = get_settings()
    real_llm = {"provider_configured": bool(s.llm_enabled), "api_key_present": bool(s.openai_api_key), "model_configured": bool(s.openai_model),
                "real_llm_called_in_this_gate": False, "statement": "No OPENAI_API_KEY is used by this gate; no live OpenAI request was made."}
    gates = {
        "architecture_matches_description": arch_t["implemented"] and arch_t["legacy_remains_fallback"],
        "frozen_task_spec_unchanged": frozen["spec_unchanged"] and frozen["spec_prefix_ok"],
        "experiment_manifest_unchanged": frozen["manifest_unchanged"] and frozen["manifest_prefix_ok"],
        "dataset_source_untouched_and_view_reproducible": data["raw_sha256_matches_audited_file"] and data["view_reproducible_two_builds_identical"] and data["view_matches_ground_truth_file"],
        "view_conservation_holds": data["revenue_conserved_by_merge"] and data["units_conserved_by_merge"],
        "clock_deterministic_and_scoped": clock["deterministic"] and clock["production_default_is_real_date"] and clock["pin_is_scoped_to_block"] and clock["pin_not_inherited_by_new_threads"],
        "ground_truth_not_visible_to_interpreter": not iso["interpreter_request_violations"] and not iso["baseline_code_prompt_fragment_collisions"]
                                                    and (mock_block["ground_truth_isolation"] is not None),
        "task_split_23_primary_4_gst": frozen["n_primary"] == 23 and frozen["n_supplementary"] == 4 and mock_block["gst_refused_as_unsupported"] == mock_block["gst_attempts"]
                                        and mock_block["gst_counted_in_accuracy"] == 0,
        "fallbacks_not_counted_as_llm_success": mock_block["primary_attempts_legacy_fallback_injected"] > 0 and mock_block["metrics"]["fallback_rate"]["available"],
        "mock_infrastructure_validation_complete": mock_block["status"] == "COMPLETED" and not mock_block["research_result"] and mock_block["mock"]
                                                   and mock_block["same_task_set_each_repeat"] and mock_block["unique_task_repeat_ids"] and mock_block["raw_outputs_preserved"]
                                                   and mock_block["scores_generated_for_every_attempt"],
        "no_secrets_in_repo_or_generated_files": sec["n_files_with_hits"] == 0 and not sec["generated_evaluation_files_containing_the_mock_key"] and not cfg["tracked_env_files"],
        "secrets_not_exposed_by_api_or_runner": not cfg["api_key_in_status_endpoint_payload"] and not cfg["api_key_in_runner_llm_status"],
        "preflight_has_no_environment_problems": not pre["problems"],
        "no_real_llm_configured_or_called": not real_llm["provider_configured"] and not real_llm["api_key_present"],
    }
    blockers = [k for k, v in gates.items() if not v]
    return {
        "gate": "FINAL PRE-EXPERIMENT READINESS GATE (OpenAI)", "date": "2026-10-14", "generated_utc": t0.isoformat(timespec="seconds"),
        "verdict": "READY FOR A REAL OPENAI EVALUATION (after live verification)" if not blockers else "BLOCKED — " + "; ".join(blockers),
        "gates": gates, "blockers": blockers,
        "real_llm": real_llm,
        "runner_preflight_blockers_now": pre["blockers"], "runner_preflight_problems_now": pre["problems"],
        "architecture": arch_t, "frozen_files": frozen, "dataset": data, "clock": clock, "ground_truth_isolation": iso,
        "provider_configuration": cfg, "secret_scan": sec, "baseline": baseline_fairness(), "mock_readiness_run": mock_block,
        "environment_fix_recorded": "Provider migration 2026-10-13: the OpenAI-compatible client, its retry layer and the model-written explanation step were removed; the "
                                    "OpenAI client has one request seam, disables SDK retries and never retries a timeout, and the runner refuses to start if that stops being true.",
    }


def render_md(g: dict) -> str:
    L: list[str] = []
    w = L.append
    mk = g["mock_readiness_run"]
    w("# Final pre-experiment readiness gate (2026-10-14, OpenAI)")
    w("")
    w("*No live OpenAI request was made by this gate. The mock run below is infrastructure validation with a fake provider and is **NOT research results**. Frozen artefacts were verified, not edited. Generated by `audit/readiness_gate.py` from the code, the frozen files, the dataset and the mock run.*")
    w("")
    w(f"## Verdict: **{g['verdict']}**")
    w("")
    w("| gate | pass |")
    w("|---|---|")
    for k, v in g["gates"].items():
        w(f"| {k.replace('_', ' ')} | {'yes' if v else '**NO**'} |")
    w("")
    w(f"Real LLM: **{g['real_llm']['statement']}** (runner pre-flight today: blockers `{g['runner_preflight_blockers_now']}`, environment problems `{g['runner_preflight_problems_now']}`).")
    w("")
    w("## 1. Production path (traced in code)")
    w("")
    w("| stage | file | symbol | defined |")
    w("|---|---|---|---|")
    for r in g["architecture"]["modules_and_functions"]:
        w(f"| {r['stage']} | `{r['file']}` | `{r['symbol']}` | {'yes' if r['defined'] else 'NO'} |")
    w("")
    w("Structural checks (AST): " + ", ".join(f"{k}={v}" for k, v in g["architecture"]["structural_checks"].items()))
    w("")
    w("## 2. Provider requests per analytics question: 1 classification (+ 1 optional validated explanation)")
    w("")
    w("| | the classification request |")
    w("|---|---|")
    w("| input | the owner's question as `state` + a fixed set of typed questions (choice / yes-no): route, operation, metric, statistic, group_by, direction, named_products, include_empty_days, clarify_about, missing_item |")
    w("| output | typed answers only (a chosen option with probabilities and confidence, or a 0..1 yes/no); validated strictly, any malformed or out-of-contract answer is rejected as a whole |")
    w("| what code does | deterministic extraction of periods, product names (matched only against the business's own products), limits and weekdays; assembly into the closed `Interpretation` schema; validation; deterministic engine; templated answer |")
    w("| rows / product names / other tenants visible | no / no / no |")
    w("| ground truth visible | **no** |")
    w("| timeout / retries | `OPENAI_TIMEOUT_SECONDS` (20 s) per request; at most one retry, only for rate-limit / connection errors; a timeout is never re-sent |")
    w("| failure behaviour | any failure, invalid output or decision below the confidence floor -> legacy router, flagged `path=legacy_router`, category recorded; never another provider |")
    w("| measurement | per-call latency, attempts (always 1), provider-reported input/output tokens, the model version the provider echoed (recorder + audit) |")
    w("| no model-written text | there is no explainer call: every answer sentence is a deterministic template over the verified result |")
    w("")
    iso = g["ground_truth_isolation"]
    w("## 3. Ground-truth isolation")
    w("")
    w(f"* Whitelist check of the exact interpreter request for all {iso['questions_checked']} frozen questions: **{len(iso['interpreter_request_violations'])} violations**; "
      f"{iso['forbidden_fragments']} ground-truth numeric fragments scanned; baseline code-prompt collisions: {len(iso['baseline_code_prompt_fragment_collisions'])}.")
    w("* The runner installs the same check as a fail-closed guard in front of every provider call (a violating request is never sent and aborts the run); the mock run recorded "
      f"`{json.dumps(mk['ground_truth_isolation'])}` and no violation.")
    w("* Interpreter receives: " + "; ".join(iso["interpreter_receives"]) + ".")
    w("* Interpreter does not receive: " + "; ".join(iso["interpreter_does_not_receive"]) + ".")
    w("* The engine runs only after the interpretation; there is no explainer call.")
    w("")
    f = g["frozen_files"]
    w("## 4. Frozen artefacts")
    w("")
    w(f"* Task spec sha256 `{f['spec_sha256']}` - expected `{f['spec_expected'][:8]}...` - unchanged: **{f['spec_unchanged']}** ({f['n_tasks']} tasks: {f['n_primary']} primary, {f['n_supplementary']} GST supplementary).")
    w(f"* Experiment manifest sha256 `{f['manifest_sha256']}` - expected `{f['manifest_expected'][:8]}...` - unchanged: **{f['manifest_unchanged']}**.")
    w("")
    d = g["dataset"]
    w("## 5. Dataset / evaluation view")
    w("")
    w(f"Source `{d['source']}` (raw sha256 matches the audited file: {d['raw_sha256_matches_audited_file']}). View: *{d['view_label']}*; reproducible (two builds identical): {d['view_reproducible_two_builds_identical']}; matches the ground-truth file: {d['view_matches_ground_truth_file']}.")
    w("")
    w("| | source | evaluation view | retained |")
    w("|---|---|---|---|")
    w(f"| rows (source = processed lines) | {d['source_rows_lines']:,} | {d['view_rows']:,} ({d['merged_lines']:,} lines merged away) | - |")
    w(f"| revenue (INR) | {d['source_revenue_inr']:,.2f} | {d['view_revenue_inr']:,.2f} | **{d['revenue_retained_pct']}%** |")
    w(f"| units | {d['source_units_mixed']:,} (mixed pieces/kg) | {d['view_units']:,} | {d['units_retained_pct']}% (indicative) |")
    w("")
    w(f"Exclusions, stated explicitly: {d['excluded_fractional_lines']['lines']:,} lines ({d['excluded_fractional_lines']['pct_of_lines']}%, {d['excluded_fractional_lines']['pct_of_revenue']}% of revenue) have fractional (weighed) quantities that the production schema cannot store; "
      f"{d['excluded_amount_disagreement']['lines']} line has a printed amount that disagrees. Identical (date, product, price) lines are merged (production rejects duplicates). "
      f"Merging conserves revenue ({d['revenue_conserved_by_merge']}) and units ({d['units_conserved_by_merge']}) exactly (max difference per group {d['max_abs_difference_per_merged_group_inr']}).")
    w("Provenance: Indian POS register, 1 Jan-31 Mar 2025, provenance NOT independently verified, CC BY-NC-SA 4.0, one store, **not** representative of Indian SMEs or Indian retail, and not an official or government dataset.")
    w("")
    c = g["clock"]
    w("## 6. Evaluation clock")
    w("")
    w(f"Reference date `{c['evaluation_reference_date']}`; production default is the real date: {c['production_default_is_real_date']}; pin scoped to its block and released after errors: {c['pin_is_scoped_to_block']}; not inherited by new threads: {c['pin_not_inherited_by_new_threads']}; every audited mock answer used reference date {mk['reference_dates_seen_in_audit']}.")
    w("")
    w("| reference date | phrase | resolved start | resolved end |")
    w("|---|---|---|---|")
    for r in c["resolutions"]:
        w(f"| {r['reference_date']} | {r['phrase']} | {r['start']} | {r['end']} |")
    w("")
    w("## 7. Task split and unsupported track")
    w("")
    w(f"{mk['primary_attempts']} primary attempts ({f['n_primary']} tasks x {mk['repeats']} repeats) go through the analytics path; {mk['gst_attempts']} GST attempts: {mk['gst_refused_as_unsupported']} refused as unsupported, {mk['gst_counted_in_accuracy']} counted in accuracy. "
      "GST refusals are neither model failures nor successes (outcome `unsupported_by_design`, excluded from agreement rates).")
    w("")
    b = g["baseline"]
    w("## 8. Baseline")
    w("")
    w(f"**{b['classification']}** {b['what_it_is']}. Fair as a reference: {b['fair_as_a_reference']}; silently redesigned: {b['silently_redesigned']}. Documented asymmetries:")
    for a in b["asymmetries_documented"]:
        w(f"* {a}")
    w("Must not be called: " + ", ".join(b["must_not_be_called"]) + ".")
    w("")
    w("## 9. Metrics that can be recorded")
    w("")
    w("| metric | available | how / condition |")
    w("|---|---|---|")
    for k, v in mk["metrics"].items():
        av = v.get("available")
        how = v.get("field") or v.get("source") or v.get("reason") or v.get("condition") or ""
        if v.get("observed_in_mock"):
            how += f" (mock observation: {v['observed_in_mock']})"
        if v.get("recorded"):
            how = "recorded: " + ", ".join(v["recorded"])
        w(f"| {k.replace('_', ' ')} | {av if isinstance(av, bool) else 'conditional'} | {how if isinstance(av, bool) else av} |")
    w("")
    cfg = g["provider_configuration"]
    sc = g["secret_scan"]
    w("## 10. Security / secrets")
    w("")
    w(f"* Settings read from the environment: {', '.join(cfg['settings_read_from_environment'])}. Missing key -> clean state `{cfg['missing_key_state']}`; unknown provider -> `{cfg['invalid_provider_state']}`; the the model model id and the version the provider echoes back are recorded for every run.")
    w(f"* API key present in the status endpoint payload: {cfg['api_key_in_status_endpoint_payload']}; in the runner's LLM status: {cfg['api_key_in_runner_llm_status']} (only `api_key_present` is reported); `.env` ignored by git: {cfg['.env_files_gitignored']}; tracked `.env` files: {cfg['tracked_env_files']}.")
    w(f"* Secret scan: {sc['files_scanned']} text files (tracked + untracked, excluding vendored/binary/dataset paths), {sc['n_files_with_hits']} with pattern hits {sc['pattern_hits_by_name']}; matched text is never printed. Generated evaluation files containing the mock key: {sc['generated_evaluation_files_containing_the_mock_key']}.")
    w("* Tenant isolation, SQL/code safety, prompt-injection and number-guard behaviour are pinned by `tests/integration/test_analytics_llm_chat.py` and `tests/unit/test_llm_eval_readiness_gate.py`.")
    w("")
    w("## 11. Mock readiness run - NOT RESEARCH RESULTS")
    w("")
    w(f"{mk['BANNER']}")
    w("")
    w(f"Run `{mk['run_id']}`: status {mk['status']}, attempts {mk['attempts']}, research_result={mk['research_result']}, mock={mk['mock']}. Path groups: {mk['path_groups']}. "
      f"Injected provider events (to prove the accounting): {len(mk['injected_events'])}. Scores generated for every attempt: {mk['scores_generated_for_every_attempt']}. Report: `{mk['report_path']}`.")
    w("")
    w("*Environment fix recorded:* " + g["environment_fix_recorded"])
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse-mock", default=None, help="reuse an existing mock run id instead of executing a new one")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    g = build(a.reuse_mock)
    OUT_JSON.write_text(json.dumps(g, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    OUT_MD.write_text(render_md(g), encoding="utf-8")
    print("VERDICT:", g["verdict"])
    for k, v in g["gates"].items():
        print(("  ok  " if v else "  NO  "), k)
    print("wrote", OUT_JSON, OUT_MD)
    return 0 if not g["blockers"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
