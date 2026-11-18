"""End-to-end trace of one request through the real production code (mocked Jev only), plus the 27-task architecture dry-run.

NOT RESEARCH RESULTS: the mock supplies only typed decisions; every number is computed by the deterministic engine.
"""
import json
from decimal import Decimal

import pytest

from app.analytics import query_engine, query_presenter
from app.schemas.analytics_query import Interpretation
from app.services import analytics_answer_service, analytics_chat_service, analytics_interpreter_service, assistant_service
from tests.analytics_llm_support import FakeLLM, decision, make_business, seed_sales


def test_request_flows_through_each_stage_in_order(client, db_session, monkeypatch):
    """question -> endpoint -> assistant_service -> Jev typed decisions + deterministic extraction -> validated structured request
    -> deterministic engine -> verified result -> FACT text -> assembled answer. One Jev request; no model-written text."""
    bid = make_business(db_session)
    seed_sales(db_session, bid)
    qn = "What were the top 3 products by quantity in February 2025?"
    fake = FakeLLM({qn: decision(operation="ranking", metric="units", group_by="product")})
    monkeypatch.setattr(analytics_chat_service, "get_llm", lambda: fake)

    order: list[str] = []

    def spy(owner, name, label):
        real = getattr(owner, name)

        def wrapper(*a, **k):
            order.append(label)
            return real(*a, **k)

        monkeypatch.setattr(owner, name, wrapper)

    spy(assistant_service, "answer_question", "1 assistant_service.answer_question")
    spy(analytics_chat_service, "try_answer", "2 analytics_chat_service.try_answer")
    spy(analytics_interpreter_service, "interpret", "3 analytics_interpreter_service.interpret (one Jev request)")
    spy(Interpretation, "model_validate", "4 Interpretation.model_validate (strict schema)")
    spy(query_engine, "run_query", "5 query_engine.run_query (deterministic, business_id-scoped)")
    spy(query_presenter, "facts", "6 query_presenter.facts (verified FACT text)")
    spy(analytics_answer_service, "assemble", "7 analytics_answer_service.assemble")

    # the route calls assistant_service.answer_question by attribute, so the spy sees it
    r = client.post(f"/api/v1/businesses/{bid}/chat", json={"message": qn})
    assert r.status_code == 200
    assert order == [
        "1 assistant_service.answer_question",
        "2 analytics_chat_service.try_answer",
        "3 analytics_interpreter_service.interpret (one Jev request)",
        "4 Interpretation.model_validate (strict schema)",
        "5 query_engine.run_query (deterministic, business_id-scoped)",
        "6 query_presenter.facts (verified FACT text)",
        "7 analytics_answer_service.assemble",
    ]
    body = r.json()
    assert body["path"] == "llm_analytics" and len(fake.calls) == 1
    assert body["details"]["sections"]["fact"] in body["answer"]
    assert body["details"]["sections"]["interpretation"] is None and body["details"]["sections"]["suggestion"] is None
    assert fake.calls[0]["state"] == qn  # Jev was handed the question, not data, and was not asked for numbers


def test_product_ranking_leads_with_the_winner_not_the_filter(client, db_session, monkeypatch):
    bid = make_business(db_session)
    seed_sales(db_session, bid)
    qn = "Which sold more units, BIG ONION or MILK?"
    fake = FakeLLM({qn: decision(operation="ranking", metric="units", group_by="product", named_products=0.95)})
    monkeypatch.setattr(analytics_chat_service, "get_llm", lambda: fake)
    answer = client.post(f"/api/v1/businesses/{bid}/chat", json={"message": qn}).json()["answer"]
    first = min((answer.index(n), n) for n in ("BIG ONION", "MILK"))[1]
    rows = client.post(f"/api/v1/businesses/{bid}/chat", json={"message": qn}).json()["details"]["table"]
    assert first == rows[0]["product"]  # the first product named is the one that sold more


def test_fractional_quantities_would_be_carried_and_formatted_exactly():
    """The engine sums with Decimal and the presenter prints non-integers; only Sale.quantity (Integer) stops weighed quantities
    from being stored today. Nothing in the analytics path assumes whole units."""
    assert query_presenter.fmt_num(Decimal("12.5")) == "12.50"
    assert query_presenter.fmt_num(Decimal("1234567.25")) == "12,34,567.25"
    assert query_presenter.fmt_num(Decimal("1234567")) == "12,34,567"
    assert query_presenter.fmt_inr(Decimal("435473.616")) == "₹4,35,474"
    assert query_presenter.fmt_inr(Decimal("42.5")) == "₹42.50"
    assert query_engine._d("2.375") + query_engine._d("0.125") == Decimal("2.500")  # noqa: SLF001 - exact decimal arithmetic


def test_27_frozen_tasks_flow_through_the_llm_path_with_a_mocked_llm(tmp_path, monkeypatch):
    """Architecture dry-run (NOT research results): 27/27 flow through the LLM analytics path; the 23 primary questions get a verified
    engine answer that agrees with the independent pandas ground-truth engine; the 4 GST questions are refused as unsupported."""
    import research.llm_evaluation.audit.llm_path_dryrun as dry

    monkeypatch.setattr(dry, "OUT", tmp_path / "dryrun.json")
    assert dry.main() == 0
    d = json.loads((tmp_path / "dryrun.json").read_text(encoding="utf-8"))
    assert d["research_result"] is False and "NOT RESEARCH RESULTS" in d["BANNER"] and d["frozen_spec_modified"] is False
    assert d["n_tasks"] == 27 and d["flowed_through_llm_analytics_path"] == 27
    assert d["primary"] == {"n": 23, "engine_produced_a_verified_answer": 23, "engine_matches_independent_ground_truth_engine": 23}
    assert d["supplementary_gst"]["correctly_refused_as_unsupported"] == 4
    assert d["mock_llm_calls"] == {"interpreter": 27}  # one Jev request per question; there is no explainer call
    assert d["ingestion_matches_view"] is True
