"""Phase 5 — LLM wiring. No network: the provider client is monkeypatched.
Verifies (a) template mode when no key, (b) the abstraction actually calls
the provider when a key is set, (c) provider failures degrade gracefully.
"""
import pytest

from app.services import llm_service
from app.services.llm_service import LLMService, extract_constraints


def test_no_api_key_uses_deterministic_templates(monkeypatch):
    monkeypatch.setattr(LLMService, "enabled", property(lambda self: False))
    svc = LLMService()
    parsed = svc.parse_goal("Increase profit by 15% in 3 months")
    assert parsed.objective == "increase_profit"
    assert parsed.target_value == 15
    text = svc.generate_strategy_explanation({"strategy_name": "Price +5%", "risk_level": "low"})
    assert "Price +5%" in text


def test_constraint_extraction_rules():
    assert "no_price_increase" in extract_constraints("grow revenue without raising prices")
    assert "no_marketing_increase" in extract_constraints("keep the marketing budget the same")
    assert extract_constraints("increase sales") == []


def test_llm_enabled_requires_both_provider_and_key(monkeypatch):
    """The 'real-LLM validation BLOCKED' state is exactly `not llm_enabled`.
    Both LLM_PROVIDER and LLM_API_KEY must be set; either alone is still
    template mode (docs/REAL_LLM_VALIDATION_PROTOCOL.md)."""
    from app.core.config import Settings

    assert Settings(llm_provider=None, llm_api_key=None).llm_enabled is False
    assert Settings(llm_provider="anthropic", llm_api_key=None).llm_enabled is False
    assert Settings(llm_provider=None, llm_api_key="sk-x").llm_enabled is False
    assert Settings(llm_provider="", llm_api_key="").llm_enabled is False
    assert Settings(llm_provider="anthropic", llm_api_key="sk-x").llm_enabled is True


def test_agents_never_call_an_llm_scores_are_llm_independent():
    """The BA / FA / RM SCORES that drive strategy selection are rule-based and
    do not change with a real LLM (app/agents/base.py: 'No agent calls an
    LLM'). A real-LLM run affects goal parsing + narration only."""
    import importlib
    import inspect

    for mod_name in ("app.agents.base", "app.agents.business_analyst",
                     "app.agents.financial_advisor", "app.agents.risk_manager",
                     "app.agents.single_agent", "app.agents.strategy_optimizer"):
        mod = importlib.import_module(mod_name)
        # no agent module imports the LLM layer or a vendor client
        for name in vars(mod):
            assert "llm" not in name.lower(), f"{mod_name}.{name}"
        code = "\n".join(
            ln for ln in inspect.getsource(mod).splitlines()
            if not ln.lstrip().startswith(("#", '"', "'"))
        ).lower()
        assert "llm_service" not in code and "llmclient" not in code and ".complete(" not in code, mod_name


class _FakeClient:
    def __init__(self):
        self.calls = []

    def complete(self, system, user, **kw):
        self.calls.append(("complete", user))
        return "LLM-NARRATED"

    def complete_json(self, system, user, **kw):
        self.calls.append(("json", user))
        return {
            "objective": "increase_revenue",
            "target_value": 20,
            "target_unit": "percent",
            "time_horizon_months": 3,
            "constraints": ["no_price_increase"],
        }


def test_llm_enabled_path_calls_provider(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(LLMService, "enabled", property(lambda self: True))
    monkeypatch.setattr(LLMService, "_client", lambda self: fake)

    svc = LLMService()
    parsed = svc.parse_goal("bump revenue a lot")
    assert parsed.objective == "increase_revenue"
    assert parsed.target_value == 20
    assert parsed.constraints == ["no_price_increase"]

    narrated = svc.evaluate_agent("risk_manager", {"key_points": ["x"], "risks": []})
    assert narrated == "LLM-NARRATED"
    assert any(kind == "json" for kind, _ in fake.calls)


def test_llm_failure_falls_back_to_template(monkeypatch):
    class _Boom:
        def complete(self, *a, **k):
            raise RuntimeError("network down")

        def complete_json(self, *a, **k):
            raise RuntimeError("network down")

    monkeypatch.setattr(LLMService, "enabled", property(lambda self: True))
    monkeypatch.setattr(LLMService, "_client", lambda self: _Boom())
    svc = LLMService()

    # Goal parsing still works via the rule-based fallback.
    parsed = svc.parse_goal("Increase profit by 15% in 3 months")
    assert parsed.objective == "increase_profit"
    # Narration falls back to the template.
    text = svc.generate_strategy_explanation({"strategy_name": "Marketing +10%"})
    assert "Marketing +10%" in text
