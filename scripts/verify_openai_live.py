"""Bounded LIVE connectivity check of the OpenAI integration. SPENDS A FEW TENTHS OF A CENT - run it deliberately, by hand.

    # OPENAI_API_KEY comes from backend/.env or the environment; it is never printed and never passed on the command line
    python scripts/verify_openai_live.py

It sends exactly ONE request through the production client (``LLMService.decide``) with the production classification schema and one
representative question, then checks that the structured response passes the production validation and assembles into a valid
``Interpretation``. It prints the configured and served model, latency, token usage and an ESTIMATED cost from the published price.
It never retries, never runs the benchmark, and exits without sending anything when no key is configured.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

QUESTION = "What were my total sales in February 2025?"


def main() -> int:
    from app.core.config import get_settings
    from app.services import analytics_interpreter_service as interp
    from app.services.llm_service import LLMService

    s = get_settings()
    if not s.llm_enabled:
        print(json.dumps({"sent": False, "reason": "OPENAI_API_KEY is not set (blank or missing). Nothing was sent.", "model_configured": s.openai_model}, indent=2))
        return 3
    svc = LLMService()
    res = svc.decide(QUESTION, interp.QUESTIONS)  # one request, no retry loop around it
    out: dict = {"sent": True, "requests_made": res.attempts, "ok": res.ok, "error": res.error, "model_configured": res.model, "model_served": res.response_model,
                 "latency_s": round(res.latency_s, 3), "usage": res.usage}
    if res.ok:
        replay = type("Replay", (), {"decide": lambda self, st, q: res})()
        built = interp.interpret(replay, QUESTION, None, None, {}, [])
        out["decisions"] = built.decisions.get("ai")
        out["extracted"] = built.decisions.get("extracted")
        out["assembled_request_valid"] = built.interpretation is not None
        out["assembly_error"] = built.error
        price_path = ROOT / "research" / "llm_evaluation" / "pricing.json"
        try:
            models = json.loads(price_path.read_text(encoding="utf-8")).get("models", {})
            name = res.response_model or res.model or ""
            key = name if name in models else max((k for k in models if name.startswith(k + "-")), key=len, default=None)
            if key and res.usage:
                p = models[key]
                out["estimated_cost_usd"] = round((res.usage["input_tokens"] * p["input_per_million_usd"] + res.usage["output_tokens"] * p["output_per_million_usd"]) / 1e6, 6)
                out["price_basis"] = f"{key}: ${p['input_per_million_usd']}/M input, ${p['output_per_million_usd']}/M output (list price; not a billing record)"
        except (OSError, ValueError):
            pass
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0 if res.ok and out.get("assembled_request_valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
