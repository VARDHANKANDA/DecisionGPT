"""Risk Manager agent — docs/MULTI_AGENT_SPECIFICATION.md §2: downside,
uncertainty, operational risk, customer impact.

Documented scoring method (a 0..1 "safety" score, higher = safer):
`score = clamp(1 - risk_score - uncertainty_penalty - inventory_penalty, 0, 1)`
- `risk_score` is the Digital Twin's own extrapolation-risk score (real,
  computed — docs/DIGITAL_TWIN_SPECIFICATION.md §9).
- `uncertainty_penalty` is the width of the simulation's revenue prediction
  interval relative to the expected revenue, capped at 0.4 so one very
  uncertain input can't single-handedly zero out the score.
- `inventory_penalty` is a fixed 0.15 when the simulation had to cap sales
  at available inventory (a real operational constraint the strategy runs
  into, not a guess).
"""
from app.agents.base import AgentEvaluationResult, clamp01
from app.analytics.digital_twin_service import SimulationOutput
from app.models.goal import Goal

UNCERTAINTY_PENALTY_CAP = 0.4
INVENTORY_PENALTY = 0.15


def evaluate(output: SimulationOutput, goal: Goal) -> AgentEvaluationResult:
    band_width = output.revenue_upper_bound - output.revenue_lower_bound
    uncertainty_ratio = band_width / output.expected_revenue if output.expected_revenue > 1e-9 else 0.0
    uncertainty_penalty = min(UNCERTAINTY_PENALTY_CAP, uncertainty_ratio * 0.2)
    inventory_penalty = INVENTORY_PENALTY if output.inventory_constrained else 0.0

    score = clamp01(1.0 - output.risk_score - uncertainty_penalty - inventory_penalty)

    key_points = [f"Extrapolation risk: {output.risk_level} (risk score {output.risk_score:.2f})."]
    if output.customer_impact is not None:
        key_points.append(f"Estimated customer impact: {output.customer_impact:+d}.")

    risks = []
    if output.risk_level != "LOW":
        risks.append(
            f"This strategy pushes price/marketing inputs {output.risk_level.lower()} beyond what your "
            "historical data has shown the model."
        )
    if output.inventory_constrained:
        risks.append("Projected demand exceeds available inventory.")
    if uncertainty_ratio > 1.0:
        risks.append("The revenue prediction interval is wide relative to the expected value.")

    assumptions = [f"Based on the Digital Twin simulation using {output.model_name} v{output.model_version}."]

    return AgentEvaluationResult("risk_manager", round(score, 4), key_points, risks, assumptions)
