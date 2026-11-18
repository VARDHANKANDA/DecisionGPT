"""Research Console endpoint for the POS LLM evaluation: honest states, never fabricated numbers."""
import json

import pytest

from app.core.config import get_settings
from app.services import llm_evaluation_status_service as svc


def _H():
    return {"X-Research-Token": get_settings().research_console_token}


def _spec():
    return {"dataset": {"path": "d"}, "view_rules": "r", "repeats_per_task": 5,
            "tasks": [{"task_id": "A01", "track": "primary", "category": "aggregation"},
                      {"task_id": "E01", "track": "supplementary", "category": "gst"}]}


@pytest.fixture()
def tree(tmp_path, monkeypatch):
    eval_dir = tmp_path / "llm_evaluation"
    (eval_dir / "tasks").mkdir(parents=True)
    (eval_dir / "ground_truth").mkdir()
    (eval_dir / "runs").mkdir()
    raw = tmp_path / "raw.zip"
    raw.write_bytes(b"x")
    monkeypatch.setattr(svc, "EVAL_DIR", eval_dir)
    monkeypatch.setattr(svc, "SPEC_PATH", eval_dir / "tasks" / "tasks_v1.json")
    monkeypatch.setattr(svc, "GT_DIR", eval_dir / "ground_truth")
    monkeypatch.setattr(svc, "RUNS_DIR", eval_dir / "runs")
    monkeypatch.setattr(svc, "RAW_ZIP", raw)
    monkeypatch.setattr(svc, "AUDIT_PATH", eval_dir / "audit" / "architecture_audit.json")
    monkeypatch.setattr(svc, "VERIFY_DIR", eval_dir / "live_verification")
    monkeypatch.setattr(svc, "GATE_PATH", eval_dir / "audit" / "readiness_gate.json")
    return eval_dir


def _install_spec_and_gt(tree):
    spec = _spec()
    (tree / "tasks" / "tasks_v1.json").write_text(json.dumps(spec), encoding="utf-8")
    h = svc._spec_hash(spec)
    (tree / "ground_truth" / f"ground_truth_{h[:12]}.json").write_text(json.dumps({"spec_sha256": h}), encoding="utf-8")


def _llm(monkeypatch, enabled):
    s = get_settings()
    monkeypatch.setattr(s, "openai_api_key", "k" if enabled else None)


def test_requires_research_access(client, tree):
    assert client.get("/api/v1/research/llm-evaluation").status_code in (401, 403)


def test_not_configured_shows_not_evaluated_with_no_numbers(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _llm(monkeypatch, False)
    body = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()
    assert body["state"] == "not_configured" and body["evaluated"] is False
    assert body["latest_run"] is None
    assert body["infrastructure"]["ready"] is True
    assert body["tasks"]["n"] == 2 and body["tasks"]["n_primary"] == 1


def test_ready_to_run_when_llm_and_infrastructure_exist(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _llm(monkeypatch, True)
    assert client.get("/api/v1/research/llm-evaluation", headers=_H()).json()["state"] == "ready_to_run"


def test_blocked_attempt_is_not_a_result(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _llm(monkeypatch, False)
    d = tree / "runs" / "blocked_1"
    d.mkdir()
    (d / "metadata.json").write_text(json.dumps({"run_id": "blocked_1", "status": "BLOCKED", "research_result": False, "reason": "no llm"}), encoding="utf-8")
    body = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()
    assert body["state"] == "not_configured" and body["evaluated"] is False
    assert body["last_blocked_attempt"]["run_id"] == "blocked_1"


def test_smoke_run_is_never_a_result(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _llm(monkeypatch, False)
    d = tree / "runs" / "smoke_1"
    d.mkdir()
    (d / "metadata.json").write_text(json.dumps({"run_id": "smoke_1", "status": "COMPLETED", "research_result": False}), encoding="utf-8")
    body = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()
    assert body["latest_run"] is None and body["evaluated"] is False


@pytest.mark.parametrize("run_status,expected", [("COMPLETED", "completed"), ("PARTIALLY_COMPLETED", "partial"), ("FAILED", "failed"), ("RUNNING", "running")])
def test_real_run_states_pass_recorded_metrics_through(client, tree, monkeypatch, run_status, expected):
    _install_spec_and_gt(tree)
    _llm(monkeypatch, True)
    d = tree / "runs" / "run_1"
    d.mkdir()
    (d / "metadata.json").write_text(json.dumps({"run_id": "run_1", "status": run_status, "research_result": True, "completed_attempts": 3, "planned_attempts": 6}), encoding="utf-8")
    (d / "metrics.json").write_text(json.dumps({"metrics": {"decisiongpt|asof": {"primary": {"quality": {"accuracy_primary_pct": 12.5}}}}}), encoding="utf-8")
    body = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()
    assert body["state"] == expected
    assert body["latest_run"]["metrics"]["decisiongpt|asof"]["primary"]["quality"]["accuracy_primary_pct"] == 12.5
    assert body["latest_run"]["completed_attempts"] == 3


def _audit(tree, implemented):
    (tree / "audit").mkdir(exist_ok=True)
    (tree / "audit" / "architecture_audit.json").write_text(json.dumps({
        "audit_date": "2026-10-08",
        "llm_analytics_path": {"implemented": implemented},
        "frozen_questions_that_reach_the_llm_interpreter_when_configured": 27 if implemented else 0,
        "frozen_question_routing": {"n_unrecognized": 24, "n_total": 27, "questions_that_can_reach_an_llm_call_even_if_configured": 0},
        "task_compatibility": {"class_counts": {"asof": {"B1": 3}}}}), encoding="utf-8")


def test_blocked_by_production_path_when_no_llm_analytics_path_exists_even_with_a_provider(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _audit(tree, implemented=False)
    _llm(monkeypatch, True)
    body = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()
    assert body["state"] == "blocked_production_path" and body["evaluated"] is False
    assert body["blockers"] == ["production_path_not_llm_powered"]
    assert body["production_llm_path"]["status"] == "not_connected_to_analytics_chat"
    assert body["production_llm_path"]["frozen_questions_that_reach_the_llm_interpreter_when_configured"] == 0


def test_both_blockers_are_reported_separately(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _audit(tree, implemented=False)
    _llm(monkeypatch, False)
    body = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()
    assert set(body["blockers"]) == {"production_path_not_llm_powered", "provider_not_configured"}
    assert body["latest_run"] is None


def test_implemented_path_without_a_provider_is_blocked_only_by_the_provider(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _audit(tree, implemented=True)
    _llm(monkeypatch, False)
    body = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()
    assert body["state"] == "blocked_provider_not_configured" and body["label"] == "Blocked \u2014 OPENAI_API_KEY not configured"
    assert body["blockers"] == ["provider_not_configured"]
    assert body["production_llm_path"]["status"] == "available"
    assert body["production_llm_path"]["frozen_questions_that_reach_the_llm_interpreter_when_configured"] == 27
    assert body["evaluation"] == "not_run" and body["evaluated"] is False and body["latest_run"] is None


def test_implemented_path_switched_off_is_reported_as_disabled(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _audit(tree, implemented=True)
    _llm(monkeypatch, True)
    monkeypatch.setattr(get_settings(), "analytics_llm_enabled", False)
    body = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()
    assert body["production_llm_path"]["status"] == "disabled" and body["state"] == "blocked_production_path"


def test_available_path_with_provider_is_ready(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _audit(tree, implemented=True)
    _llm(monkeypatch, True)
    body = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()
    assert body["state"] == "ready_to_run" and body["blockers"] == []
    assert body["evaluation"] == "not_run"


# --------------------------------------------------------------------------------------- run history / verification / plan
def _write_run(tree, run_id, **meta):
    d = tree / "runs" / run_id
    d.mkdir(parents=True)
    (d / "metadata.json").write_text(json.dumps({"run_id": run_id, **meta}), encoding="utf-8")
    return d


def test_run_history_labels_every_stored_run_by_what_it_is(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _llm(monkeypatch, True)
    _write_run(tree, "blocked_1", status="BLOCKED", research_result=False, created_utc="2026-10-07T00:00:00+00:00", reason="no llm")
    _write_run(tree, "mock_1", status="COMPLETED", mock=True, mode="mock", research_result=False, created_utc="2026-10-08T00:00:00+00:00",
               planned_attempts=10, completed_attempts=10)
    _write_run(tree, "smoke_1", status="COMPLETED", mode="smoke", research_result=False, created_utc="2026-10-06T00:00:00+00:00")
    body = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()
    kinds = {r["run_id"]: r["kind"] for r in body["run_history"]}
    assert kinds == {"blocked_1": "blocked", "mock_1": "mock_validation", "smoke_1": "plumbing_check"}
    assert [r["run_id"] for r in body["run_history"]] == ["mock_1", "blocked_1", "smoke_1"]  # newest first
    # none of them is a result
    assert body["evaluated"] is False and body["latest_run"] is None
    assert all(r["research_result"] is False for r in body["run_history"])


def test_a_real_run_is_labelled_live_and_gets_per_task_outcomes(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _llm(monkeypatch, True)
    d = _write_run(tree, "real_1", status="COMPLETED", research_result=True, mock=False, mode="real", created_utc="2026-10-20T00:00:00+00:00",
                   planned_attempts=4, completed_attempts=4, llm={"provider": "openai", "model": "gpt-4.1-mini-2025-04-14"})
    (d / "metrics.json").write_text(json.dumps({"run_id": "real_1", "metrics": {"decisiongpt|asof": {"primary": {"quality": {}, "by_category": {}, "efficiency": {}}}}}), encoding="utf-8")
    rows = [
        {"task_id": "A01", "category": "aggregation", "track": "primary", "question": "q1", "latency_s": 1.0, "score": {"correct": True, "outcome": "correct"}},
        {"task_id": "A01", "category": "aggregation", "track": "primary", "question": "q1", "latency_s": 3.0, "score": {"correct": False, "outcome": "wrong_number"}},
        {"task_id": "E01", "category": "gst", "track": "supplementary", "question": "q2", "error": "x", "excluded_from_accuracy": True, "score": {"outcome": "unable_to_answer"}},
    ]
    (d / "task_results.jsonl").write_text(chr(10).join(json.dumps(r) for r in rows), encoding="utf-8")
    body = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()
    assert body["evaluated"] is True and body["state"] == "completed"
    assert body["run_history"][0]["kind"] == "live_evaluation" and body["run_history"][0]["model"] == "gpt-4.1-mini-2025-04-14"
    per = {t["task_id"]: t for t in body["latest_run"]["per_task"]}
    assert per["A01"]["attempts"] == 2 and per["A01"]["correct"] == 1 and per["A01"]["outcomes"] == {"correct": 1, "wrong_number": 1}
    assert per["E01"]["excluded"] == 1 and per["E01"]["errors"] == 1 and per["E01"]["correct"] == 0


def test_live_verification_is_reported_but_is_never_an_evaluation(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _llm(monkeypatch, True)
    vdir = tree / "live_verification"
    vdir.mkdir()
    (vdir / "v.json").write_text(json.dumps({
        "record_type": "connectivity_verification", "date": "2026-10-13", "provider": "openai", "summary": "s", "does_not_show": ["accuracy"],
        "requests": [{"step": "a", "through_production_client": True, "http_status": 200, "input_tokens": 1000, "output_tokens": 5}]}), encoding="utf-8")
    body = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()
    v = body["live_verification"]
    assert v["requests_total"] == 1 and v["all_http_200"] is True
    assert body["evaluated"] is False and body["latest_run"] is None and body["state"] == "ready_to_run"
    # a connectivity record is not a measured run of the evaluation, so no token or cost estimate is borrowed from it
    plan = body["run_plan"]
    assert plan["planned_attempts"] == 10 and plan["primary_attempts"] == 5
    assert plan["estimated_input_tokens"] is None and plan["estimated_cost_usd_at_list_price"] is None and plan["runnable_now"] is True


def test_no_verification_record_means_no_claim_and_no_cost_estimate(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _llm(monkeypatch, True)
    body = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()
    assert body["live_verification"] is None and body["run_history"] == []
    assert body["run_plan"]["estimated_input_tokens"] is None and body["run_plan"]["estimated_cost_usd_at_list_price"] is None


def test_the_reference_baseline_is_reported_as_not_run(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _llm(monkeypatch, True)
    (tree / "audit").mkdir(exist_ok=True)
    (tree / "audit" / "readiness_gate.json").write_text(json.dumps({"baseline": {"runs_on_jev": False}}), encoding="utf-8")
    b = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()["baselines"]
    assert b[0]["id"] == "B2" and b[0]["runs_on_provider"] is False and "not implemented for the current provider" in b[0]["reason"].lower()


def test_a_subset_run_is_a_labelled_pilot_with_counts_from_stored_rows(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _llm(monkeypatch, True)
    sel = {"tasks_in_frozen_spec": 2, "task_ids_attempted": ["A01"], "task_ids_not_attempted": ["E01"], "repeats_frozen": 5, "repeats_used": 1}
    d = _write_run(tree, "run_pilot", status="PARTIALLY_COMPLETED", run_type="partial_pilot", research_result=True, mock=False, mode="research",
                   created_utc="2026-10-14T00:00:00+00:00", planned_attempts=1, completed_attempts=1, selection=sel,
                   llm={"provider": "openai", "model_configured": "gpt-4.1-mini"},
                   model_identity={"n_provider_calls_recorded": 1, "models_returned_by_provider": ["gpt-4.1-mini-2025-04-14"]},
                   decisiongpt_answer_paths={"llm_analytics": 1})
    (d / "metrics.json").write_text(json.dumps({"run_id": "run_pilot", "metrics": {"decisiongpt|asof": {"primary": {"quality": {}, "by_category": {}, "efficiency": {}}}}}), encoding="utf-8")
    row = {"task_id": "A01", "category": "aggregation", "track": "primary", "question": "q", "answer": "Your sales were 10.", "truth": 10, "path": "llm_analytics",
           "latency_s": 1.0, "cost_usd": 0.00005, "llm_summary": {"n_calls": 1, "input_tokens": 1000, "output_tokens": 400}, "score": {"correct": True, "outcome": "correct"}}
    (d / "task_results.jsonl").write_text(json.dumps(row), encoding="utf-8")
    body = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()
    assert body["state"] == "partial" and body["evaluated"] is True  # a pilot is never "completed"
    s = body["latest_run"]["summary"]
    assert s["run_type"] == "partial_pilot" and s["tasks_in_spec"] == 2 and s["task_ids_not_attempted"] == ["E01"]
    assert s["repeats_used"] == 1 and s["repeats_frozen"] == 5
    assert s["primary"]["correct"] == 1 and s["primary"]["attempts"] == 1 and s["supplementary"]["attempts"] == 0
    assert s["provider_requests"] == 1 and s["input_tokens"] == 1000 and s["output_tokens"] == 400 and s["estimated_cost_usd_at_list_price"] == 0.00005
    assert s["models_returned"] == ["gpt-4.1-mini-2025-04-14"]
    hist = body["run_history"][0]
    assert hist["kind"] == "live_evaluation" and hist["run_type"] == "partial_pilot" and hist["tasks_attempted"] == 1 and hist["tasks_in_spec"] == 2
    assert body["run_plan"]["runnable_now"] is True


def _live(tree, run_id, ids, when, provider="openai", model="gpt-4.1-mini-2025-04-14", in_tok=1000, out_tok=400):
    d = _write_run(tree, run_id, status="PARTIALLY_COMPLETED", run_type="partial_pilot", research_result=True, mock=False, created_utc=when,
                   planned_attempts=len(ids), completed_attempts=len(ids), llm={"provider": provider, "model_configured": model},
                   selection={"tasks_in_frozen_spec": 2, "task_ids_attempted": ids, "task_ids_not_attempted": [], "repeats_frozen": 5, "repeats_used": 1},
                   model_identity={"n_provider_calls_recorded": len(ids), "models_returned_by_provider": [model]})
    rows = [{"task_id": i, "track": "primary" if i == "A01" else "supplementary", "category": "c", "question": "q", "answer": "a", "truth": 1, "path": "llm_analytics",
             "path_class": "llm_answered", "latency_s": 1.0, "cost_usd": 0.0001, "llm_summary": {"n_calls": 1, "input_tokens": in_tok, "output_tokens": out_tok},
             "score": {"correct": i == "A01", "outcome": "correct" if i == "A01" else "other"}} for i in ids]
    (d / "task_results.jsonl").write_text(chr(10).join(json.dumps(r) for r in rows), encoding="utf-8")
    (d / "metrics.json").write_text(json.dumps({"run_id": run_id, "metrics": {"decisiongpt|asof": {"primary": {"quality": {}, "by_category": {}, "efficiency": {}}}}}), encoding="utf-8")


def test_live_coverage_is_grouped_by_provider_and_never_pooled(client, tree, monkeypatch):
    _install_spec_and_gt(tree)  # spec has A01 (primary) and E01 (supplementary), repeats_per_task=5
    _llm(monkeypatch, True)
    _live(tree, "run_a", ["A01"], "2026-10-14T01:00:00+00:00")
    _live(tree, "run_b", ["E01"], "2026-10-14T02:00:00+00:00")
    _live(tree, "run_old_jev", ["A01", "E01"], "2026-10-13T00:00:00+00:00", provider="typesafe-jev", model="jev-1.13.0")
    _write_run(tree, "mock_x", status="COMPLETED", mock=True, mode="mock", research_result=False, created_utc="2026-10-14T03:00:00+00:00")
    cov = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()["live_coverage"]
    assert [c["provider"] for c in cov] == ["openai", "typesafe-jev"]  # the active provider first; never merged
    oa, jv = cov
    assert oa["is_active_provider"] is True and jv["is_active_provider"] is False
    assert [r["run_id"] for r in oa["runs"]] == ["run_a", "run_b"]  # the mock run and the other provider's run are not counted
    assert oa["tasks_attempted_at_least_once"] == 2 and oa["task_ids_never_attempted"] == []
    assert oa["max_repeats_any_run"] == 1 and oa["repeats_frozen"] == 5  # complete coverage at 1 repeat is NOT the frozen protocol
    assert oa["primary_correct_sum"] == 1 and oa["primary_attempts_sum"] == 1 and oa["provider_requests_sum"] == 2
    assert [r["run_id"] for r in jv["runs"]] == ["run_old_jev"] and jv["provider_requests_sum"] == 2
    assert "never pooled" in oa["note"].lower()


def test_run_plan_uses_only_the_active_providers_measured_tokens_and_its_own_price(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _llm(monkeypatch, True)
    monkeypatch.setattr(get_settings(), "openai_model", "gpt-4.1-mini")
    (tree / "pricing.json").write_text(json.dumps({"models": {"gpt-4.1-mini": {"input_per_million_usd": 0.40, "output_per_million_usd": 1.60}}}), encoding="utf-8")
    # only another provider has run: nothing may be borrowed from it
    _live(tree, "run_old_jev", ["A01"], "2026-10-13T00:00:00+00:00", provider="typesafe-jev", model="jev-1.13.0", in_tok=1345, out_tok=452)
    plan = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()["run_plan"]
    assert plan["provider"] == "openai" and plan["estimated_input_tokens"] is None and plan["estimated_cost_usd_at_list_price"] is None
    # now the active provider has a measured run: 1000 in / 400 out per request, 10 attempts, $0.40 / $1.60 per million
    _live(tree, "run_oa", ["A01"], "2026-10-14T00:00:00+00:00")
    plan = client.get("/api/v1/research/llm-evaluation", headers=_H()).json()["run_plan"]
    assert plan["measured_input_tokens_per_attempt"] == 1000 and plan["estimated_input_tokens"] == 10000
    assert plan["estimated_cost_usd_at_list_price"] == round(10 * (1000 * 0.40 + 400 * 1.60) / 1_000_000, 4)
    assert "run_oa" in plan["estimate_basis"]


def test_no_live_runs_means_no_coverage_claim(client, tree, monkeypatch):
    _install_spec_and_gt(tree)
    _llm(monkeypatch, True)
    _write_run(tree, "mock_only", status="COMPLETED", mock=True, mode="mock", research_result=False, created_utc="2026-10-14T03:00:00+00:00")
    assert client.get("/api/v1/research/llm-evaluation", headers=_H()).json()["live_coverage"] is None
