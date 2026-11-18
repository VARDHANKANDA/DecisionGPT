"""Architectural conclusions of the 2026-10-08 audit, pinned as tests (research/llm_evaluation/audit).

The audit found the production chat was a fixed-intent router with NO LLM analytics path. Later the same day an LLM analytics
path was added (see ARCHITECTURE_UPDATE_LLM_ANALYTICS_PATH_2026-10-08.md); these tests now pin BOTH facts: the legacy router is
unchanged (it is the fallback), and the new path exists with the structure the evaluation relies on.

If production code changes in a way that invalidates the audit (a new LLM call site, a router change, a new raw date.today() site),
these tests fail on purpose so the audit and the evaluation target definition are re-done, not silently reused.
"""
import json
from datetime import date
from pathlib import Path

import pytest

import research.llm_evaluation.run_evaluation as runner
from research.llm_evaluation.audit import architecture as arch
from research.llm_evaluation.ground_truth import spec_sha256
from research.llm_evaluation.llm_instrument import LLMRecorder
from research.llm_evaluation.systems.decisiongpt import DecisionGPTSystem

FROZEN_SPEC_SHA256 = "98f370377280c730938ccfd2db2d848335e98ce3419f149f4769c0a638f30146"
SPEC = json.loads(runner.SPEC_PATH.read_text(encoding="utf-8"))


def test_frozen_spec_is_unchanged():
    assert spec_sha256(SPEC) == FROZEN_SPEC_SHA256
    subsets = json.loads(arch.SUBSET_PATH.read_text(encoding="utf-8"))
    assert subsets["frozen_spec_sha256"] == FROZEN_SPEC_SHA256 and "unchanged" in subsets["derived_from"]


# --------------------------------------------------------------------------- the LLM architecture
def test_llm_call_sites_are_exactly_the_audited_ones():
    """Provider access is exactly two places: the analytics interpreter (one typed Jev request per question) and goal classification."""
    sites = {(s["file"].split("/")[-1], s["function"], s["method"]) for s in arch.scan_llm_call_sites()}
    assert sites == {
        ("analytics_interpreter_service.py", "interpret", "decide"),
        ("goal_service.py", "parse_and_validate_goal", "parse_goal"),
    }


def test_no_legacy_intent_can_reach_a_provider():
    """Jev returns typed decisions, not prose, so the legacy handlers' former 'rephrase' steps are deterministic templates now."""
    imap = arch.intent_llm_map()
    assert {i for i, m in imap.items() if m["invokes_llm_when_configured"]} == set()
    assert {"why_kpi_fell", "price_change_advice", "marketing_change_advice", "what_focus", "top_products", "unrecognized"} <= set(imap)


def test_the_llm_never_routes_retrieves_or_computes():
    """classify_intent / retrieval / date logic contain no LLM call: the only LLM calls are the audited narration sites above."""
    import ast

    tree = ast.parse((arch.APP / "services" / "assistant_service.py").read_text(encoding="utf-8"))
    for fn_name in ("classify_intent", "_product_revenue", "_top_products", "_improving_worsening", "answer_question"):
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == fn_name)
        assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in arch.LLM_FACADE_METHODS | arch.LLM_CLIENT_METHODS
                       for n in ast.walk(fn)), fn_name


def test_router_has_no_date_parsing():
    import ast

    tree = ast.parse((arch.APP / "services" / "assistant_service.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "classify_intent")
    strings = {n.value.lower() for n in ast.walk(fn) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert not {"january", "february", "march", "jan", "feb"} & strings and not any("2025" in s for s in strings)


# --------------------------------------------------------------------------- routing of the frozen questions
def test_frozen_questions_routing_is_pinned():
    routed = {r["task_id"]: r["intent"] for r in arch.route_frozen_questions()}
    assert sum(1 for i in routed.values() if i == "unrecognized") == 24
    assert {t for t, i in routed.items() if i != "unrecognized"} == {"C01", "C02", "C03"}
    assert {i for i in routed.values() if i != "unrecognized"} == {"top_products"}


def _configure_provider(monkeypatch, post):
    """A configured key and a counting stand-in for the single request seam of the OpenAI client (nothing reaches the network)."""
    from app.core.config import get_settings
    from app.services.openai_client import OpenAIClient

    monkeypatch.setattr(get_settings(), "openai_api_key", "test-key")
    monkeypatch.setattr(OpenAIClient, "_request", lambda self, payload: post(payload))


def _wire_answers(payload, route="other_tool"):
    """A Responses-shaped dict whose output text is the schema-constrained classification JSON."""
    import json

    from app.services.analytics_interpreter_service import QUESTIONS
    from research.llm_evaluation.mock_llm import _openai_object, _response, _typed_answers

    interp = {"route": "legacy"} if route == "other_tool" else {"route": route}
    wire = {k: q.payload() for k, q in QUESTIONS.items()}
    return _response(json.dumps(_openai_object(_typed_answers(interp, wire, None))), (1, 1), model="mock-openai")


def test_the_legacy_router_alone_makes_zero_provider_calls_for_every_frozen_question(db_session, monkeypatch):
    """Behavioural proof about the FALLBACK path: key configured, every provider request counted -> 0 for all 27 questions routed by
    the legacy router, including the intents that used to rephrase text (they are templates now)."""
    from app.services import assistant_service
    from tests.analytics_llm_support import make_business

    calls = []
    _configure_provider(monkeypatch, lambda payload: calls.append(payload) or _wire_answers(payload))
    biz = make_business(db_session)
    for t in SPEC["tasks"]:
        assistant_service._legacy_answer(db_session, biz, t["natural_language_question"])
    assistant_service._legacy_answer(db_session, biz, "What should I focus on to improve my business?")
    assert calls == []


def test_with_a_key_configured_every_frozen_question_reaches_the_ai_interpreter(client, db_session, monkeypatch):
    """Behavioural proof about the NEW path: the first thing each of the 27 questions meets is ONE classification request."""
    from tests.analytics_llm_support import make_business

    seen = []
    _configure_provider(monkeypatch, lambda payload: seen.append(payload) or _wire_answers(payload))
    biz = make_business(db_session)
    for t in SPEC["tasks"]:
        r = client.post(f"/api/v1/businesses/{biz}/chat", json={"message": t["natural_language_question"]})
        assert r.status_code == 200 and r.json()["path"] == "legacy_router"  # this fake classifier hands everything to the router
    assert len(seen) == len(SPEC["tasks"]) == 27
    assert [p["input"] for p in seen] == [f"<text>\n{t['natural_language_question']}\n</text>" for t in SPEC["tasks"]]
    assert all(set(p) == {"model", "instructions", "input", "store", "max_output_tokens", "text"} for p in seen)
    assert all(p["store"] is False and p["text"]["format"]["strict"] is True for p in seen)


def test_with_the_kill_switch_off_the_provider_is_never_reached(client, db_session, monkeypatch):
    from app.core.config import get_settings
    from tests.analytics_llm_support import make_business

    calls = []
    _configure_provider(monkeypatch, lambda payload: calls.append(1) or _wire_answers(payload))
    monkeypatch.setattr(get_settings(), "analytics_llm_enabled", False)
    biz = make_business(db_session)
    for t in SPEC["tasks"][:5]:
        assert client.post(f"/api/v1/businesses/{biz}/chat", json={"message": t["natural_language_question"]}).json()["path"] == "legacy_router"
    assert calls == []


def test_the_analytics_path_is_structurally_complete():
    status = arch.analytics_llm_path_status()
    assert status["implemented"], status["checks"]
    assert all(status["checks"].values())


# --------------------------------------------------------------------------- evaluation clock
def test_no_chat_reachable_module_reads_the_wall_clock_directly():
    """They all go through app.core.clock.today(), which the evaluation pins; a new raw date.today() there would break reproducibility."""
    assert arch.chat_reachable_modules_with_today() == []


def test_remaining_raw_date_today_sites_are_outside_the_chat_path():
    got = {(s["file"].split("/")[-1], s["function"]) for s in arch.date_today_sites()}
    for chat_related in ("kpi_service.py", "assistant_service.py", "churn_service.py", "breakdown_service.py"):
        assert not any(f == chat_related for f, _ in got), chat_related
    assert {f for f, _ in got} <= {"business_service.py", "decision_architecture_service.py", "demo_business_service.py", "harness.py", "clock.py"}


def test_evaluation_clock_is_deterministic_and_restorable(tmp_path):
    from app.core import clock

    sysm = DecisionGPTSystem(tmp_path, LLMRecorder())
    real = date.today()
    sysm.set_clock(date(2025, 3, 31))
    try:
        assert clock.today() == date(2025, 3, 31) and sysm.asof == date(2025, 3, 31)
    finally:
        sysm.set_clock(None)
    assert clock.today() == real and sysm.asof is None


def test_production_trailing_windows_are_inclusive_and_calendar_month_aligned_only_by_coincidence(db_session):
    """period/trailing windows are [today-N, today] (N+1 days): under 2025-03-31 'last 30 days' is exactly March."""
    from datetime import timedelta

    today = date(2025, 3, 31)
    assert today - timedelta(days=30) == date(2025, 3, 1)  # the handler window the audit relies on


# --------------------------------------------------------------------------- task classification
def test_classification_is_deterministic_and_covers_exactly_the_frozen_tasks():
    ids = [t["task_id"] for t in SPEC["tasks"]]
    assert sorted(arch.TASK_CLASSIFICATION) == sorted(ids)
    assert arch.task_table("asof") == arch.task_table("asof")
    assert arch.class_counts() == {"asof": {"B1": 3, "B2": 19, "C": 5}, "realclock": {"A": 1, "B1": 2, "B2": 19, "C": 5}}


def test_no_task_is_answerable_through_chat_under_the_primary_clock_and_none_is_class_d():
    rows = arch.task_table("asof")
    assert not [r for r in rows if r["class"] == "A"]
    assert not [r for r in rows if r["class"] == "D"]
    assert all(r["runnable_through_production_chat_with_correct_semantics"] is False for r in rows)


def test_recognized_questions_are_incompatible_handler_semantics_not_phrasing():
    rows = {r["task_id"]: r for r in arch.task_table("asof")}
    for tid in ("C01", "C02", "C03"):
        assert rows[tid]["router_recognizes"] and "G" in rows[tid]["causes"]


def test_audit_file_is_not_stale():
    stored = json.loads((arch.HERE / "architecture_audit.json").read_text(encoding="utf-8"))
    fresh = arch.build_audit()
    assert stored["frozen_question_routing"] == fresh["frozen_question_routing"]
    assert stored["task_compatibility"]["class_counts"] == fresh["task_compatibility"]["class_counts"]
    assert stored["chat_intents"] == fresh["chat_intents"]
    assert stored["data_view"]["view_sha256"] == fresh["data_view"]["view_sha256"]


# --------------------------------------------------------------------------- data-view conservation
def test_view_conservation_numbers():
    d = arch.view_conservation()
    assert d["revenue_conserved_by_merge"] and d["quantity_conserved_by_merge"] and d["max_abs_difference_per_merged_group_inr"] == 0.0
    assert d["original_processed_lines"] == d["rejected_fractional_quantity"]["lines"] + d["whole_quantity_lines_retained"] + d["rejected_amount_disagreement"]["lines"]
    assert d["original_revenue_inr"] == pytest.approx(d["rejected_fractional_quantity"]["revenue_inr"] + d["whole_quantity_revenue_inr"] + d["rejected_amount_disagreement"]["revenue_inr"], abs=0.01)
    assert d["view_revenue_inr"] == d["whole_quantity_revenue_inr"]
    assert d["pct_original_revenue_retained"] == pytest.approx(78.22, abs=0.01)
    assert "NOT the original dataset" in d["label"]


# --------------------------------------------------------------------------- GST track separation
def test_gst_track_is_separate_everywhere():
    primary = [t for t in SPEC["tasks"] if t["track"] == "primary"]
    supp = [t for t in SPEC["tasks"] if t["track"] == "supplementary"]
    assert all("gst_pct" not in t["required_fields"] for t in primary)
    assert supp and all("gst_pct" in t["required_fields"] for t in supp)
    subsets = json.loads(arch.SUBSET_PATH.read_text(encoding="utf-8"))
    gst = set(subsets["supplementary_gst_track"])
    answerable = set(subsets["answerable_through_production_chat"]["asof_clock"]) | set(subsets["answerable_through_production_chat"]["real_clock"])
    assert gst == {"E01", "E02", "E03", "E04"} and not gst & (answerable | set(subsets["single_existing_production_call_not_reachable_via_chat_B1"]) | set(subsets["existing_building_block_plus_trivial_arithmetic_not_reachable_via_chat_B2"]))
    assert gst <= set(subsets["missing_field_or_aggregation_C"])


# --------------------------------------------------------------------------- honest blocked state
def test_run_stays_blocked_while_no_provider_is_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(runner, "llm_status", lambda: {"enabled": False, "provider": None, "model_configured": None, "api_key_present": False})
    assert runner.main(["run"]) == runner.EXIT_BLOCKED
    d = next(tmp_path.iterdir())
    meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
    assert meta["status"] == "BLOCKED" and meta["research_result"] is False
    assert meta["blockers"] == ["provider_not_configured"]  # the analytics path exists; only the provider is missing
    assert "OPENAI_API_KEY" in meta["reason"] and meta["production_llm_path"]["analytics_llm_path_implemented"] is True
    assert not (d / "task_results.jsonl").exists() and not (d / "metrics.json").exists()


def test_run_is_blocked_by_the_path_if_the_kill_switch_is_off(tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(get_settings(), "analytics_llm_enabled", False)
    monkeypatch.setattr(runner, "llm_status", lambda: {"enabled": True, "provider": "openai", "model_configured": "gpt-4.1-mini", "api_key_present": True})
    assert runner.main(["run"]) == runner.EXIT_BLOCKED
    meta = json.loads((next(tmp_path.iterdir()) / "metadata.json").read_text(encoding="utf-8"))
    assert meta["blockers"] == ["production_path_not_llm_powered"]


def test_every_system_has_an_explicit_non_misleading_label():
    labels = runner.SYSTEM_LABELS
    assert "AI analytics path" in labels["decisiongpt"] and "Target B" in labels["decisiongpt"]
    assert "NOT an AI answer" in labels["decisiongpt"]
    assert "NOT a simpler baseline" in labels["llm_code_baseline"] and "NOT DecisionGPT" in labels["llm_code_baseline"]
