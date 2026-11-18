"""Measurement-only instrumentation of the production OpenAI client.

Wraps ``OpenAIClient._request`` (the single SDK call) so every provider call made anywhere (the DecisionGPT interpreter request, the
validated explanation, or the goal classifier) records: role, provider, requested model, model echoed by the provider, latency, token
usage exactly as the provider returned it, the number of requests the call needed (1 unless a bounded retry of a transient error
occurred), and errors. It never alters a request or response. Nothing is estimated: a field the provider did not return stays None.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

API_HOST = "api.openai.com"


def call_role(payload: dict) -> str:
    """Which pre-registered request this call is: 'interpreter' (fixed classification schema) | 'explainer' | 'other'."""
    from app.services.analytics_interpreter_service import QUESTIONS
    from app.services.openai_client import SYSTEM_DECIDE, SYSTEM_EXPLAIN, build_schema

    if payload.get("instructions") == SYSTEM_EXPLAIN:
        return "explainer"
    try:
        schema = payload["text"]["format"]["schema"]
    except (KeyError, TypeError):
        return "other"
    if payload.get("instructions") == SYSTEM_DECIDE and schema == build_schema(QUESTIONS):
        return "interpreter"
    return "other"


@dataclass
class LLMRecorder:
    calls: list[dict] = field(default_factory=list)
    _orig: object = None
    # Optional fail-closed guard: payload_guard(role, payload) -> list of violations. If it returns any, the request is NOT sent
    # (an exception is raised before the provider is contacted) and the violations are recorded on the call entry.
    payload_guard: object = None
    # Hard cap on provider requests for this recorder (None = unlimited). A request that would exceed it is NOT sent.
    max_calls: int | None = None

    def install(self) -> "LLMRecorder":
        from app.services.openai_client import OpenAIClient

        if getattr(OpenAIClient, "_eval_wrapped", False):
            return self
        self._orig = OpenAIClient._request
        rec = self
        orig = self._orig

        def wrapped(client, payload):
            t0 = time.perf_counter()
            entry = {"role": call_role(payload), "provider": client.provider, "url_host": API_HOST, "model_requested": payload.get("model"),
                     "max_tokens": payload.get("max_output_tokens"), "temperature": None, "ts": time.time()}
            if rec.max_calls is not None and len(rec.calls) >= rec.max_calls:
                entry.update(ok=False, error="request cap reached: request not sent", latency_s=0.0, attempts=0, cap_reached=True)
                rec.calls.append(entry)
                raise RuntimeError("request cap reached: request not sent")
            if rec.payload_guard is not None:
                violations = rec.payload_guard(entry["role"], payload)
                if violations:
                    entry.update(ok=False, error="ground-truth isolation violation: request not sent", latency_s=0.0, attempts=0, leak_violations=violations)
                    rec.calls.append(entry)
                    raise RuntimeError("ground-truth isolation violation: request not sent")

            def attempts_made():
                n = getattr(client, "last_attempts", None)
                return int(n) if isinstance(n, int) and n > 0 else None

            try:
                data = orig(client, payload)
            except Exception as exc:  # recorded (class name only: the message may echo credentials), then re-raised unchanged
                entry.update(ok=False, error=type(exc).__name__, latency_s=time.perf_counter() - t0, attempts=attempts_made())
                rec.calls.append(entry)
                raise
            usage = data.get("usage") or {}
            entry.update(
                ok=True,
                latency_s=time.perf_counter() - t0,
                model_returned=data.get("model"),
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                usage_raw=usage or None,
                attempts=attempts_made(),
            )
            rec.calls.append(entry)
            return data

        OpenAIClient._request = wrapped
        OpenAIClient._eval_wrapped = True
        return self

    def uninstall(self) -> None:
        from app.services.openai_client import OpenAIClient

        if getattr(OpenAIClient, "_eval_wrapped", False) and self._orig is not None:
            OpenAIClient._request = self._orig
            OpenAIClient._eval_wrapped = False

    def mark(self) -> int:
        return len(self.calls)

    def since(self, mark: int) -> list[dict]:
        return self.calls[mark:]


def summarize_calls(calls: list[dict]) -> dict:
    """Aggregate per-attempt LLM usage; a total is reported only if EVERY call returned that field."""
    n = len(calls)
    ok = [c for c in calls if c.get("ok")]

    def total(key):
        vals = [c.get(key) for c in calls]
        return sum(vals) if n and all(isinstance(v, (int, float)) for v in vals) else None

    return {"n_calls": n, "n_errors": n - len(ok), "input_tokens": total("input_tokens"), "output_tokens": total("output_tokens"),
            "llm_latency_s": sum(c.get("latency_s", 0.0) for c in calls) if n else 0.0}


def compact_calls(calls: list[dict]) -> list[dict]:
    """The per-call fields that go into every result row (no request/response bodies)."""
    keys = ("role", "ok", "latency_s", "input_tokens", "output_tokens", "attempts", "model_requested", "model_returned", "error", "leak_violations")
    return [{k: c.get(k) for k in keys} for c in calls]


def cost_usd(calls: list[dict], pricing: dict | None) -> float | None:
    """Cost of the calls that RETURNED a response, only when the provider returned token counts for each of them AND a verified price for
    that exact model is supplied. Calls that failed returned no usage, so their cost is unknown: they are excluded (the total is then a
    lower bound, reported as such by the metrics) and never estimated."""
    calls = [c for c in calls if c.get("ok")]
    if not calls or not pricing:
        return None
    total = 0.0
    for c in calls:
        name = c.get("model_returned") or c.get("model_requested") or ""
        price = pricing.get(name)
        if not price:  # a dated snapshot such as "gpt-4.1-mini-2025-04-14" is priced as its family; the longest matching key wins
            fam = [k for k in pricing if name.startswith(k + "-")]
            price = pricing[max(fam, key=len)] if fam else None
        if not price or not isinstance(c.get("input_tokens"), (int, float)) or not isinstance(c.get("output_tokens"), (int, float)):
            return None
        total += c["input_tokens"] / 1e6 * price["input_per_million_usd"] + c["output_tokens"] / 1e6 * price["output_per_million_usd"]
    return total
