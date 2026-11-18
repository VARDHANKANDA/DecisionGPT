"""Chat route, end to end, with MOCKED providers: the optional explanation step and the capability (missing-data) policy.

Assertions cover both the returned answer and the number of provider requests of each kind. No test reaches the network, spends credits
or reads a key. Numbers in assertions come from plain-Python arithmetic on the seeded rows, never from the model."""
import json

import httpx
import pytest

from app.analytics.query_presenter import fmt_inr
from app.core.config import get_settings
from app.services import analytics_chat_service
from app.services.openai_client import ExplainResult, OpenAIClient
from tests.analytics_llm_support import FakeLLM, decision, failure, make_business, ref_sum, seed_sales
from tests.integration.test_analytics_llm_chat import _audit
from tests.integration.test_openai_chat_path import KEY, RANK_QUESTION, RANKING, Seam, classification, install, keyed  # noqa: F401  (fixture)
from research.llm_evaluation.mock_llm import _response

TOP4 = "What were my top 4 products by sales in February 2025?"
TOTAL = "What were my sales in February 2025?"
GST = "How much of my sales between January and March 2025 came from items with 5% GST?"
USEFUL = "RED ONION led, ahead of BIG ONION, with EGG last of the four."


class ExplainFake(FakeLLM):
    """FakeLLM that also answers the explanation request, and counts both kinds of request."""

    def __init__(self, script=None, explanation=None):
        super().__init__(script)
        self.explanation, self.explain_calls = explanation, []

    def explain(self, question, facts, notes):
        self.explain_calls.append({"question": question, "facts": list(facts), "notes": list(notes)})
        if isinstance(self.explanation, Exception):
            raise self.explanation
        if isinstance(self.explanation, ExplainResult):
            return self.explanation
        return ExplainResult(True, self.explanation, None, 0.01, "gpt-4.1-mini", "gpt-4.1-mini-2025-04-14", {"input_tokens": 100, "output_tokens": 20})


def ask(client, bid, text, headers=None):
    return client.post(f"/api/v1/businesses/{bid}/chat", json={"message": text}, headers=headers)


@pytest.fixture()
def shop(client, db_session):
    bid = make_business(db_session, "Shop")
    return bid, seed_sales(db_session, bid)


def use(monkeypatch, fake):
    monkeypatch.setattr(analytics_chat_service, "get_llm", lambda: fake)
    return fake


def ranking_llm(question=TOP4, explanation=USEFUL):
    return ExplainFake({question: decision(operation="ranking", metric="revenue", group_by="product")}, explanation)


# ------------------------------------------------------------------ 1-3, 7: the guard in the real route
def test_a_valid_explanation_adds_context_between_fact_and_caveat(client, shop, monkeypatch):
    bid, _ = shop
    fake = use(monkeypatch, ranking_llm())
    body = ask(client, bid, TOP4).json()
    a = body["answer"]
    assert len(fake.calls) == 1 and len(fake.explain_calls) == 1  # one classification, one explanation
    assert USEFUL in a and a.index("ranked by sales") < a.index(USEFUL) < a.index("This is based on the sales recorded")
    assert body["details"]["sections"]["interpretation"] == USEFUL
    assert _audit(client.app, bid)["explanation_source"] == "openai"


@pytest.mark.parametrize("explanation,reason", [
    ("RED ONION led, ahead of BIG ONION. RED ONION led, ahead of BIG ONION.", "duplicate_sentence"),                       # exact duplicate
    ("This is based on the sales recorded in your uploaded data.", "duplicate_of_verified_sentence"),                      # repeats the caveat
    ("RED ONION made ₹3,180 and BIG ONION made ₹2,950.", None),                                                            # repeats numbers, adds nothing
    ("RED ONION led with ₹3,810, ahead of BIG ONION.", "number_not_in_verified_facts"),                                     # changed number
    ("Customers prefer RED ONION over BIG ONION.", "unsupported_term"),                                                    # unsupported claim
    ("RED ONION led because of the festival.", "causal_claim"),
    ("You should stock more RED ONION.", "advice"),
    ("RED ONION led for the whole month.", "unsupported_completeness_claim"),
    ("", "empty"), ("NONE", "no_additional_context"), ('{"a": 1}', "malformed"),
])
def test_a_bad_explanation_falls_back_to_the_verified_answer(client, shop, monkeypatch, explanation, reason):
    bid, _ = shop
    baseline_llm = use(monkeypatch, ranking_llm(explanation="NONE"))
    baseline = ask(client, bid, TOP4).json()["answer"]  # the deterministic text, for comparison
    assert baseline_llm.explain_calls  # the request was made and rejected
    fake = use(monkeypatch, ranking_llm(explanation=explanation))
    body = ask(client, bid, TOP4).json()
    assert body["answer"] == baseline  # byte-identical: facts + caveat only
    assert body["details"]["sections"]["interpretation"] is None and body["path"] == "llm_analytics"
    audit = _audit(client.app, bid)
    assert audit["explanation_source"] == "template" and len(fake.explain_calls) == 1
    if reason:
        assert audit["explanation_rejected"] == reason


def test_the_caveat_survives_every_accepted_explanation(client, shop, monkeypatch):
    bid, _ = shop
    use(monkeypatch, ranking_llm())
    a = ask(client, bid, TOP4).json()["answer"]
    assert a.endswith("This is based on the sales recorded in your uploaded data.")


# ------------------------------------------------------------------ the request is skipped when the answer is already clear
def test_a_clear_one_sentence_answer_makes_no_explanation_request(client, shop, monkeypatch):
    bid, ref = shop
    fake = use(monkeypatch, ExplainFake({TOTAL: decision(operation="aggregate", metric="revenue")}, USEFUL))
    body = ask(client, bid, TOTAL).json()
    exp = ref_sum(ref, "revenue", start=__import__("datetime").date(2025, 2, 1), end=__import__("datetime").date(2025, 2, 28))
    assert fmt_inr(exp) in body["answer"]
    assert len(fake.calls) == 1 and fake.explain_calls == []
    assert _audit(client.app, bid)["explanation_skipped"] == "answer_already_clear"


# ------------------------------------------------------------------ 9: explanation mode disabled (no request; classification unaffected)
def test_disabled_explanations_send_no_request_but_questions_are_still_interpreted(client, shop, monkeypatch):
    bid, _ = shop
    monkeypatch.setattr(get_settings(), "analytics_explain_enabled", False)
    fake = use(monkeypatch, ranking_llm())
    body = ask(client, bid, TOP4).json()
    assert body["path"] == "llm_analytics" and body["intent"] == "analytics_query"  # interpretation and calculation still run
    assert body["details"]["table"] and USEFUL not in body["answer"]
    assert len(fake.calls) == 1 and fake.explain_calls == []
    assert _audit(client.app, bid)["explanation_skipped"] == "disabled"


def test_disabled_explanations_through_the_real_client_send_exactly_one_request(client, shop, keyed, monkeypatch):  # noqa: F811
    bid, _ = shop
    monkeypatch.setattr(get_settings(), "analytics_explain_enabled", False)
    seam = install(monkeypatch, Seam(classification(**RANKING)))  # an explanation request would raise: no reply is configured
    body = ask(client, bid, RANK_QUESTION).json()
    assert seam.roles == ["classify"] and len(seam.payloads) == 1
    assert body["path"] == "llm_analytics" and body["details"]["sections"]["interpretation"] is None and KEY not in json.dumps(body)


def test_enabled_explanations_through_the_real_client_send_classification_plus_one(client, shop, keyed, monkeypatch):  # noqa: F811
    bid, _ = shop
    monkeypatch.setattr(get_settings(), "analytics_explain_enabled", True)
    seam = install(monkeypatch, Seam(classification(**RANKING), _response(USEFUL, (300, 30))))
    body = ask(client, bid, RANK_QUESTION).json()
    assert seam.roles == ["classify", "explain"] and USEFUL in body["answer"]


# ------------------------------------------------------------------ 14: fallback provenance and error handling
@pytest.mark.parametrize("explanation", [
    ExplainResult(False, None, "timeout", 0.5, "gpt-4.1-mini"),
    ExplainResult(False, None, "provider_error", 0.5, "gpt-4.1-mini"),
    RuntimeError("provider layer exploded"),
])
def test_a_failed_explanation_never_costs_the_verified_answer(client, shop, monkeypatch, explanation):
    bid, _ = shop
    fake = use(monkeypatch, ranking_llm(explanation=explanation))
    body = ask(client, bid, TOP4).json()
    assert body["path"] == "llm_analytics" and body["notice"] is None and body["answer_type"] == "known"
    assert "ranked by sales" in body["answer"] and body["details"]["sections"]["interpretation"] is None
    assert len(fake.explain_calls) == 1
    audit = _audit(client.app, bid)
    assert audit["explanation_source"] == "template" and audit["explanation_error"] in {"timeout", "provider_error", "exception"}


def test_a_failed_classification_is_a_labelled_fallback_and_asks_for_no_explanation(client, shop, monkeypatch):
    bid, _ = shop
    fake = use(monkeypatch, ExplainFake({TOP4: failure("timeout")}, USEFUL))
    body = ask(client, bid, TOP4).json()
    assert body["path"] == "legacy_router" and body["notice"] and fake.explain_calls == []


# ------------------------------------------------------------------ 10-13: GST / missing data / clarification / supported
@pytest.mark.parametrize("route,extra", [
    ("calculate", {"operation": "share_of_total", "named_products": 0.9}),
    ("clarify", {"clarify_about": "product"}),
    ("missing_data", {"missing_item": "gst_or_tax"}),
])
def test_missing_gst_data_gets_one_consistent_refusal_without_a_made_up_figure(client, shop, monkeypatch, route, extra):
    bid, _ = shop
    fake = use(monkeypatch, ExplainFake({GST: decision(route=route, **extra)}, USEFUL))
    body = ask(client, bid, GST).json()
    assert body["intent"] == "analytics_unsupported" and body["answer_type"] == "none" and body["sufficient_evidence"] is False
    assert "doesn't contain GST or tax information" in body["answer"] and "won't estimate it" in body["answer"]
    assert "Which product" not in body["answer"] and "₹" not in body["answer"] and "%" not in body["answer"].replace("5%", "")
    assert body["details"].get("missing_data") == "GST or tax information"
    assert len(fake.calls) == 1 and fake.explain_calls == []


def test_a_clarification_that_cannot_resolve_missing_data_is_never_asked(client, shop, monkeypatch):
    bid, _ = shop
    use(monkeypatch, ExplainFake({"Which product has the most GST?": decision(route="clarify", clarify_about="product")}))
    body = ask(client, bid, "Which product has the most GST?").json()
    assert body["answer_type"] != "clarification" and "Which product do you mean" not in body["answer"]


def test_an_ambiguous_question_the_data_can_answer_is_clarified_then_answered(client, shop, monkeypatch):
    bid, _ = shop
    fake = use(monkeypatch, ExplainFake({
        "Onion sales?": decision(operation="aggregate", metric="revenue", named_products=0.9),
        "RED ONION sales in February 2025?": decision(operation="aggregate", metric="revenue", named_products=0.9),
    }))
    first = ask(client, bid, "Onion sales?").json()
    assert first["answer_type"] == "clarification" and "BIG ONION" in first["answer"] and "RED ONION" in first["answer"]
    second = ask(client, bid, "RED ONION sales in February 2025?").json()
    assert second["answer_type"] == "known" and second["details"]["revenue_total"] > 0
    assert len(fake.calls) == 2 and fake.explain_calls == []


def test_supported_non_gst_questions_are_unaffected(client, shop, monkeypatch):
    bid, ref = shop
    qs = {
        TOTAL: decision(operation="aggregate", metric="revenue"),
        "How many units did I sell in February 2025?": decision(operation="aggregate", metric="units"),
        "Which weekday had the most sales in February 2025?": decision(operation="ranking", metric="revenue", group_by="weekday"),
    }
    fake = use(monkeypatch, ExplainFake(qs, USEFUL))
    for q in qs:
        body = ask(client, bid, q).json()
        assert body["path"] == "llm_analytics" and body["answer_type"] == "known" and body["intent"] == "analytics_query", q
    assert len(fake.calls) == 3 and fake.explain_calls == []


def test_the_standard_assistant_applies_the_same_policy_when_the_model_is_off(client, shop, monkeypatch):
    bid, _ = shop
    monkeypatch.setattr(get_settings(), "openai_api_key", None)
    body = ask(client, bid, "How much GST did I collect last month?").json()
    assert body["path"] == "legacy_router"  # labelled as the standard assistant, not as an AI answer
    assert body["intent"] == "analytics_unsupported" and body["sufficient_evidence"] is False
    assert "doesn't contain GST or tax information" in body["answer"]
    ok = ask(client, bid, "Which are my top selling products?").json()
    assert ok["path"] == "legacy_router" and ok["intent"] == "top_products"  # unrelated legacy intents still answer


def test_a_failed_classification_on_a_gst_question_still_refuses_and_is_labelled(client, shop, monkeypatch):
    bid, _ = shop
    use(monkeypatch, ExplainFake({GST: failure("low_confidence")}))
    body = ask(client, bid, GST).json()
    assert body["path"] == "legacy_router" and body["notice"] and body["sufficient_evidence"] is False
    assert "doesn't contain GST or tax information" in body["answer"]


# ------------------------------------------------------------------ 15: tenant isolation
def test_the_explanation_only_ever_sees_the_requesting_businesses_verified_facts(client, db_session, monkeypatch):
    a = make_business(db_session, "Shop A")
    seed_sales(db_session, a, scale=1)
    b = make_business(db_session, "Shop B")
    ref_b = seed_sales(db_session, b, scale=7)
    fake = use(monkeypatch, ranking_llm())
    body = ask(client, a, TOP4).json()
    assert len(fake.explain_calls) == 1
    sent = json.dumps(fake.explain_calls)
    top_b = ref_sum(ref_b, "revenue", start=__import__("datetime").date(2025, 2, 1), end=__import__("datetime").date(2025, 2, 28), product="RED ONION")
    assert fmt_inr(top_b) not in sent and fmt_inr(top_b) not in body["answer"]
    assert a not in sent and b not in sent and "Shop A" not in sent


def test_a_business_cannot_be_queried_through_another_tenants_token(client, db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_enabled", True)
    t1 = client.post("/api/v1/auth/register", json={"email": "p@x.com", "password": "orange-river-4271", "role": "sme"}).json()["access_token"]
    t2 = client.post("/api/v1/auth/register", json={"email": "q@x.com", "password": "orange-river-4271", "role": "sme"}).json()["access_token"]
    biz = client.post("/api/v1/businesses", json={"name": "P Store", "industry": "retail", "business_type": "retail", "business_size": "small"},
                      headers={"Authorization": f"Bearer {t1}"}).json()["id"]
    fake = use(monkeypatch, ranking_llm())
    r = ask(client, biz, TOP4, headers={"Authorization": f"Bearer {t2}"})
    assert r.status_code in (403, 404) and fake.calls == [] and fake.explain_calls == []
