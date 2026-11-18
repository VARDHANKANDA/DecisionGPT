"""The PRODUCTION provider path of POST /businesses/{id}/chat with a MOCKED OpenAI request seam (``OpenAIClient._request``):
route -> analytics_chat_service.get_llm() -> LLMService -> OpenAIClient -> (mock). The real client, schema building, response
validation, interpreter, deterministic engine and the explanation guard all run. Proves provider selection, fallback labelling,
numerical authority of the engine, tenant isolation and secret hygiene. No test reaches the network or spends credits."""
import json
import logging
from datetime import date

import httpx
import openai
import pytest

from app.analytics.query_presenter import fmt_inr
from app.core.config import get_settings
from app.services.analytics_interpreter_service import QUESTIONS
from app.services.openai_client import SYSTEM_EXPLAIN, OpenAIClient
from research.llm_evaluation.mock_llm import _openai_object, _response, _typed_answers
from tests.analytics_llm_support import make_business, ref_sum, seed_sales

KEY = "test-key-NOT-A-REAL-KEY-chat-path-0123456789"
QUESTION = "What were my sales in February 2025?"
RANK_QUESTION = "What were my top 4 products by sales in February 2025?"  # a multi-row ranking is the answer shape that may get a restatement
RANKING = {"operation": "ranking", "metric": "revenue", "group_by": "product", "direction": "desc"}
REQ = httpx.Request("POST", "https://api.openai.com/v1/responses")


def classification(route="calculate", **query):
    interp = {"route": "legacy"} if route == "legacy" else {"route": route, "query": {"operation": "aggregate", "metric": "revenue", **query}}
    wire = {k: q.payload() for k, q in QUESTIONS.items()}
    return _response(json.dumps(_openai_object(_typed_answers(interp, wire, None))), (900, 90), model="gpt-4.1-mini-2025-04-14")


class Seam:
    def __init__(self, classify, explain=None):
        self.classify, self.explain, self.payloads = classify, explain, []

    def __call__(self, client, payload):
        client.last_attempts += 1
        self.payloads.append(payload)
        item = self.explain if payload.get("instructions") == SYSTEM_EXPLAIN else self.classify
        if item is None:
            raise AssertionError("an unexpected request was sent")
        if isinstance(item, Exception):
            raise item
        return item

    @property
    def roles(self):
        return ["explain" if p.get("instructions") == SYSTEM_EXPLAIN else "classify" for p in self.payloads]


@pytest.fixture()
def keyed(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "openai_api_key", KEY)
    monkeypatch.setattr(s, "openai_model", "gpt-4.1-mini")
    monkeypatch.setattr(s, "openai_max_retries", 1)
    monkeypatch.setattr("time.sleep", lambda *_: None)


@pytest.fixture()
def shop(client, db_session):
    bid = make_business(db_session, "Shop")
    return bid, seed_sales(db_session, bid)


def install(monkeypatch, seam):
    monkeypatch.setattr(OpenAIClient, "_request", lambda client, payload: seam(client, payload))
    return seam


def ask(client, bid, text=QUESTION, headers=None):
    return client.post(f"/api/v1/businesses/{bid}/chat", json={"message": text}, headers=headers)


def expected_revenue(ref):
    return ref_sum(ref, "revenue", start=date(2025, 2, 1), end=date(2025, 2, 28))


# ------------------------------------------------------------------ provider selection and numerical authority
def test_the_model_classifies_the_engine_calculates_and_a_clear_answer_gets_no_second_request(client, shop, keyed, monkeypatch):
    bid, ref = shop
    seam = install(monkeypatch, Seam(classification()))  # an explanation request would raise: no explain reply is configured
    body = ask(client, bid).json()
    exp = expected_revenue(ref)
    assert seam.roles == ["classify"]  # one classification; the verified one-sentence answer needs no restatement
    assert body["path"] == "llm_analytics" and body["answer_type"] == "known"
    assert fmt_inr(exp) in body["answer"] and body["details"]["revenue_total"] == float(exp)  # the engine's number, from the seeded rows
    assert body["details"]["sections"]["interpretation"] is None
    # the model saw the question only - never a business id, row or other tenant's data
    sent = json.dumps(seam.payloads)
    assert bid not in sent and "Shop" not in sent and "BIG ONION" not in sent


def test_a_model_explanation_that_invents_a_number_is_dropped_and_the_figure_is_unchanged(client, shop, keyed, monkeypatch):
    bid, ref = shop
    seam = install(monkeypatch, Seam(classification(**RANKING), _response("Sales were roughly 9,99,999 in February.", (300, 40))))
    body = ask(client, bid, RANK_QUESTION).json()
    assert seam.roles == ["classify", "explain"]  # the restatement WAS requested, then rejected
    assert "9,99,999" not in body["answer"] and body["answer"].startswith("For February 2025, ranked by sales")
    assert body["details"]["sections"]["interpretation"] is None


def test_a_model_explanation_with_a_causal_claim_is_dropped(client, shop, keyed, monkeypatch):
    bid, ref = shop
    seam = install(monkeypatch, Seam(classification(**RANKING), _response("Sales were strong because of the festival.", (300, 40))))
    body = ask(client, bid, RANK_QUESTION).json()
    assert seam.roles == ["classify", "explain"]
    assert "festival" not in body["answer"] and body["details"]["sections"]["interpretation"] is None


def test_the_answer_survives_a_failed_explanation_request(client, shop, keyed, monkeypatch):
    bid, ref = shop
    seam = install(monkeypatch, Seam(classification(**RANKING), openai.APITimeoutError(request=REQ)))
    body = ask(client, bid, RANK_QUESTION).json()
    assert seam.roles == ["classify", "explain"]
    assert body["path"] == "llm_analytics" and body["answer"].startswith("For February 2025, ranked by sales")


def test_a_nonsense_classification_cannot_produce_a_number(client, shop, keyed, monkeypatch):
    bid, _ = shop
    seam = install(monkeypatch, Seam(_response(json.dumps({"route": {"choice": "run_sql", "confidence": 1.0}}), (1, 1))))
    body = ask(client, bid).json()
    assert body["path"] == "legacy_router" and body["notice"] and seam.roles == ["classify"]


# ------------------------------------------------------------------ honest fallback
@pytest.mark.parametrize("failure,expected_requests", [
    (openai.AuthenticationError("x", response=httpx.Response(401, request=REQ), body=None), 1),
    (openai.RateLimitError("x", response=httpx.Response(429, request=REQ), body={"code": "insufficient_quota"}), 1),
    (openai.RateLimitError("x", response=httpx.Response(429, request=REQ), body=None), 2),  # one bounded retry
    (openai.APITimeoutError(request=REQ), 1),
    (openai.APIConnectionError(request=REQ), 2),
    (openai.NotFoundError("x", response=httpx.Response(404, request=REQ), body={"code": "model_not_found"}), 1),
    (_response("not json", (1, 1)), 1),
    ({"model": "m", "status": "completed", "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}]}, 1),
])
def test_every_provider_failure_is_a_labelled_fallback_not_an_ai_result(client, shop, keyed, monkeypatch, failure, expected_requests):
    bid, _ = shop
    seam = install(monkeypatch, Seam(failure))
    body = ask(client, bid).json()
    assert body["path"] == "legacy_router" and body["notice"]
    assert "explain" not in seam.roles and len(seam.payloads) == expected_requests
    assert KEY not in json.dumps(body)


def test_without_a_key_nothing_is_sent_and_the_standard_assistant_answers(client, shop, monkeypatch):
    bid, _ = shop
    monkeypatch.setattr(get_settings(), "openai_api_key", None)
    seam = install(monkeypatch, Seam(classification()))
    body = ask(client, bid).json()
    assert seam.payloads == [] and body["path"] == "legacy_router"


def test_the_kill_switches(client, shop, keyed, monkeypatch):
    bid, ref = shop
    monkeypatch.setattr(get_settings(), "analytics_llm_enabled", False)
    seam = install(monkeypatch, Seam(classification()))
    assert ask(client, bid).json()["path"] == "legacy_router" and seam.payloads == []
    monkeypatch.setattr(get_settings(), "analytics_llm_enabled", True)
    monkeypatch.setattr(get_settings(), "analytics_explain_enabled", False)
    seam = install(monkeypatch, Seam(classification()))
    body = ask(client, bid).json()
    assert seam.roles == ["classify"] and fmt_inr(expected_revenue(ref)) in body["answer"]  # classification only, deterministic text


# ------------------------------------------------------------------ isolation and secrets
def test_another_tenant_is_refused_before_any_model_request(client, db_session, keyed, monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_enabled", True)
    a = client.post("/api/v1/auth/register", json={"email": "a@x.com", "password": "orange-river-4271", "role": "sme"}).json()["access_token"]
    b = client.post("/api/v1/auth/register", json={"email": "b@x.com", "password": "orange-river-4271", "role": "sme"}).json()["access_token"]
    biz = client.post("/api/v1/businesses", json={"name": "A Store", "industry": "retail", "business_type": "retail", "business_size": "small"},
                      headers={"Authorization": f"Bearer {a}"}).json()["id"]
    seam = install(monkeypatch, Seam(classification()))
    r = ask(client, biz, headers={"Authorization": f"Bearer {b}"})
    assert r.status_code in (403, 404) and seam.payloads == []
    assert ask(client, biz).status_code in (401, 403) and seam.payloads == []  # anonymous


def test_the_key_never_reaches_logs_or_responses(client, shop, keyed, monkeypatch, caplog):
    bid, _ = shop
    install(monkeypatch, Seam(classification(), _response("That is the total.", (1, 1))))
    with caplog.at_level(logging.DEBUG):
        body = ask(client, bid).json()
    assert KEY not in json.dumps(body) and KEY not in caplog.text
