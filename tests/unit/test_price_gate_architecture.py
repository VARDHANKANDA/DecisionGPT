"""No owner-facing surface may quote a simulated figure without the shared eligibility gate.

``digital_twin_service.simulate_strategy`` returns raw model output (a price effect the business's data cannot support, on the registered
synthetic model's scale). Every module that calls it must be either (a) listed here as research / pipeline code with its reason, or
(b) pass the result through ``api_view`` (or ``with_business_baseline`` + ``public_view``). A new caller fails this test until a person
decides which it is, so an endpoint cannot bypass the gate by being added quietly.
"""
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "backend" / "app"

# Not owner-facing, or gated by its own mechanism. Each entry says why.
ALLOWED_RAW = {
    "analytics/digital_twin_service.py": "defines it",
    "services/decision_service.py": "production decisions gate price candidates with PipelineOptions.price_response_gate before simulating",
    "services/decision_architecture_service.py": "research architectures A-D (admin research console), not an owner-facing recommendation",
    "services/ablation_service.py": "research ablations through analyze_goal",
    "services/multi_agent_diagnostic_service.py": "research diagnostic",
    "services/risk_calibration_service.py": "research diagnostic",
    "services/risk_manager_diagnostic_service.py": "research diagnostic",
    "services/risk_manager_generalization_service.py": "research diagnostic",
    "services/strategy_generation_service.py": "candidate generation inside the decision pipeline (gated there)",
}
RESEARCH_DIRS = ("evaluation/",)
# Owner-facing callers: must route through the gate.
GATED_CALLERS = {
    "api/v1/endpoints/digital_twin.py": ("api_view", "read_with_business_baseline"),
    "services/assistant_service.py": ("api_view",),
    "services/counterfactual_service.py": ("api_view",),
    "services/debate_service.py": ("api_view",),
}


def _callers() -> dict[str, str]:
    out = {}
    for p in APP.rglob("*.py"):
        rel = p.relative_to(APP).as_posix()
        src = p.read_text(encoding="utf-8")
        if re.search(r"\bsimulate_strategy\b", src):
            out[rel] = src
    return out


def test_every_caller_of_simulate_strategy_is_classified():
    unknown = [rel for rel in _callers() if rel not in ALLOWED_RAW and rel not in GATED_CALLERS and not rel.startswith(RESEARCH_DIRS)]
    assert not unknown, (
        f"{unknown} call simulate_strategy without being classified. If it shows a simulated figure to a business owner it must use "
        "digital_twin_service.api_view (price effect withheld unless supported); add it to GATED_CALLERS. If it is research or "
        "pipeline code, add it to ALLOWED_RAW with the reason."
    )


def test_owner_facing_callers_route_through_the_gate():
    callers = _callers()
    for rel, needed in GATED_CALLERS.items():
        assert rel in callers, f"{rel} no longer calls simulate_strategy; remove it from GATED_CALLERS"
        missing = [n for n in needed if n not in callers[rel]]
        assert not missing, f"{rel} calls simulate_strategy but does not use {missing}"


def test_the_gate_is_not_weakened_in_the_shared_helper():
    src = (APP / "analytics" / "digital_twin_service.py").read_text(encoding="utf-8")
    api_view = src[src.index("def api_view"): src.index("def public_view")]
    assert "with_business_baseline" in api_view and "public_view" in api_view
    check = src[src.index("def price_effect_check"): src.index("def price_response_notes")]
    assert "price_scenarios" in check and "identified" in check          # eligibility of the model is part of the decision
