"""Final pre-experiment readiness gate, pinned as tests. MOCKED provider only - nothing here is a research result.

Covers: fail-closed runner preflight, attempt/latency/token accounting through the REAL Jev client stack (wire-level fake), fallback accounting,
ground-truth isolation, clock scoping, "no model-written text", secret hygiene, and one full mock infrastructure run.
"""
import json
import threading
import time
from datetime import date

import pytest

import research.llm_evaluation.run_evaluation as runner
from app.core import clock
from app.core.config import get_settings
from research.llm_evaluation import attempt_accounting, isolation, metrics, mock_llm
from research.llm_evaluation.audit import readiness_gate as gate
from research.llm_evaluation.llm_instrument import LLMRecorder, compact_calls, cost_usd

SPEC = json.loads(runner.SPEC_PATH.read_text(encoding="utf-8"))
Q2T = {t["natural_language_question"]: t["task_id"] for t in SPEC["tasks"]}

_CACHE: dict = {}


@pytest.fixture(autouse=True)
def _cheap_preflight(monkeypatch):
    """preflight() rebuilds the evaluation view and recomputes the ground truth (tens of seconds). The tests below exercise the gate LOGIC,
    so build the (deterministic, unchanged) view once per process and reuse it; the real preflight is still run end-to-end by the gate script."""
    if not _CACHE:
        view, info = runner.build_view()
        _CACHE.update(view=view, info=info, fresh=runner.compute_all(SPEC, view, info))
    monkeypatch.setattr(runner, "build_view", lambda: (_CACHE["view"], _CACHE["info"]))
    monkeypatch.setattr(runner, "compute_all", lambda spec, view=None, info=None: _CACHE["fresh"])


# ============================================================================ fail-closed runner
def test_runner_refuses_when_the_frozen_task_spec_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(runner, "FROZEN_SPEC_SHA256", "0" * 64)
    pre = runner.preflight()
    assert "FROZEN TASK SPECIFICATION CHANGED — EVALUATION BLOCKED." in pre["problems"]
    with mock_llm.mock_provider_active(Q2T):  # even with a (mock) provider the run must not start
        assert runner.main(["run"]) == runner.EXIT_FAIL
    assert list(tmp_path.iterdir()) == []


def test_runner_refuses_when_the_manifest_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(runner, "FROZEN_MANIFEST_SHA256", "f" * 64)
    assert "EXPERIMENT MANIFEST CHANGED — EVALUATION BLOCKED." in runner.preflight()["problems"]
    assert runner.main(["run"]) == runner.EXIT_FAIL and list(tmp_path.iterdir()) == []


def test_frozen_constants_match_the_recorded_hashes():
    assert runner.FROZEN_SPEC_SHA256.startswith("98f37037") and runner.FROZEN_MANIFEST_SHA256.startswith("94aa419c")
    pre = runner.preflight()
    assert pre["checks"]["frozen_spec_unchanged"] and pre["checks"]["frozen_manifest_unchanged"]


def test_the_openai_key_and_model_must_be_present(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "openai_api_key", None)
    assert "provider_not_configured" in runner.preflight()["blockers"]
    monkeypatch.setattr(s, "openai_api_key", "dummy-not-a-key")
    monkeypatch.setattr(s, "openai_model", "")
    assert "model_not_configured" in runner.preflight()["blockers"]  # the model id must be named so it can be recorded
    monkeypatch.setattr(s, "openai_model", "gpt-4.1-mini")
    assert "model_not_configured" not in runner.preflight()["blockers"] and "provider_not_configured" not in runner.preflight()["blockers"]


def test_runner_fails_closed_if_the_one_attempt_policy_is_not_true(monkeypatch):
    monkeypatch.setattr(runner, "_retry_environment", lambda: {"ok": False, "retry_policy": "unknown", "single_post_site": False})
    assert any("one attempt per call" in p for p in runner.preflight()["problems"])


def test_the_client_makes_exactly_one_attempt_per_call():
    env = runner._retry_environment()
    assert env["ok"] and env["single_request_seam"] and env["timeout_not_retried"] and env["retry_cap_ok"] and env["retry_policy"].startswith("bounded")


def test_the_reference_tool_use_system_is_blocked_not_silently_dropped(tmp_path, monkeypatch):
    """It needs a text/code-generating model; asking for it must say so and run nothing."""
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    with mock_llm.mock_provider_active(Q2T):
        assert runner.main(["run", "--systems", "decisiongpt,llm_code_baseline"]) == runner.EXIT_BLOCKED
    assert list(tmp_path.iterdir()) == []


def test_default_conditions_are_the_reproducible_one_only():
    assert runner.DEFAULT_CONDITIONS == "asof"


# ============================================================================ clock
def test_clock_default_scoped_released_and_not_inherited():
    assert clock.today() == date.today() and not clock.is_pinned()
    seen = {}
    with clock.reference_date(date(2025, 3, 31)):
        assert clock.today() == date(2025, 3, 31)
        t = threading.Thread(target=lambda: seen.update(today=clock.today(), pinned=clock.is_pinned()))
        t.start()
        t.join()
    assert seen == {"today": date.today(), "pinned": False}  # a new thread (e.g. another user's request) never sees the research date
    assert clock.today() == date.today()
    assert runner._clock_self_test()["ok"]


@pytest.mark.parametrize(
    "ref,phrase,spec,start,end",
    [
        (date(2025, 3, 31), "this month", {"kind": "calendar", "unit": "month", "offset": 0}, date(2025, 3, 1), date(2025, 3, 31)),
        (date(2025, 3, 31), "previous month", {"kind": "calendar", "unit": "month", "offset": -1}, date(2025, 2, 1), date(2025, 2, 28)),
        (date(2025, 3, 31), "February", {"kind": "calendar", "unit": "month", "month": 2}, date(2025, 2, 1), date(2025, 2, 28)),
        (date(2025, 3, 31), "March", {"kind": "calendar", "unit": "month", "month": 3}, date(2025, 3, 1), date(2025, 3, 31)),
        (date(2025, 4, 1), "this month (boundary)", {"kind": "calendar", "unit": "month", "offset": 0}, date(2025, 4, 1), date(2025, 4, 30)),
        (date(2025, 4, 1), "previous month (boundary)", {"kind": "calendar", "unit": "month", "offset": -1}, date(2025, 3, 1), date(2025, 3, 31)),
        (date(2025, 1, 1), "previous month (year boundary)", {"kind": "calendar", "unit": "month", "offset": -1}, date(2024, 12, 1), date(2024, 12, 31)),
        (date(2025, 3, 31), "explicit historical date", {"kind": "absolute", "start": "2025-02-14", "end": "2025-02-14"}, date(2025, 2, 14), date(2025, 2, 14)),
    ],
)
def test_relative_date_language_is_deterministic_under_the_evaluation_clock(ref, phrase, spec, start, end):
    from pydantic import TypeAdapter

    from app.analytics.query_engine import resolve_period
    from app.schemas.analytics_query import DateSpec

    ta = TypeAdapter(DateSpec)
    for _ in range(2):  # twice: same inputs, same output
        with clock.reference_date(ref):
            p, _a = resolve_period(ta.validate_python(spec), clock.today(), None)
        assert (p.start, p.end) == (start, end), phrase


# ============================================================================ ground-truth isolation
def _payload(question: str):
    from app.services.analytics_interpreter_service import QUESTIONS
    from app.services.openai_client import SYSTEM_DECIDE, build_schema

    return {"model": "gpt-4.1-mini", "instructions": SYSTEM_DECIDE, "input": f"<text>\n{question}\n</text>", "store": False, "max_output_tokens": 700,
            "text": {"format": {"type": "json_schema", "name": "classification", "strict": True, "schema": build_schema(QUESTIONS)}}}


def test_interpreter_requests_for_all_frozen_questions_carry_no_ground_truth():
    gt = runner.load_or_make_ground_truth(SPEC)
    forb = isolation.forbidden_fragments(gt)
    assert len(forb) > 20  # the scan is not vacuous
    qs = set(Q2T)
    for q in qs:
        assert isolation.check_interpreter_payload(_payload(q), qs, None, forb) == [], q


def test_isolation_check_catches_leaks_and_tampering():
    gt = runner.load_or_make_ground_truth(SPEC)
    forb = isolation.forbidden_fragments(gt)
    qs = set(Q2T)
    q = SPEC["tasks"][0]["natural_language_question"]
    ok = _payload(q)
    assert isolation.check_interpreter_payload(ok, qs, None, forb) == []
    leak = {**ok, "input": f"<text>\n{q} (hint: 14,59,083)\n</text>"}
    assert isolation.check_interpreter_payload(leak, qs, None, forb)  # not a frozen question verbatim
    extra = {**ok, "context": {"rows": [1, 2, 3]}}
    assert isolation.check_interpreter_payload(extra, qs, None, forb)  # an unexpected field
    swapped = {**ok, "instructions": ok["instructions"] + " The ground truth is attached."}
    assert isolation.check_interpreter_payload(swapped, qs, None, forb)  # the pre-registered instructions were altered
    answer = json.loads(json.dumps(ok))
    answer["text"]["format"]["schema"]["properties"]["route"]["description"] = "the answer is 1459083"
    assert isolation.check_interpreter_payload(answer, qs, None, forb)  # the pre-registered schema was altered


def test_recorder_guard_blocks_a_violating_request_before_it_is_sent(monkeypatch):
    from app.services.openai_client import OpenAIClient

    sent = []
    monkeypatch.setattr(OpenAIClient, "_sdk", lambda self: sent.append(1))
    rec = LLMRecorder()
    rec.payload_guard = lambda role, payload: ["synthetic leak"]
    rec.install()
    try:
        client = type("C", (), {"provider": "openai", "timeout": 1, "last_attempts": 0})()
        with pytest.raises(RuntimeError, match="isolation violation"):
            OpenAIClient._request(client, _payload(SPEC["tasks"][0]["natural_language_question"]))
    finally:
        rec.uninstall()
    assert sent == [] and rec.calls[0]["leak_violations"] == ["synthetic leak"]
    assert compact_calls(rec.calls)[0]["leak_violations"]


# ============================================================================ attempts / latency / tokens / model identity (real client stack, fake wire)
def _call(q: str, injections):
    from app.services.analytics_interpreter_service import QUESTIONS
    from app.services.llm_service import LLMService

    with mock_llm.mock_provider_active(Q2T, injections) as prov:
        rec = LLMRecorder().install()
        try:
            t0 = time.perf_counter()
            res = LLMService().decide(q, QUESTIONS)
            wall = time.perf_counter() - t0
        finally:
            rec.uninstall()
    return res, rec.calls, wall, prov


Q_A01 = SPEC["tasks"][0]["natural_language_question"]


def test_success_records_one_attempt_tokens_and_the_model_the_provider_echoed():
    res, calls, _w, prov = _call(Q_A01, {})
    assert res.ok and res.attempts == 1 and res.response_model == mock_llm.MOCK_MODEL_ECHOED and res.model == mock_llm.MOCK_MODEL_REQUESTED
    assert res.usage == {"input_tokens": 1100, "output_tokens": 120}
    c = calls[0]
    assert c["role"] == "interpreter" and c["attempts"] == 1 and c["input_tokens"] == 1100 and c["output_tokens"] == 120
    assert c["model_requested"] == mock_llm.MOCK_MODEL_REQUESTED and c["model_returned"] == mock_llm.MOCK_MODEL_ECHOED
    assert len(prov.requests) == 1


@pytest.mark.parametrize("kind,error", [("http_529", "provider_error"), ("http_429", "rate_limited"), ("timeout", "timeout"), ("malformed", "malformed_output")])
def test_failures_are_categorised_and_never_retried(kind, error):
    res, calls, _w, prov = _call(Q_A01, {"A01": {("interpreter", 1): kind}})
    assert not res.ok and res.error == error and res.attempts == 1
    # a malformed body is a successful HTTP call whose CONTENT was rejected by validation; every other kind failed at the request
    assert calls[0]["ok"] is (kind == "malformed") and calls[0]["attempts"] == 1
    assert len(prov.requests) == 1  # one request (the mock disables the bounded retry): an ambiguous failure never spends more


def test_cost_needs_provider_usage_and_a_price_for_the_exact_model_and_never_guesses():
    ok = {"ok": True, "input_tokens": 1_000_000, "output_tokens": 500_000, "model_returned": mock_llm.MOCK_MODEL_ECHOED}
    assert cost_usd([ok], mock_llm.MOCK_PRICING) == pytest.approx(1.0)  # mock price: $1 per 1M input, output free
    assert cost_usd([ok], None) is None  # no verified price -> not available
    assert cost_usd([{**ok, "model_returned": "other-model"}], mock_llm.MOCK_PRICING) is None  # price for a different model is not used
    assert cost_usd([{**ok, "input_tokens": None}], mock_llm.MOCK_PRICING) is None  # no usage -> not available
    assert cost_usd([ok, {"ok": False, "error": "timeout"}], mock_llm.MOCK_PRICING) == pytest.approx(1.0)  # failed call: unknown cost, excluded, not guessed
    assert cost_usd([], mock_llm.MOCK_PRICING) is None


# ============================================================================ fallback / unsupported accounting
def _row(system="decisiongpt", track="primary", correct=True, **out):
    row = {"system": system, "task": {"track": track, "category": "c", "expected_answer_type": "numeric"}, "task_id": "T", "latency_s": 0.1,
           "score": {"correct": correct, "outcome": "correct" if correct else "numerically_incorrect"}, "llm_summary": {"n_calls": 2}}
    acct = attempt_accounting.classify(system, track, {"path": "llm_analytics", "intent": "analytics_query", "sufficient_evidence": True, **out}, out.get("audit"))
    return attempt_accounting.apply(row, acct)


def test_a_legacy_fallback_is_never_an_llm_success_even_if_its_text_was_right():
    r = _row(path="legacy_router", intent="top_products", audit={"fallback_reason": "timeout"})
    assert r["path_group"] == "legacy_fallback" and r["failure_category"] == "provider_failure"
    assert r["score"]["correct"] is False and r["score"]["outcome"] == "legacy_fallback"
    assert r["score_unadjusted"]["correct"] is True and r["counts_as_llm_path_success"] is False
    for reason, cat in (("malformed_output", "invalid_output"), ("invalid_request", "invalid_output"), ("interpreter_routed_legacy", "interpreter_routed_legacy"), ("provider_error", "provider_failure")):
        assert _row(path="legacy_router", intent="x", audit={"fallback_reason": reason})["failure_category"] == cat


def test_gst_refusals_are_neither_failures_nor_successes_but_a_primary_refusal_is_a_failure():
    gst = _row(track="supplementary", correct=False, intent="analytics_unsupported")
    assert gst["excluded_from_accuracy"] and gst["score"]["outcome"] == "unsupported_by_design" and gst["counts_as_llm_path_success"] is False
    primary_refusal = _row(track="primary", correct=False, intent="analytics_unsupported")
    assert not primary_refusal["excluded_from_accuracy"] and primary_refusal["path_group"] == "unsupported"
    infra = _row(error="HTTP 500: boom", path=None)
    assert infra["path_group"] == "infrastructure_failure" and infra["score"]["correct"] is False


def test_metrics_exclude_gst_refusals_and_keep_fallbacks_in_the_denominator():
    rows = [_row(correct=True), _row(correct=True), _row(correct=False),
            _row(correct=True, path="legacy_router", intent="top_products", audit={"fallback_reason": "timeout"}),
            _row(track="supplementary", correct=False, intent="analytics_unsupported")]
    sup = [r for r in rows if r["task"]["track"] == "supplementary"]
    prim = [r for r in rows if r["task"]["track"] == "primary"]
    q = metrics.quality(prim)
    assert q["n_attempts"] == 4 and q["n_correct"] == 2 and q["accuracy_primary_pct"] == 50.0  # the fallback is a non-success, not dropped
    pa = q["path_accounting"]
    assert pa["fallback_rate_pct"] == 25.0 and pa["legacy_fallback_attempts_whose_text_would_have_scored_correct"] == 1
    assert pa["accuracy_among_attempts_answered_by_llm_path_pct"] == pytest.approx(66.67)
    qs = metrics.quality(sup)
    assert qs["n_attempts"] == 0 and qs["n_excluded_unsupported_by_design"] == 1 and qs.get("accuracy_primary_pct") is None


def test_p95_is_not_invented_from_few_observations_and_tokens_are_never_estimated():
    few = [{**_row(), "latency_s": float(i), "llm_calls": [{"role": "interpreter", "ok": True, "latency_s": 1.0, "attempts": 1, "input_tokens": None, "output_tokens": None}]} for i in range(5)]
    e = metrics.efficiency(few)
    assert e["latency_end_to_end_s"]["p95"] is None and e["latency_end_to_end_s"]["median"] == 2.0
    assert e["tokens"]["input_total"] is None and e["tokens"]["calls_without_usage"] == 5 and e["tokens"]["complete"] is False
    many = [{**_row(), "latency_s": float(i)} for i in range(40)]
    assert metrics.efficiency(many)["latency_end_to_end_s"]["p95"] is not None


# ============================================================================ no model-written text
def test_no_part_of_an_answer_can_be_model_written(client, db_session, monkeypatch):
    from app.services import analytics_answer_service, analytics_chat_service
    from tests.analytics_llm_support import FakeLLM, decision, make_business, seed_sales

    # the former number / causal-claim guards guarded model prose; the prose itself is gone, so there is nothing left to guard
    assert not any(hasattr(analytics_answer_service, n) for n in ("explain", "check_part", "allowed_numbers", "extract_numbers", "EXPLAIN_SYSTEM"))
    bid = make_business(db_session)
    seed_sales(db_session, bid)
    qn = "Total sales in February 2025?"
    fake = FakeLLM({qn: decision(operation="aggregate", metric="revenue")})
    monkeypatch.setattr(analytics_chat_service, "get_llm", lambda: fake)
    body = client.post(f"/api/v1/businesses/{bid}/chat", json={"message": qn}).json()
    assert body["details"]["sections"]["fact"] in body["answer"] and body["details"]["sections"]["interpretation"] is None
    assert len(fake.calls) == 1


# ============================================================================ secrets hygiene
def test_secret_scanner_detects_synthetic_secrets_and_ignores_plain_text():
    fake_openai = "sk-" + "A1b2C3d4" * 4
    fake_bearer = "Bearer " + "x" * 45
    fake_assign = 'api_key = "' + "Zz9" * 8 + '"'
    assert "openai_style_key" in gate.scan_text(f"token is {fake_openai}")
    assert "bearer_token_literal" in gate.scan_text(f"Authorization: {fake_bearer}")
    assert "assigned_secret_literal" in gate.scan_text(fake_assign)
    assert gate.scan_text("LLM_API_KEY=  # set locally, never commit\nthe api key is read from the environment") == []


def test_env_files_are_ignored_and_not_tracked():
    cfg = gate.provider_config_checks()
    assert ".env" in cfg[".env_files_gitignored"] and "backend/.env" in cfg[".env_files_gitignored"] and cfg["tracked_env_files"] == []
    assert not cfg["api_key_in_status_endpoint_payload"] and not cfg["api_key_in_runner_llm_status"]


def test_repository_has_no_secret_patterns():
    sc = gate.secret_scan()
    assert sc["n_files_with_hits"] == 0, sc["pattern_hits_by_name"]  # paths only, never the matched text


# ============================================================================ the full mock infrastructure run (27 tasks x 2 repeats)
def test_mock_infrastructure_run_end_to_end(tmp_path, monkeypatch):
    from research.llm_evaluation import report as report_mod
    from app.services import llm_evaluation_status_service as status_svc

    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(report_mod, "REPORTS_DIR", tmp_path / "reports")
    run_dir = runner.execute(mode="mock", systems=["decisiongpt"], conditions=["asof"], repeats_override=2)
    meta = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (run_dir / "task_results.jsonl").read_text(encoding="utf-8").splitlines()]

    # mock is never a research result
    # 2 repeats < the frozen 5, so even with every task attempted the run is a labelled partial pilot, never COMPLETED
    assert meta["mock"] is True and meta["research_result"] is False and run_dir.name.startswith("mock_")
    assert meta["status"] == "PARTIALLY_COMPLETED" and meta["run_type"] == "partial_pilot" and meta["selection"]["repeats_used"] == 2
    assert "NOT RESEARCH RESULTS" in meta["note"] and meta["pricing_is_mock"] is True
    # the frozen set, twice, with unique ids and every raw output kept
    assert len(rows) == 54 == meta["completed_attempts"]
    assert len({(r["task_id"], r["repeat"]) for r in rows}) == 54
    for k in (1, 2):
        assert {r["task_id"] for r in rows if r["repeat"] == k} == {t["task_id"] for t in SPEC["tasks"]}
    assert len(list((run_dir / "raw_outputs").glob("*.json"))) == 54
    assert meta["spec_sha256"] == runner.FROZEN_SPEC_SHA256 and meta["manifest_sha256"] == runner.FROZEN_MANIFEST_SHA256
    # 23 primary tasks through the analytics path, 4 GST refused and excluded
    prim = [r for r in rows if r["task"]["track"] == "primary"]
    supp = [r for r in rows if r["task"]["track"] == "supplementary"]
    assert len(prim) == 46 and len(supp) == 8
    assert all(r["path"] == "llm_analytics" for r in rows if r["path_group"] != "legacy_fallback")
    assert all(r["path_class"] == "llm_unsupported" and r["excluded_from_accuracy"] for r in supp)
    # every answered primary attempt used a classification request and, at most, one validated-explanation request
    answered = [r for r in prim if r["path_group"] == "llm_path"]
    assert answered and all([c["role"] for c in r["llm_calls"]] in (["interpreter"], ["interpreter", "explainer"]) for r in answered)
    # injected failures were classified, not hidden
    assert meta["decisiongpt_path_groups"].get("legacy_fallback", 0) >= 1
    fb = [r for r in prim if r["path_group"] == "legacy_fallback"]
    assert all(r["score"]["correct"] is False and r["failure_category"] for r in fb)
    # reference date comes from the evaluation clock for every audited answer
    assert {r["audit_summary"]["reference_date"] for r in rows if r["audit_summary"]["reference_date"]} == {"2025-03-31"}
    # ground-truth guard was active and nothing was blocked
    assert meta["ground_truth_isolation"]["forbidden_fragment_count"] > 20
    assert not any(c.get("leak_violations") for r in rows for c in r["llm_calls"])
    # model identity recorded precisely
    mi = meta["model_identity"]
    assert mi["model_requested"] == mock_llm.MOCK_MODEL_REQUESTED and mi["models_returned_by_provider"] == [mock_llm.MOCK_MODEL_ECHOED]
    assert mi["retry_policy"].startswith("bounded") and mi["request_parameters_by_role"]["interpreter"]["max_tokens"] == ["700"]
    # report: mock banner, precise terminology, provenance stays unverified
    text = (tmp_path / "reports" / f"{run_dir.name}.md").read_text(encoding="utf-8")
    assert text.startswith("# MOCK INFRASTRUCTURE VALIDATION (NOT RESEARCH RESULTS)")
    assert "The deterministic query engine is the numerical authority." in text and "schema-constrained labels only" in text
    assert "does NOT evaluate LLM arithmetic ability" in text
    low = text.lower()
    for bad in ("decisiongpt accuracy", "official indian", "representative of indian smes and", "verified provenance"):
        assert bad not in low, bad
    assert "NOT independently verified" in text and "CC BY-NC-SA 4.0" in text and "NOT representative of Indian SMEs or Indian retail generally" in text
    assert "not an official or government dataset" in low
    # no secrets in any generated file
    for p in list(run_dir.rglob("*")) + list((tmp_path / "reports").rglob("*")):
        if p.is_file() and p.suffix in (".json", ".jsonl", ".md"):
            assert "MOCK-NOT-A-REAL-KEY" not in p.read_text(encoding="utf-8"), p
    # the console shows it as infrastructure validation, never as a result
    monkeypatch.setattr(status_svc, "RUNS_DIR", tmp_path / "runs")
    st = status_svc.build_status()
    assert st["evaluated"] is False and st["latest_run"] is None and st["mock_validation"]["run_id"] == run_dir.name
    assert "NOT research results" in st["mock_validation"]["note"]
    # the real configuration was restored
    assert get_settings().llm_enabled is False and not clock.is_pinned()


def test_limitation_prose_matches_the_audited_view_numbers():
    from research.llm_evaluation import report as report_mod
    from research.llm_evaluation.audit import architecture as arch

    c = arch.view_conservation()
    joined = " ".join(report_mod.LIMITATIONS)
    assert f"{round(c['rejected_fractional_quantity']['pct_of_lines'])}% of lines" in joined
    assert f"{c['pct_original_revenue_retained']}%" in joined
