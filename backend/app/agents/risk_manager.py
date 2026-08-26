"""Risk Manager agent — docs/MULTI_AGENT_SPECIFICATION.md §2: downside,
uncertainty, operational risk, customer impact.

Documented scoring method (a 0..1 "safety" score, higher = safer):
`score = clamp(1 - risk_score - uncertainty_penalty - inventory_penalty - causal_penalty, 0, 1)`
- `risk_score` is the Digital Twin's own extrapolation-risk score (real,
  computed — docs/DIGITAL_TWIN_SPECIFICATION.md §9).
- `uncertainty_penalty` is the width of the simulation's revenue prediction
  interval relative to the expected revenue, capped at 0.4 so one very
  uncertain input can't single-handedly zero out the score.
- `inventory_penalty` is a fixed 0.15 when the simulation had to cap sales
  at available inventory (a real operational constraint the strategy runs
  into, not a guess).
- `causal_penalty` is a fixed 0.10 when the causal pathway behind this
  strategy has only ASSUMED evidence in this business's data (the projected
  effect rests on an unvalidated domain hypothesis) — 0 otherwise.

Round 2 (`review`): the Risk Manager challenges optimistic peers when their
scores materially exceed what the extrapolation risk / uncertainty
justify.
"""
from app.agents.base import AgentEvaluationResult, PeerReview, clamp01
from app.analytics.digital_twin_service import SimulationOutput
from app.models.goal import Goal

UNCERTAINTY_PENALTY_CAP = 0.4
INVENTORY_PENALTY = 0.15
CAUSAL_ASSUMED_PENALTY = 0.10


def evaluate(output: SimulationOutput, goal: Goal, causal_context=None) -> AgentEvaluationResult:
    band_width = output.revenue_upper_bound - output.revenue_lower_bound
    uncertainty_ratio = band_width / output.expected_revenue if output.expected_revenue > 1e-9 else 0.0
    uncertainty_penalty = min(UNCERTAINTY_PENALTY_CAP, uncertainty_ratio * 0.2)
    inventory_penalty = INVENTORY_PENALTY if output.inventory_constrained else 0.0

    causal_penalty = 0.0
    causal_evidence = None
    if causal_context is not None:
        causal_evidence = causal_context.strongest_pathway_evidence
        if causal_evidence == "assumed":
            causal_penalty = CAUSAL_ASSUMED_PENALTY

    score = clamp01(1.0 - output.risk_score - uncertainty_penalty - inventory_penalty - causal_penalty)

    key_points = [f"Extrapolation risk: {output.risk_level} (risk score {output.risk_score:.2f})."]
    if output.customer_impact is not None:
        key_points.append(f"Estimated customer impact: {output.customer_impact:+d}.")
    if causal_evidence is not None:
        key_points.append(f"Causal evidence behind this lever: {causal_evidence.replace('_', ' ')}.")

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
    if causal_penalty > 0:
        risks.append(
            "The causal pathway from this strategy's lever to revenue is only an ASSUMED domain "
            "hypothesis in your data — the projected effect is not causally validated."
        )

    assumptions = [f"Based on the Digital Twin simulation using {output.model_name} v{output.model_version}."]

    result = AgentEvaluationResult("risk_manager", round(score, 4), key_points, risks, assumptions)
    result.meta["uncertainty_ratio"] = round(uncertainty_ratio, 4)
    result.meta["causal_penalty"] = causal_penalty
    return result


def review(own: AgentEvaluationResult, peers: dict[str, AgentEvaluationResult], output: SimulationOutput) -> PeerReview:
    ba = peers.get("business_analyst")
    fa = peers.get("financial_advisor")
    challenges: list[str] = []
    adjusted: float | None = None

    optimistic = [p for p in (ba, fa) if p is not None and p.score >= 0.65]
    if optimistic and output.risk_level == "HIGH":
        names = " and ".join(p.agent.replace("_", " ").title() for p in optimistic)
        challenges.append(
            f"{names} score this highly, but extrapolation risk is HIGH (risk score "
            f"{output.risk_score:.2f}) — the model is predicting well outside its observed input range."
        )

    if optimistic and own.meta.get("uncertainty_ratio", 0) > 1.0:
        challenges.append(
            "Peer optimism is not supported by the simulation's uncertainty: the revenue interval is "
            "wider than the expected value itself."
        )

    if own.meta.get("causal_penalty", 0) > 0 and optimistic:
        challenges.append(
            "Peers are treating the projected effect as reliable, but no causal pathway for this lever "
            "rises above ASSUMED evidence in this business's data."
        )

    return PeerReview(
        agent="risk_manager",
        concurs=not challenges,
        challenges=challenges,
        adjusted_score=adjusted,  # the Risk Manager challenges peers rather than moving its own score
        rationale=(
            "Challenged peer optimism against extrapolation risk / uncertainty / causal evidence."
            if challenges
            else "Peer assessments are within what risk and uncertainty support."
        ),
    )
