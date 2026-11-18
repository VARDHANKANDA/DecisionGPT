"""OpenAI client: request contract (strict structured output), response validation, error classification, bounded retries,
no secret leakage, and the explanation guard. MOCKED: the SDK's request seam is replaced; no test reaches the network."""
import json
import logging

import httpx
import openai
import pytest

from app.core.config import get_settings
from app.services import analytics_answer_service as aas
from app.services import openai_client as oc
from app.services.openai_client import Choice, Noul, OpenAIClient

KEY = "test-key-NOT-A-REAL-KEY-0123456789abcdef"
Q = {
    "intent": Choice("What is asked?", {"a": "first thing", "b": "second thing"}),
    "urgent": Noul("Is it urgent?"),
}
REQ = httpx.Request("POST", "https://api.openai.com/v1/responses")


def resp_text(obj, usage=(321, 40), model="gpt-4.1-mini-2025-04-14", status="completed"):
    return {"id": "resp_x", "model": model, "status": status, "usage": {"input_tokens": usage[0], "output_tokens": usage[1]},
            "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": obj if isinstance(obj, str) else json.dumps(obj)}]}]}


GOOD = {"intent": {"choice": "b", "confidence": 0.8}, "urgent": {"probability": 0.9}}


@pytest.fixture()
def configured(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "openai_api_key", KEY)
    monkeypatch.setattr(s, "openai_model", "gpt-4.1-mini")
    monkeypatch.setattr(s, "openai_max_retries", 1)
    monkeypatch.setattr("time.sleep", lambda *_: None)


class Seam:
    """Replaces OpenAIClient._request; records payloads; plays a script of results/exceptions (one per call)."""

    def __init__(self, *script):
        self.script, self.payloads = list(script), []

    def __call__(self, client, payload):
        client.last_attempts += 1
        self.payloads.append(payload)
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item


def run(monkeypatch, *script, state="Is my order late?", questions=Q):
    seam = Seam(*script)
    monkeypatch.setattr(OpenAIClient, "_request", lambda client, payload: seam(client, payload))
    return OpenAIClient().decide(state, questions), seam


def status_error(cls, status, code=None):
    return cls("boom", response=httpx.Response(status, request=REQ), body={"code": code} if code else None)


# ---------------------------------------------------------------------------------------------- request contract
def test_request_is_a_strict_schema_constrained_responses_call(configured, monkeypatch):
    out, seam = run(monkeypatch, resp_text(GOOD))
    assert out.ok and len(seam.payloads) == 1
    p = seam.payloads[0]
    assert set(p) == {"model", "instructions", "input", "store", "max_output_tokens", "text"}
    assert p["model"] == "gpt-4.1-mini" and p["store"] is False and p["instructions"] == oc.SYSTEM_DECIDE
    assert p["input"] == "<text>\nIs my order late?\n</text>"  # the question only, in a fixed wrapper: no rows, ids or names
    fmt = p["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True
    sch = fmt["schema"]
    assert sch["additionalProperties"] is False and sch["required"] == ["intent", "urgent"]
    assert sch["properties"]["intent"]["properties"]["choice"]["enum"] == ["a", "b"]  # only labels the application knows
    assert sch["properties"]["intent"]["additionalProperties"] is False and sch["properties"]["urgent"]["required"] == ["probability"]
    assert "temperature" not in p and "tools" not in p  # no tools, no free generation


def test_the_sdk_is_built_with_no_internal_retries_and_the_configured_timeout(configured, monkeypatch):
    seen = {}

    class Fake:
        def __init__(self, **kw):
            seen.update(kw)
            self.responses = type("R", (), {"create": staticmethod(lambda **k: type("X", (), {"model_dump": lambda self: resp_text(GOOD)})())})()

    monkeypatch.setattr(openai, "OpenAI", Fake)
    monkeypatch.setattr(get_settings(), "openai_timeout_seconds", 7)
    out = OpenAIClient().decide("hello", Q)
    assert out.ok and seen == {"api_key": KEY, "timeout": 7, "max_retries": 0}


def test_valid_output_is_parsed_with_model_and_usage(configured, monkeypatch):
    out, _ = run(monkeypatch, resp_text(GOOD))
    assert out.provider == "openai" and out.error is None and out.attempts == 1
    assert out.choice("intent").value == "b" and out.choice("intent").confidence == 0.8
    assert out.noul("urgent") == 0.9
    assert out.model == "gpt-4.1-mini" and out.response_model == "gpt-4.1-mini-2025-04-14"
    assert out.usage == {"input_tokens": 321, "output_tokens": 40}


# ---------------------------------------------------------------------------------------------- configuration
def test_missing_or_blank_key_sends_nothing(monkeypatch):
    s = get_settings()
    for v in (None, ""):
        monkeypatch.setattr(s, "openai_api_key", v)
        out, seam = run(monkeypatch, resp_text(GOOD))
        assert not out.ok and out.error == "not_configured" and seam.payloads == []
        assert s.llm_enabled is False and s.analytics_llm_active is False


def test_empty_oversized_or_unsupported_input_is_refused_locally(configured, monkeypatch):
    for state in ("", "   ", "x" * (oc.MAX_STATE_CHARS + 1), None):
        out, seam = run(monkeypatch, resp_text(GOOD), state=state)
        assert out.error == "invalid_request" and seam.payloads == []
    out, seam = run(monkeypatch, resp_text(GOOD), questions={})
    assert out.error == "invalid_request" and seam.payloads == []


# ---------------------------------------------------------------------------------------------- response validation
@pytest.mark.parametrize("name,body,kind", [
    ("label not offered", {"intent": {"choice": "run_sql", "confidence": 0.9}, "urgent": {"probability": 0.5}}, "malformed_output"),
    ("missing question", {"intent": {"choice": "a", "confidence": 0.9}}, "malformed_output"),
    ("confidence out of range", {"intent": {"choice": "a", "confidence": 1.7}, "urgent": {"probability": 0.5}}, "malformed_output"),
    ("probability is a bool", {"intent": {"choice": "a", "confidence": 0.9}, "urgent": {"probability": True}}, "malformed_output"),
    ("not an object", ["a"], "malformed_output"),
    ("not json", "this is not json", "malformed_output"),
    ("empty text", "   ", "empty_response"),
])
def test_malformed_output_is_rejected_whole(configured, monkeypatch, name, body, kind):
    out, _ = run(monkeypatch, resp_text(body))
    assert not out.ok and out.error == kind and out.answers == {}, name


def test_refusal_incomplete_and_empty_responses(configured, monkeypatch):
    refusal = {"model": "m", "status": "completed", "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "I cannot help with that"}]}]}
    assert run(monkeypatch, refusal)[0].error == "refusal"
    assert run(monkeypatch, resp_text(GOOD, status="incomplete"))[0].error == "malformed_output"
    assert run(monkeypatch, {"model": "m", "status": "completed", "output": []})[0].error == "empty_response"


def test_extra_keys_from_the_model_are_ignored_not_trusted(configured, monkeypatch):
    out, _ = run(monkeypatch, resp_text({**GOOD, "sql": "DROP TABLE sales", "revenue": 1e9}))
    assert out.ok and set(out.answers) == {"intent", "urgent"}


# ---------------------------------------------------------------------------------------------- error classification and retries
@pytest.mark.parametrize("exc,kind,requests", [
    (status_error(openai.AuthenticationError, 401), "authentication_failed", 1),
    (status_error(openai.PermissionDeniedError, 403), "authentication_failed", 1),
    (status_error(openai.RateLimitError, 429, "insufficient_quota"), "quota_exceeded", 1),  # billing limit: never retried
    (status_error(openai.NotFoundError, 404, "model_not_found"), "unsupported_model", 1),
    (status_error(openai.BadRequestError, 400, "model_not_found"), "unsupported_model", 1),
    (status_error(openai.BadRequestError, 400), "invalid_request", 1),
    (status_error(openai.InternalServerError, 500), "provider_error", 1),  # may have been billed: never retried
    (openai.APITimeoutError(request=REQ), "timeout", 1),  # ambiguous: never retried
])
def test_errors_are_classified_and_unsafe_ones_are_not_retried(configured, monkeypatch, exc, kind, requests):
    out, seam = run(monkeypatch, exc)
    assert not out.ok and out.error == kind and len(seam.payloads) == requests and out.attempts == requests


def test_rate_limit_and_connection_errors_get_one_bounded_retry(configured, monkeypatch):
    out, seam = run(monkeypatch, status_error(openai.RateLimitError, 429), resp_text(GOOD))
    assert out.ok and len(seam.payloads) == 2 and out.attempts == 2
    out, seam = run(monkeypatch, openai.APIConnectionError(request=REQ))  # keeps failing
    assert out.error == "network_error" and len(seam.payloads) == 2  # 1 try + max_retries=1, then stop
    monkeypatch.setattr(get_settings(), "openai_max_retries", 0)
    out, seam = run(monkeypatch, status_error(openai.RateLimitError, 429))
    assert out.error == "rate_limited" and len(seam.payloads) == 1


def test_retries_are_capped_even_if_misconfigured(configured, monkeypatch):
    monkeypatch.setattr(get_settings(), "openai_max_retries", 99)
    assert OpenAIClient().max_retries == 2
    out, seam = run(monkeypatch, openai.APIConnectionError(request=REQ))
    assert len(seam.payloads) == 3 and out.error == "network_error"


# ---------------------------------------------------------------------------------------------- secrets
def test_the_key_never_appears_in_results_errors_or_logs(configured, monkeypatch, caplog):
    leaky = status_error(openai.AuthenticationError, 401)
    leaky.message = f"Incorrect API key provided: {KEY}"
    with caplog.at_level(logging.DEBUG):
        for item in (leaky, openai.APIConnectionError(message=f"could not reach host with {KEY}", request=REQ), resp_text("not json " + KEY)):
            out, _ = run(monkeypatch, item)
            assert not out.ok
            assert KEY not in json.dumps(out.__dict__, default=str)
    assert KEY not in caplog.text
    assert KEY not in repr(get_settings())


def test_classify_exception_never_uses_the_exception_message():
    kind, retry = OpenAIClient.classify_exception(RuntimeError(KEY))
    assert (kind, retry) == ("provider_error", False)


# ---------------------------------------------------------------------------------------------- explanation
def test_explain_returns_text_with_usage(configured, monkeypatch):
    seam = Seam(resp_text("Your sales for February were 13,86,969."))
    monkeypatch.setattr(OpenAIClient, "_request", lambda client, payload: seam(client, payload))
    r = OpenAIClient().explain("What were my sales?", ["Your total sales were ₹13,86,969."], ["Based on your data."])
    assert r.ok and r.text.startswith("Your sales") and r.usage == {"input_tokens": 321, "output_tokens": 40}
    p = seam.payloads[0]
    assert p["instructions"] == oc.SYSTEM_EXPLAIN and "text" not in p and p["store"] is False
    assert "₹13,86,969" in p["input"] and "tools" not in p


def test_explain_failures_are_classified(configured, monkeypatch):
    for item, kind in ((status_error(openai.RateLimitError, 429, "insufficient_quota"), "quota_exceeded"), (resp_text(""), "empty_response")):
        seam = Seam(item)
        monkeypatch.setattr(OpenAIClient, "_request", lambda client, payload, seam=seam: seam(client, payload))
        r = OpenAIClient().explain("q", ["fact"], [])
        assert not r.ok and r.error == kind and r.text is None
    monkeypatch.setattr(get_settings(), "openai_api_key", None)
    assert OpenAIClient().explain("q", ["f"], []).error == "not_configured"


FACTS = ["Your total sales for February 2025 were ₹13,86,969."]
NOTES = ["This is based on 200 sales records.", "Your data covers 1 January 2025 to 31 March 2025."]


@pytest.mark.parametrize("text,ok,why", [
    # a restatement built only from the verified words and numbers adds nothing; the deterministic text is shown instead
    ("Sales for February were ₹13,86,969, based on 200 records.", False, "adds_no_new_context"),
    ("Sales were 13,86,969 in February.", False, "restates_verified_sentence"),
    ("Sales were about 14 lakh in February.", False, "number_not_in_verified_facts"),
    ("Sales were ₹13,86,970.", False, "number_not_in_verified_facts"),
    ("Sales rose 12% in February.", False, "number_not_in_verified_facts"),
    ("Sales were high because of the festival.", False, "causal_claim"),
    ("Sales were driven by marketing.", False, "causal_claim"),
    ("You should raise your prices.", False, "advice"),
    ("See <b>this</b> or https://example.com", False, "markup_or_link"),
    ("x" * 401, False, "too_long"),
    ("", False, "empty"),
    (None, False, "empty"),
])
def test_explanation_is_shown_only_if_it_adds_no_number_cause_or_advice(text, ok, why):
    assert aas.validate_explanation(text, FACTS, NOTES) == (ok, why)


def test_assemble_keeps_the_fact_first_and_the_restatement_after_it():
    exp = aas.Explanation(interpretation="That is the total for the month.", source="openai")
    assert aas.assemble(FACTS, NOTES, exp).startswith(FACTS[0] + " That is the total for the month.")  # assemble only orders text
    assert aas.assemble(FACTS, NOTES) == " ".join(FACTS + NOTES)


def test_reasoning_models_get_a_low_effort_setting_and_output_headroom(configured, monkeypatch):
    monkeypatch.setattr(get_settings(), "openai_model", "gpt-5-mini")
    out, seam = run(monkeypatch, resp_text(GOOD))
    p = seam.payloads[0]
    assert out.ok and p["reasoning"] == {"effort": "low"} and p["max_output_tokens"] == 1500 and "temperature" not in p
    for plain in ("gpt-4.1-mini", "gpt-4o-mini"):
        monkeypatch.setattr(get_settings(), "openai_model", plain)
        _, seam = run(monkeypatch, resp_text(GOOD))
        assert "reasoning" not in seam.payloads[0] and seam.payloads[0]["max_output_tokens"] == 700
    assert oc.is_reasoning_model("gpt-5") and oc.is_reasoning_model("o3-mini") and not oc.is_reasoning_model("gpt-4.1")


def test_the_research_recorder_enforces_a_strict_per_request_cap(configured, monkeypatch):
    from research.llm_evaluation.llm_instrument import LLMRecorder

    sent = []
    monkeypatch.setattr(OpenAIClient, "_request", lambda client, payload: (sent.append(1), resp_text(GOOD))[1])
    rec = LLMRecorder()
    rec.max_calls = 2
    rec.install()
    try:
        outs = [OpenAIClient().decide("Is my order late?", Q) for _ in range(3)]
    finally:
        rec.uninstall()
    assert [o.ok for o in outs] == [True, True, False]  # the third request was never sent
    assert len(sent) == 2 and sum(1 for c in rec.calls if c.get("ok")) == 2
    assert rec.calls[-1].get("cap_reached") is True and rec.calls[-1]["attempts"] == 0
