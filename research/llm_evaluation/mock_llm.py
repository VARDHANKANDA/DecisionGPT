"""Wire-level MOCK OpenAI provider for infrastructure validation.   *** NOT A REAL MODEL; NOTHING PRODUCED HERE IS A RESEARCH RESULT ***

It replaces only ``OpenAIClient._request`` (the single SDK call, the last line before the network), so the real client, schema
building, response parsing/validation, error classification, ``LLMService.decide``, the production analytics path (classification +
deterministic extraction + query engine), the measurement recorder and the audit trail all run exactly as they will with the real
provider. The mock "model" is told nothing about answers: for each question it returns the labels a competent classifier would give
in the closed vocabulary (derived from the same intended structured requests used by ``audit/llm_path_dryrun.py``), and it can
inject controlled failures to prove the failure accounting works. Token usage and the echoed model id are fixed MOCK values.
"""
from __future__ import annotations

import json as _json
from contextlib import contextmanager
from datetime import date
from typing import Any, Iterator

import httpx

MOCK_MODEL_REQUESTED = "mock-openai"
MOCK_MODEL_ECHOED = "mock-openai-2026-01-01"
MOCK_USAGE = {"interpreter": (1100, 120), "explainer": (300, 40)}  # (input_tokens, output_tokens) - fixed MOCK values
MOCK_PRICING = {MOCK_MODEL_ECHOED: {"input_per_million_usd": 1.0, "output_per_million_usd": 0.0}}  # MOCK prices, mock runs only
MOCK_BASE_URL = "http://mock-provider.invalid"

Q1 = {"kind": "absolute", "start": "2025-01-01", "end": "2025-03-31"}
ALL = {"kind": "all_time"}


def month(m: int) -> dict:
    return {"kind": "calendar", "unit": "month", "year": 2025, "month": m}


def agg(metric, period, **kw):
    return {"route": "analytics_query", "query": {"operation": "aggregate", "metric": metric, "period": period, **kw}}


def rank(metric, group_by, period, limit, direction="desc", **kw):
    return {"route": "analytics_query", "query": {"operation": "ranking", "metric": metric, "group_by": group_by, "period": period,
                                                  "limit": limit, "direction": direction, **kw}}


def compare(period, against, metric="revenue"):
    return {"route": "analytics_query", "query": {"operation": "compare_periods", "metric": metric, "period": period, "comparison_period": against}}


GST = {"route": "unsupported", "unsupported_reason": "missing_field", "unsupported_item": "GST rate information"}

# The structured request a competent classifier + extractor yields for each frozen task (test scaffolding only; never used by production
# code). The mock derives its TYPED DECISIONS from this; periods, products and limits are produced by production code from the question text.
INTERPRETATIONS: dict[str, dict] = {
    "A01": agg("revenue", month(1)),
    "A02": agg("revenue", month(2)),
    "A03": agg("revenue", Q1),
    "A04": agg("units", month(3)),
    "A05": agg("units", month(2)),
    "B01": compare(month(2), month(1)),
    "B02": compare(month(3), month(2)),
    "B03": rank("revenue", "day", Q1, 1),
    "B04": rank("revenue", "day", Q1, 1, "asc"),
    "B05": compare({"kind": "absolute", "start": "2025-03-01", "end": "2025-03-15"}, {"kind": "absolute", "start": "2025-02-01", "end": "2025-02-15"}),
    "C01": rank("units", "product", month(2), 1),
    "C02": rank("revenue", "product", Q1, 3),
    "C03": rank("units", "product", month(3), 3),
    "C04": agg("units", Q1, products=["BIG ONION"]),
    "C05": rank("units", "product", Q1, 2, products=["BIG ONION", "MILK"]),
    "C06": {"route": "analytics_query", "query": {"operation": "share_of_total", "metric": "revenue", "period": Q1, "products": ["EGG"]}},
    "D01": rank("revenue", "weekday", ALL, 1),
    "D02": rank("revenue", "weekday", ALL, 1, "asc"),
    "D03": agg("revenue", Q1, weekdays=[6]),
    "D04": agg("revenue", Q1, statistic="mean_per_active_day"),
    "F01": agg("distinct_products", month(1)),
    "F02": agg("units", month(3), statistic="mean_per_active_day"),
    "F03": rank("revenue", "day", Q1, 1),
    "E01": GST, "E02": GST, "E03": GST, "E04": GST,
}

# Controlled failure injection used by the mock readiness run: {task_id: {(role, ordinal): kind}}; ordinal counts HTTP requests made for that
# task+role starting at 1 (there are no retries, so the ordinal equals the repeat number).
# kinds: http_529 | http_429 | timeout | malformed | route_other_tool | invalid_option | low_confidence
DEFAULT_INJECTIONS: dict[str, dict[tuple[str, int], str]] = {
    "B01": {("interpreter", 2): "http_529"},  # repeat 2: overloaded -> no retry -> legacy fallback
    "C03": {("interpreter", 2): "timeout"},  # repeat 2: timeout -> fallback
    "A04": {("interpreter", 3): "malformed"},  # repeat 3: not JSON -> fallback (invalid output)
    "A05": {("interpreter", 5): "invalid_option"},  # repeat 5: a choice that was not offered -> rejected -> fallback (invalid output)
    "F01": {("interpreter", 4): "route_other_tool"},  # repeat 4: the classifier hands the question to the legacy router
    "D03": {("interpreter", 1): "http_429"},  # repeat 1: rate limited -> fallback
    "A02": {("interpreter", 1): "low_confidence"},  # repeat 1: a decision below the confidence floor is never acted on -> fallback
}


def _typed_answers(interp: dict, questions: dict, kind: str | None) -> dict:
    """The typed answers the mock returns for one intended structured request (None -> a competent classification)."""
    if kind == "route_other_tool":
        interp = {"route": "legacy"}
    q = interp.get("query") or {}
    if interp.get("route") == "unsupported":
        picks = {"route": "missing_data", "missing_item": "gst_or_tax"}
    elif interp.get("route") == "legacy":
        picks = {"route": "other_tool"}
    else:
        picks = {
            "route": "calculate", "operation": q.get("operation", "aggregate"), "metric": q.get("metric", "revenue"),
            "statistic": q.get("statistic", "total"), "group_by": q.get("group_by", "none"), "direction": q.get("direction", "desc"),
        }
    conf = 0.3 if kind == "low_confidence" else 0.9
    answers: dict[str, Any] = {}
    for key, spec in questions.items():
        if spec["type"] == "noul":
            if key == "named_products":
                answers[key] = {"type": "noul", "noul": 0.95 if q.get("products") else 0.05}
            else:  # include_empty_days
                answers[key] = {"type": "noul", "noul": 0.05}
            continue
        options = list(spec["criteria"])
        choice = picks.get(key) if picks.get(key) in options else options[0]
        if kind == "invalid_option" and key == "route":
            choice = "run_sql"
        probs = {o: (conf if o == choice else (1 - conf) / max(1, len(options) - 1)) for o in options}
        if kind == "invalid_option" and key == "route":
            probs = {o: 1 / len(options) for o in options}
        answers[key] = {"type": "choice", "choice": choice, "probabilities": probs, "confidence": conf if key == "route" else 0.9}
    return answers


def _openai_object(wire_answers: dict) -> dict:
    """Typed answers in the neutral wire shape -> the JSON object the strict schema asks the model for."""
    out = {}
    for key, a in wire_answers.items():
        if a["type"] == "choice":
            out[key] = {"choice": a["choice"], "confidence": a.get("confidence", 0.9)}
        else:
            out[key] = {"probability": a["noul"]}
    return out


def _response(text: str, usage: tuple[int, int], model: str = MOCK_MODEL_ECHOED) -> dict:
    return {"id": "resp_mock", "model": model, "status": "completed",
            "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}],
            "usage": {"input_tokens": usage[0], "output_tokens": usage[1]}}


class MockProvider:
    def __init__(self, question_to_task: dict[str, str], injections: dict | None = None):
        self.q2t = question_to_task
        self.injections = DEFAULT_INJECTIONS if injections is None else injections
        self.requests: list[dict[str, Any]] = []  # in-memory only: lets tests prove what the model was and was not shown
        self._ordinal: dict[tuple[str, str], int] = {}
        self.injected_events: list[dict] = []

    # ---- the fake of OpenAIClient._request
    def request(self, client, payload):
        import openai

        from research.llm_evaluation.llm_instrument import call_role

        client.last_attempts += 1
        role = call_role(payload)
        inp = payload.get("input") if isinstance(payload.get("input"), str) else ""
        if role == "interpreter" and inp.startswith("<text>\n"):
            question = inp[len("<text>\n"):-len("\n</text>")]
        elif role == "explainer" and inp.startswith("Question: "):
            question = inp.split("\n", 1)[0][len("Question: "):]
        else:
            question = None
        task = self.q2t.get(question or "")
        key = (task or "?", role)
        self._ordinal[key] = self._ordinal.get(key, 0) + 1
        ordinal = self._ordinal[key]
        self.requests.append({"role": role, "task": task, "ordinal": ordinal, "body": payload})
        kind = (self.injections.get(task or "", {}) or {}).get((role, ordinal))
        req = httpx.Request("POST", "https://api.openai.com/v1/responses")
        if kind:
            self.injected_events.append({"task_id": task, "role": role, "ordinal": ordinal, "kind": kind})
        if kind == "http_529":
            raise openai.InternalServerError("overloaded", response=httpx.Response(529, request=req), body=None)
        if kind == "http_429":
            raise openai.RateLimitError("rate limit", response=httpx.Response(429, request=req), body=None)
        if kind == "timeout":
            raise openai.APITimeoutError(request=req)
        if kind == "malformed":
            return _response("this is not json", MOCK_USAGE.get(role, (0, 0)))
        if role == "explainer":
            return _response("This restates the verified figure above without adding any new figure.", MOCK_USAGE["explainer"])
        interp = INTERPRETATIONS.get(task or "", {"route": "legacy"})
        qs = {}
        from app.services.analytics_interpreter_service import QUESTIONS

        for k, q in QUESTIONS.items():
            qs[k] = q.payload()
        text = _json.dumps(_openai_object(_typed_answers(interp, qs, kind)))
        return _response(text, MOCK_USAGE["interpreter"])


@contextmanager
def mock_provider_active(question_to_task: dict[str, str], injections: dict | None = None) -> Iterator[MockProvider]:
    """Within the block: settings carry a clearly fake key and ``OpenAIClient._request`` is the mock. Everything is restored on exit."""
    from app.core.config import get_settings
    from app.services.openai_client import OpenAIClient

    s = get_settings()
    saved = {k: getattr(s, k) for k in ("openai_api_key", "openai_model", "openai_max_retries")}
    prov = MockProvider(question_to_task, injections)
    orig = OpenAIClient._request
    try:
        s.openai_api_key, s.openai_model, s.openai_max_retries = "MOCK-NOT-A-REAL-KEY", MOCK_MODEL_REQUESTED, 0
        OpenAIClient._request = lambda client, payload: prov.request(client, payload)  # type: ignore[assignment]
        yield prov
    finally:
        OpenAIClient._request = orig  # type: ignore[assignment]
        for k, v in saved.items():
            setattr(s, k, v)


def reference_date() -> date:
    return date(2025, 3, 31)
