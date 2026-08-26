"""The one place an actual LLM vendor HTTP API is called.

Kept behind ``LLMService`` (app/services/llm_service.py) — no other module
imports this. Provider + key + model + base URL all come from environment
variables (see app/core/config.py); nothing is hard-coded, and when
``llm_api_key`` is unset ``LLMService`` never constructs this client at all.

Supports OpenAI-style ``/chat/completions`` (``openai`` /
``openai_compatible``) and Anthropic ``/v1/messages`` (``anthropic``).
"""
import json

import httpx

from app.core.config import get_settings

try:  # tenacity is listed in requirements but keep this import soft
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )

    _HAS_TENACITY = True
except ImportError:  # pragma: no cover - depends on env
    _HAS_TENACITY = False

    def retry(*_a, **_k):  # type: ignore[no-redef]
        def deco(fn):
            return fn

        return deco

    def retry_if_exception_type(*_a, **_k):  # type: ignore[no-redef]
        return None

    def stop_after_attempt(*_a, **_k):  # type: ignore[no-redef]
        return None

    def wait_exponential(*_a, **_k):  # type: ignore[no-redef]
        return None

_DEFAULT_BASE = {
    "openai": "https://api.openai.com/v1",
    "openai_compatible": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
}


class LLMProviderError(RuntimeError):
    pass


class LLMClient:
    def __init__(self) -> None:
        s = get_settings()
        self.provider = (s.llm_provider or "openai").lower()
        self.api_key = s.llm_api_key
        self.model = s.llm_model or ("claude-sonnet-4-20250514" if self.provider == "anthropic" else "gpt-4o-mini")
        self.base_url = (s.llm_base_url or _DEFAULT_BASE.get(self.provider, _DEFAULT_BASE["openai"])).rstrip("/")
        self.timeout = s.llm_timeout_seconds
        if not self.api_key:
            raise LLMProviderError("LLM_API_KEY is not configured.")

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    )
    def _post(self, url: str, headers: dict, payload: dict) -> dict:
        resp = httpx.post(url, headers=headers, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def complete(self, system: str, user: str, *, json_mode: bool = False, max_tokens: int = 600) -> str:
        if self.provider == "anthropic":
            payload = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": 0,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            data = self._post(f"{self.base_url}/v1/messages", headers, payload)
            parts = data.get("content", [])
            return "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()

        # OpenAI-compatible
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}", "content-type": "application/json"}
        data = self._post(f"{self.base_url}/chat/completions", headers, payload)
        return data["choices"][0]["message"]["content"].strip()

    def complete_json(self, system: str, user: str, *, max_tokens: int = 600) -> dict:
        raw = self.complete(system, user, json_mode=True, max_tokens=max_tokens)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Some providers wrap JSON in prose/fences — salvage the object.
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end != -1:
                return json.loads(raw[start : end + 1])
            raise
