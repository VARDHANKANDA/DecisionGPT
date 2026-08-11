"""Financial Advisor agent — docs/MULTI_AGENT_SPECIFICATION.md §2: revenue,
cost, margin, profit, ROI.

Documented scoring method: `score = clamp(0.5 + signal, 0, 1)`, where
`signal` is the relative change in expected profit vs baseline. Profit
requires product unit_cost data (docs/PRD.md §22); when it's unavailable,
this agent falls back to revenue as the next-best financial signal and
says so explicitly — it never estimates a profit figure that wasn't
actually computed (see AGENTS.md "no fabrication").
"""
from app.agents.base import AgentEvaluationResult, clamp01
from app.analytics.digital_twin_service import SimulationOutput
from app.models.goal import Goal


def evaluate(output: SimulationOutput, goal: Goal) -> AgentEvaluationResult:
    key_points = []
    assumptions = [f"Based on the Digital Twin simulation using {output.model_name} v{output.model_version}."]

    if output.expected_profit is not None and output.baseline_profit is not None and abs(output.baseline_profit) > 1e-9:
        signal = (output.expected_profit - output.baseline_profit) / abs(output.baseline_profit)
        basis = "profit"
        key_points.append(
            f"Projected profit: {signal * 100:+.1f}% (₹{output.baseline_profit:,.0f} -> ₹{output.expected_profit:,.0f})."
        )
    else:
        baseline_revenue = output.baseline_revenue
        signal = (output.expected_revenue - baseline_revenue) / baseline_revenue if baseline_revenue > 1e-9 else 0.0
        basis = "revenue"
        key_points.append(
            f"Projected revenue: {signal * 100:+.1f}% (₹{output.baseline_revenue:,.0f} -> ₹{output.expected_revenue:,.0f})."
        )
        assumptions.append(
            "Profit wasn't available (no product unit_cost on file), so this score is based on revenue instead."
        )

    score = clamp01(0.5 + signal)

    risks = []
    if basis == "revenue":
        risks.append("Cannot evaluate margin impact without product cost data — this may overstate the benefit.")
    if signal < -0.05:
        risks.append(f"This strategy is projected to reduce {basis}.")

    return AgentEvaluationResult("financial_advisor", round(score, 4), key_points, risks, assumptions)
