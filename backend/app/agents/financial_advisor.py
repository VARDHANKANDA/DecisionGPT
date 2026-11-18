"""Financial Advisor agent — docs/MULTI_AGENT_SPECIFICATION.md §2: revenue,
cost, margin, profit, ROI.

Documented scoring method: `score = clamp(0.5 + signal, 0, 1)`, where
`signal` is the relative change in expected profit vs baseline. Profit
requires product unit_cost data (docs/PRD.md §22); when it's unavailable,
this agent falls back to revenue as the next-best financial signal and
says so explicitly — it never estimates a profit figure that wasn't
actually computed (see AGENTS.md "no fabrication").

Round 2 (`review`): the advisor re-checks financial assumptions against
peers — e.g. when its own score is revenue-based (no cost data) and the
Business Analyst is also optimistic, it flags that the upside is unverified
on margin.
"""
from app.agents.base import AgentEvaluationResult, PeerReview, clamp01
from app.analytics.digital_twin_service import SimulationOutput
from app.models.goal import Goal


def evaluate(output: SimulationOutput, goal: Goal, causal_context=None) -> AgentEvaluationResult:
    key_points = []
    assumptions = [f"Based on the Digital Twin simulation using {output.model_name} {output.model_version}."]
    basis = "revenue"

    # Goal tracking
    target_val = getattr(goal, "target_value", None)
    target_str = f" (goal target: {target_val:+.1f}%)" if target_val is not None else ""

    if output.expected_profit is not None and output.baseline_profit is not None and abs(output.baseline_profit) > 1e-9:
        signal = (output.expected_profit - output.baseline_profit) / abs(output.baseline_profit)
        basis = "profit"
        key_points.append(
            f"Projected profit: {signal * 100:+.1f}% "
            f"(observed baseline ₹{output.baseline_profit:,.0f} -> simulated projection ₹{output.expected_profit:,.0f}{target_str})."
        )
    else:
        baseline_revenue = output.baseline_revenue
        signal = (output.expected_revenue - baseline_revenue) / baseline_revenue if baseline_revenue > 1e-9 else 0.0
        basis = "revenue"
        key_points.append(
            f"Projected revenue: {signal * 100:+.1f}% "
            f"(observed baseline ₹{output.baseline_revenue:,.0f} -> simulated projection ₹{output.expected_revenue:,.0f}{target_str})."
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
    if basis == "profit" and output.expected_profit is not None and output.expected_profit < 0:
        risks.append("Projected net profit is negative — strategy fails basic financial viability.")

    result = AgentEvaluationResult("financial_advisor", round(score, 4), key_points, risks, assumptions)
    result.meta["basis"] = basis  # consumed by review(); not persisted
    return result


def _basis_of(result: AgentEvaluationResult) -> str:
    return result.meta.get("basis", "revenue")


def review(own: AgentEvaluationResult, peers: dict[str, AgentEvaluationResult], output: SimulationOutput) -> PeerReview:
    ba = peers.get("business_analyst")
    rm = peers.get("risk_manager")
    challenges: list[str] = []
    adjusted: float | None = None
    basis = _basis_of(own)

    # 1. Unverified margin check: if revenue only (no cost data) and both agents optimistic, apply single bounded adjustment.
    if basis == "revenue" and own.score >= 0.6 and ba is not None and ba.score >= 0.6:
        challenges.append(
            "Both the Business Analyst and this agent are optimistic, but with no unit_cost data the "
            "upside is unverified on margin — a revenue gain from discounting could still be profit-negative."
        )
        adjusted = round(clamp01(own.score - 0.05), 4)

    # 2. Operational fulfillment check: if inventory constrained and not already adjusted, record fulfillment risk.
    if output.inventory_constrained and own.score >= 0.55:
        challenges.append(
            "Revenue projection assumes demand is fulfilled, but the simulation capped sales at available "
            "inventory — realised revenue may be lower."
        )
        if adjusted is None:
            adjusted = round(clamp01(own.score - 0.05), 4)

    # 3. Bidirectional reconciliation: if verified profit basis, non-declining BA demand, and RM safety, confirm financial strength.
    if adjusted is None and basis == "profit" and ba is not None and rm is not None:
        if ba.score >= 0.50 and rm.score >= 0.65 and own.score >= 0.55:
            # Positive operational and risk confirmation reinforces verified profit margin
            adjusted = round(clamp01(own.score + 0.03), 4)


    return PeerReview(
        agent="financial_advisor",
        concurs=adjusted is None or adjusted >= own.score,
        challenges=challenges,
        adjusted_score=adjusted,
        rationale=(
            "Re-checked financial assumptions against peer optimism and fulfilment constraints."
            if challenges
            else "Financial assumptions consistent with peer assessments."
        ),
    )

