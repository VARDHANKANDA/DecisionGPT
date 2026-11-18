"""Strategy Optimizer — docs/MULTI_AGENT_SPECIFICATION.md §2, §7.

The one fixed scoring formula (§7: "Fix the scoring formula before final
experiments"), version-tagged so experiments referencing it stay
reproducible even if it's revised later:

    strategy_score = normalized_goal_benefit - normalized_risk_penalty

where `normalized_goal_benefit` is the mean of the Business Analyst and
Financial Advisor scores (do they independently think this strategy grows
the business?) and `normalized_risk_penalty` is `1 - risk_manager_score`
(the Risk Manager's score is already a 0..1 safety score). This is how
"agent disagreement" (§2 Strategy Optimizer bullet) gets resolved: a
strategy the growth-focused agents like but the Risk Manager doesn't gets
pulled back down, rather than any agent's number being overridden.

`resolve()` runs the round-2 debate: it applies each agent's post-review
adjusted score, records the conflicts raised, recomputes the strategy
score, and derives a *documented* confidence value (never an arbitrary
percentage — see the `confidence_basis` it returns).
"""
from dataclasses import dataclass, field
from statistics import pstdev

from app.agents.base import AgentEvaluationResult, PeerReview

FORMULA_VERSION = "v2"


def compute_strategy_score(
    business_analyst_score: float,
    financial_advisor_score: float,
    risk_manager_score: float,
    risk_penalty_weight: float = 1.0,
    scoring_mode: str = "linear",
) -> float:
    """Computes strategy score from agent evaluations.
    - Default `scoring_mode="linear"`: the fixed §7 scoring rule `(BA+FA)/2 - λ·(1-RM)`.
    - `scoring_mode="calibrated"`: multiplicative risk discounting `((BA+FA)/2) · max(0, 1 - λ·(1-RM))`
      preventing negative scores and avoiding crushing profitable actions with modest risk.
    - `scoring_mode="bounded"`: linear score clamped to [0, 1].
    """
    goal_benefit = (business_analyst_score + financial_advisor_score) / 2
    if scoring_mode in ("calibrated", "multiplicative"):
        risk_discount = max(0.0, 1.0 - risk_penalty_weight * (1.0 - risk_manager_score))
        return round(goal_benefit * risk_discount, 4)
    elif scoring_mode == "bounded":
        risk_penalty = risk_penalty_weight * (1.0 - risk_manager_score)
        return round(max(0.0, min(1.0, goal_benefit - risk_penalty)), 4)
    else:
        risk_penalty = risk_penalty_weight * (1.0 - risk_manager_score)
        return round(goal_benefit - risk_penalty, 4)


def compute_calibrated_strategy_score(
    business_analyst_score: float,
    financial_advisor_score: float,
    risk_manager_score: float,
    risk_penalty_weight: float = 0.35,
) -> float:
    """Helper for calibrated multiplicative strategy scoring (Candidate C formulation)."""
    return compute_strategy_score(
        business_analyst_score,
        financial_advisor_score,
        risk_manager_score,
        risk_penalty_weight=risk_penalty_weight,
        scoring_mode="calibrated",
    )


@dataclass
class ResolvedDecision:
    final_score: float
    round1_scores: dict[str, float]
    round2_scores: dict[str, float]
    conflicts: list[dict] = field(default_factory=list)
    resolution_rationale: str = ""
    confidence: float = 0.0
    confidence_basis: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "formula_version": FORMULA_VERSION,
            "final_score": self.final_score,
            "round1_scores": self.round1_scores,
            "round2_scores": self.round2_scores,
            "conflicts": self.conflicts,
            "resolution_rationale": self.resolution_rationale,
            "confidence": self.confidence,
            "confidence_basis": self.confidence_basis,
        }


def resolve_single(sa: AgentEvaluationResult, output, causal_evidence_factor: float = 1.0) -> ResolvedDecision:
    """Ablation 'without Multi-Agent' — a single blended agent, no debate.
    Confidence uses the same documented components as the multi-agent path,
    minus the inter-agent agreement term (there's only one agent)."""
    band = output.revenue_upper_bound - output.revenue_lower_bound
    uncertainty_ratio = band / output.expected_revenue if output.expected_revenue > 1e-9 else 1.0
    uncertainty_penalty = min(0.5, uncertainty_ratio * 0.2)
    confidence = round(
        max(0.0, min(1.0, sa.score * causal_evidence_factor * (1.0 - uncertainty_penalty))), 4
    )
    return ResolvedDecision(
        final_score=round(sa.score, 4),
        round1_scores={"single_agent": sa.score},
        round2_scores={"single_agent": sa.score},
        conflicts=[],
        resolution_rationale="Single-agent baseline (multi-agent debate disabled): score taken directly.",
        confidence=confidence,
        confidence_basis={
            "single_agent_score": round(sa.score, 4),
            "causal_evidence_factor": round(causal_evidence_factor, 4),
            "uncertainty_penalty": round(uncertainty_penalty, 4),
            "agreement_factor": 1.0,
            "risk_factor": round(sa.score, 4),
            "formula": "single_agent_score * causal_evidence * (1 - uncertainty_penalty)",
        },
    )


def resolve(
    round1: dict[str, AgentEvaluationResult],
    reviews: list[PeerReview],
    output,
    causal_evidence_factor: float = 1.0,
    risk_penalty_weight: float = 1.0,
    scoring_mode: str = "linear",
) -> ResolvedDecision:
    """Aggregate round-1 evaluations + round-2 reviews into a single
    resolved decision for one strategy.

    `risk_penalty_weight` defaults to 1.0 (the production §7 formula). The
    research-only "Risk-Penalty Sensitivity" variant passes 0.0 to isolate
    whether the risk-penalty term is what drives strategy selection — the Risk
    Manager still evaluates, still challenges peers in round 2, and still feeds
    the confidence `risk_factor`; only its weight in the ranking score moves."""
    ba = round1["business_analyst"]
    fa = round1["financial_advisor"]
    rm = round1["risk_manager"]

    round1_scores = {"business_analyst": ba.score, "financial_advisor": fa.score, "risk_manager": rm.score}

    # Apply post-review self-adjustments (only BA / FA move their own score;
    # the Risk Manager challenges rather than self-adjusts).
    round2_scores = dict(round1_scores)
    for r in reviews:
        if r.adjusted_score is not None:
            round2_scores[r.agent] = r.adjusted_score

    final_score = compute_strategy_score(
        round2_scores["business_analyst"],
        round2_scores["financial_advisor"],
        round2_scores["risk_manager"],
        risk_penalty_weight=risk_penalty_weight,
        scoring_mode=scoring_mode,
    )

    conflicts: list[dict] = []
    seen_concerns = set()
    for r in reviews:
        for c in r.challenges:
            key = (r.agent, c)
            if key not in seen_concerns:
                seen_concerns.add(key)
                conflicts.append({"raised_by": r.agent, "concern": c})

    # --- documented confidence -----------------------------------------
    # 1. agreement: how close the three round-1 scores are (population
    #    stddev; 0 => perfect agreement => factor 1.0).
    agreement = 1.0 - min(1.0, 2.0 * pstdev(list(round1_scores.values())))
    # 2. risk: the Risk Manager's own safety score (already 0..1).
    risk_factor = round2_scores["risk_manager"]
    # 3. uncertainty: simulation revenue-interval width vs expected.
    band = output.revenue_upper_bound - output.revenue_lower_bound
    uncertainty_ratio = band / output.expected_revenue if output.expected_revenue > 1e-9 else 1.0
    uncertainty_penalty = min(0.5, uncertainty_ratio * 0.2)
    # 4. causal evidence factor (0.6..1.0), passed in by the caller.
    confidence = max(
        0.0,
        min(1.0, agreement * risk_factor * causal_evidence_factor * (1.0 - uncertainty_penalty)),
    )
    confidence = round(confidence, 4)

    confidence_basis = {
        "agreement_factor": round(agreement, 4),
        "risk_factor": round(risk_factor, 4),
        "causal_evidence_factor": round(causal_evidence_factor, 4),
        "uncertainty_penalty": round(uncertainty_penalty, 4),
        "formula": "agreement * risk * causal_evidence * (1 - uncertainty_penalty)",
    }
    if risk_penalty_weight != 1.0:
        confidence_basis["risk_penalty_weight"] = round(risk_penalty_weight, 4)
        confidence_basis["variant"] = "risk_penalty_sensitivity (research-only; production weight = 1.0)"
    if scoring_mode != "linear":
        confidence_basis["scoring_mode"] = scoring_mode

    if conflicts:
        raisers = sorted({c["raised_by"].replace("_", " ").title() for c in conflicts})
        moved = [a for a in round1_scores if round2_scores[a] != round1_scores[a]]
        rationale = (
            f"{len(conflicts)} conflict(s) raised by {', '.join(raisers)}. "
            + (
                f"Self-adjusted after review: {', '.join(a.replace('_', ' ') for a in moved)}. "
                if moved
                else "No agent revised its own score; "
            )
            + f"Final strategy score {final_score:.3f} via {FORMULA_VERSION} formula ({scoring_mode})."
        )

    else:
        rationale = (
            f"All three agents concurred (round-1 score spread {pstdev(list(round1_scores.values())):.3f}). "
            f"Final strategy score {final_score:.3f}."
        )

    return ResolvedDecision(
        final_score=final_score,
        round1_scores=round1_scores,
        round2_scores=round2_scores,
        conflicts=conflicts,
        resolution_rationale=rationale,
        confidence=confidence,
        confidence_basis=confidence_basis,
    )
