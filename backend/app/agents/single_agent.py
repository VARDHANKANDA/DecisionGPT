"""Single-Agent baseline — used only by the Research Console's Decision
Architecture experiment (docs/PRD.md §13, architecture C: "Prediction +
Digital Twin + Single Agent") to give the real three-agent system
(app.agents.business_analyst/financial_advisor/risk_manager +
strategy_optimizer) something genuine to be compared against. Never used
in the SME-facing pipeline (app.services.decision_service always uses the
full three-agent system).

Documented formula: the same growth signal business_analyst uses, and the
same risk_score risk_manager uses, combined directly with no separate
specialists or optimizer debate — score = growth_score * (1 - risk_score).
"""
from app.agents.base import AgentEvaluationResult, clamp01
from app.analytics.digital_twin_service import SimulationOutput


def evaluate(output: SimulationOutput) -> AgentEvaluationResult:
    baseline = output.baseline_revenue
    growth = (output.expected_revenue - baseline) / baseline if baseline > 1e-9 else 0.0
    growth_score = clamp01(0.5 + growth)
    score = round(growth_score * (1 - output.risk_score), 4)

    return AgentEvaluationResult(
        "single_agent",
        score,
        key_points=[f"Projected revenue change: {growth * 100:+.1f}%, risk-adjusted score {score:.3f}."],
        risks=[] if output.risk_level == "LOW" else [f"{output.risk_level.title()} extrapolation risk."],
        assumptions=[f"Based on {output.model_name} {output.model_version}."],
    )
