"""Provider wiring for the Jev integration. No network: the Jev client is replaced by a recording fake.
Verifies (a) rule-based mode when no key is set, (b) the abstraction really asks Jev when a key is set and uses a confident answer,
(c) provider failures degrade to the rule-based result and say so, (d) nothing that used to be free text calls a provider.
"""
from app.core.config import Settings
from app.services.openai_client import Answer, DecisionResult
from app.services.llm_service import LLMService, extract_constraints


def test_no_api_key_uses_deterministic_rules_and_templates(monkeypatch):
    monkeypatch.setattr(LLMService, "enabled", property(lambda self: False))
    svc = LLMService()
    parsed = svc.parse_goal("Increase profit by 15% in 3 months")
    assert parsed.objective == "increase_profit" and parsed.target_value == 15 and parsed.decision_source == "rules"
    text = svc.generate_strategy_explanation({"strategy_name": "Price +5%", "risk_level": "low"})
    assert "Price +5%" in text


def test_constraint_extraction_rules():
    assert "no_price_increase" in extract_constraints("grow revenue without raising prices")
    assert "no_marketing_increase" in extract_constraints("keep the marketing budget the same")
    assert extract_constraints("increase sales") == []


def test_ai_is_enabled_only_by_the_jev_key():
    # _env_file=None: hermetic - a developer's real backend/.env must not change what this asserts
    assert Settings(_env_file=None, openai_api_key=None).llm_enabled is False
    assert Settings(_env_file=None, openai_api_key="").llm_enabled is False
    assert Settings(_env_file=None, openai_api_key="tsk-x").llm_enabled is True
    # the old provider settings are gone and cannot enable anything
    assert Settings(_env_file=None, llm_provider="openai", llm_api_key="sk-x").llm_enabled is False  # type: ignore[call-arg]


def test_agents_never_call_an_llm_scores_are_llm_independent():
    """The BA / FA / RM SCORES that drive strategy selection are rule-based and never touch the AI layer."""
    import importlib
    import inspect

    for mod_name in ("app.agents.base", "app.agents.business_analyst",
                     "app.agents.financial_advisor", "app.agents.risk_manager",
                     "app.agents.single_agent", "app.agents.strategy_optimizer"):
        mod = importlib.import_module(mod_name)
        for name in vars(mod):
            assert "llm" not in name.lower() and "openai" not in name.lower(), f"{mod_name}.{name}"
        code = "\n".join(
            ln for ln in inspect.getsource(mod).splitlines()
            if not ln.lstrip().startswith(("#", '"', "'"))
        ).lower()
        assert "llm_service" not in code and "openai_client" not in code and "typesafe" not in code, mod_name


def _goal_decision(objective="increase_revenue", conf=0.9, constraint_noul=None):
    answers = {"objective": Answer("choice", objective, {objective: conf}, conf)}
    for k in ("no_price_increase", "no_price_decrease", "no_price_change", "no_marketing_increase", "no_marketing_decrease"):
        answers[f"c_{k}"] = Answer("noul", (constraint_noul or {}).get(k, 0.02))
    return DecisionResult(True, answers, None, 0.001, "openai", "gpt-4.1-mini", "gpt-4.1-mini-2025-04-14", {"input_tokens": 200, "output_tokens": 0}, 1)


class _FakeLLMClient:
    def __init__(self, result):
        self.result, self.calls = result, []

    def decide(self, state, questions):
        self.calls.append((state, questions))
        return self.result


def test_goal_objective_and_constraints_come_from_typed_decisions_numbers_stay_rule_based(monkeypatch):
    fake = _FakeLLMClient(_goal_decision("increase_revenue", 0.9, {"no_price_increase": 0.95}))
    monkeypatch.setattr(LLMService, "enabled", property(lambda self: True))
    monkeypatch.setattr(LLMService, "_client", lambda self: fake)
    parsed = LLMService().parse_goal("grow turnover by 20% in 3 months")
    assert parsed.objective == "increase_revenue" and parsed.primary_kpi == "revenue" and parsed.decision_source == "ai"
    assert parsed.target_value == 20 and parsed.time_horizon_months == 3  # from rules: Jev cannot extract numbers
    assert parsed.constraints == ["no_price_increase"]
    assert len(fake.calls) == 1 and fake.calls[0][0] == "grow turnover by 20% in 3 months"  # one request, only the goal text


def test_low_confidence_or_none_keeps_the_rule_based_objective(monkeypatch):
    monkeypatch.setattr(LLMService, "enabled", property(lambda self: True))
    for res in (_goal_decision("increase_revenue", 0.3), _goal_decision("none", 0.95)):
        monkeypatch.setattr(LLMService, "_client", lambda self, r=res: _FakeLLMClient(r))
        parsed = LLMService().parse_goal("Increase profit by 15% in 3 months")
        assert parsed.objective == "increase_profit" and parsed.decision_source == "rules"


def test_provider_failure_falls_back_to_rules_and_says_so(monkeypatch):
    monkeypatch.setattr(LLMService, "enabled", property(lambda self: True))
    monkeypatch.setattr(LLMService, "_client", lambda self: _FakeLLMClient(DecisionResult(False, {}, "timeout")))
    parsed = LLMService().parse_goal("Increase profit by 15% in 3 months")
    assert parsed.objective == "increase_profit" and parsed.decision_source == "rules"
    assert any("timeout" in w for w in parsed.parse_warnings)
    # narration is a template whether or not a provider is configured
    assert "Marketing +10%" in LLMService().generate_strategy_explanation({"strategy_name": "Marketing +10%"})


def test_free_text_features_never_reach_a_provider(monkeypatch):
    """Jev cannot write text, so narration/explanation/rephrasing are templates: asking for them must not build a client."""
    monkeypatch.setattr(LLMService, "enabled", property(lambda self: True))

    def boom(self):
        raise AssertionError("no provider call is allowed for free-text generation")

    monkeypatch.setattr(LLMService, "_client", boom)
    svc = LLMService()
    assert "Risk" in svc.evaluate_agent("risk_manager", {"key_points": ["x"], "risks": ["y"]})
    assert svc.generate_strategy_explanation({"strategy_name": "S"}).startswith("Strategy: S")
    assert isinstance(svc.generate_business_response({"type": "unknown"}), str)
