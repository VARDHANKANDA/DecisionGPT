"""Business Analyst agent — docs/MULTI_AGENT_SPECIFICATION.md §2: sales,
demand, growth.

Documented scoring method: `score = clamp(0.5 + growth, 0, 1)` where
`growth` is the Digital Twin's own relative change in expected units sold
vs baseline for this strategy. 0% growth -> neutral 0.5; +/-50% or more
growth/decline saturates the score at 1.0/0.0. This is the one fixed
formula this agent uses (docs/MULTI_AGENT_SPECIFICATION.md §7 "fix the
scoring formula").

Round 2 (`review`): the analyst reacts to the Financial Advisor's and Risk
Manager's round-1 assessments — it can flag a strategic-fit problem when a
strategy the finance/risk side likes actually erodes sales volume.
"""
from app.agents.base import AgentEvaluationResult, PeerReview, clamp01
from app.analytics.digital_twin_service import SimulationOutput
from app.models.goal import Goal


def evaluate(output: SimulationOutput, goal: Goal, causal_context=None) -> AgentEvaluationResult:
    baseline = output.baseline_units_sold
    growth = (output.expected_units_sold - baseline) / baseline if baseline > 1e-9 else 0.0
    score = clamp01(0.5 + growth)

    # Goal awareness: identify stated primary target
    kpi_name = getattr(goal, "primary_kpi", "units") or "units"
    target_val = getattr(goal, "target_value", None)
    target_str = f" (goal target: {target_val:+.1f}%)" if target_val is not None else ""

    key_points = [
        f"Projected units sold: {growth * 100:+.1f}% "
        f"(observed baseline {output.baseline_units_sold:.1f} -> simulated projection {output.expected_units_sold:.1f}{target_str})."
    ]

    risks = []
    if output.inventory_constrained:
        risks.append("Projected demand exceeds available inventory — sales are capped at available fulfillment capacity.")
    if growth < -0.05:
        if kpi_name in ("revenue", "profit"):
            risks.append(f"Volume contraction ({growth * 100:+.1f}%) observed under price optimization; acceptable if margin gain offsets volume loss.")
        else:
            risks.append(f"This strategy is projected to reduce sales volume ({growth * 100:+.1f}%).")

    assumptions = [
        f"Based on the Digital Twin simulation using {output.model_name} {output.model_version}.",
        f"Observed historical sales baseline is {output.baseline_units_sold:.1f} units; projected outcome is model-inferred.",
    ]
    if causal_context is not None:
        assumptions.append(
            f"Causal pathway to demand/revenue: {causal_context.strongest_pathway_evidence.replace('_', ' ')} "
            "(from the business's own causal graph)."
        )

    return AgentEvaluationResult("business_analyst", round(score, 4), key_points, risks, assumptions)


def review(own: AgentEvaluationResult, peers: dict[str, AgentEvaluationResult], output: SimulationOutput) -> PeerReview:
    fa = peers.get("financial_advisor")
    rm = peers.get("risk_manager")
    challenges: list[str] = []
    adjusted: float | None = None

    growth = (
        (output.expected_units_sold - output.baseline_units_sold) / output.baseline_units_sold
        if output.baseline_units_sold > 1e-9
        else 0.0
    )

    # 1. Downside challenge: Finance likes a price move but volume collapses severely (>15% drop).
    if fa is not None and fa.score >= 0.6 and growth <= -0.15:
        challenges.append(
            f"Financial Advisor scores this {fa.score:.2f}, but it is projected to cut unit sales "
            f"{growth * 100:+.1f}% — severe demand destruction concern."
        )

    # 2. Downside concurrence: All peers negative and sales falling.
    if rm is not None and fa is not None and rm.score < 0.5 and fa.score < 0.5 and growth < 0:
        challenges.append("Concur with Risk/Finance: this strategy weakens the core sales trajectory.")
        adjusted = round(clamp01(own.score - 0.05), 4)

    # 3. Bidirectional reconciliation: Strong consensus across peers with verified safety and stable volume.
    if adjusted is None and fa is not None and rm is not None:
        if fa.score >= 0.65 and rm.score >= 0.65 and growth >= 0.0:
            # Positive peer consensus confirms operational viability without volume sacrifice
            adjusted = round(clamp01(own.score + 0.03), 4)

    return PeerReview(
        agent="business_analyst",
        concurs=not challenges or adjusted is None,
        challenges=challenges,
        adjusted_score=adjusted,
        rationale=(
            "Reviewed peer assessments for demand/growth consistency and operational feasibility."
            if challenges
            else "Operational and demand assumptions verified consistent with peer assessments."
        ),
    )

