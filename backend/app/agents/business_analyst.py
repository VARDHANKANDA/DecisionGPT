"""Business Analyst agent — docs/MULTI_AGENT_SPECIFICATION.md §2: sales,
demand, growth.

Documented scoring method: `score = clamp(0.5 + growth, 0, 1)` where
`growth` is the Digital Twin's own relative change in expected units sold
vs baseline for this strategy. 0% growth -> neutral 0.5; +/-50% or more
growth/decline saturates the score at 1.0/0.0. This is the one fixed
formula this agent uses (docs/MULTI_AGENT_SPECIFICATION.md §7 "fix the
scoring formula").
"""
from app.agents.base import AgentEvaluationResult, clamp01
from app.analytics.digital_twin_service import SimulationOutput
from app.models.goal import Goal


def evaluate(output: SimulationOutput, goal: Goal) -> AgentEvaluationResult:
    baseline = output.baseline_units_sold
    growth = (output.expected_units_sold - baseline) / baseline if baseline > 1e-9 else 0.0
    score = clamp01(0.5 + growth)

    key_points = [
        f"Projected units sold: {growth * 100:+.1f}% "
        f"({output.baseline_units_sold:.1f} -> {output.expected_units_sold:.1f} over the simulated horizon)."
    ]

    risks = []
    if output.inventory_constrained:
        risks.append("Projected demand exceeds available inventory — some of this growth may not be fulfillable.")
    if growth < -0.05:
        risks.append("This strategy is projected to reduce sales volume.")

    assumptions = [f"Based on the Digital Twin simulation using {output.model_name} v{output.model_version}."]

    return AgentEvaluationResult("business_analyst", round(score, 4), key_points, risks, assumptions)
