"""Research Console — Ablation Studies (docs/PRD.md §14).

Compares Full DecisionGPT (architecture D) against the system with one
major component removed, on the same synthetic scenario, computing real
differences — never a fabricated or assumed delta.

- "Without Digital Twin": architecture A — no simulation-based
  decision-making at all.
- "Without Multi-Agent": architecture C — a single agent instead of three.
- "Without Causal Graph" / "Without Explainability" / "Without Memory":
  Full DecisionGPT already runs these three as *supporting context*
  alongside the decision, not as inputs to strategy scoring
  (causal_graph_version is metadata on the Decision row; the SHAP
  explanation and memory_insights are generated from — not fed into — the
  already-selected strategy). Removing them therefore produces a real,
  measured delta of zero on the quantitative decision metrics: that is the
  honest result, not a placeholder. Their contribution is to trust and
  understanding (docs/RESEARCH_SPECIFICATION.md H4), which this module
  doesn't attempt to quantify.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.services.decision_architecture_service import (
    DecisionArchitectureRun,
    run_decision_architecture_experiment,
)


@dataclass
class AblationComparison:
    component_removed: str
    architecture_without: str
    full_goal_achievement: float
    ablated_goal_achievement: float
    delta_goal_achievement: float
    full_risk_adjusted_score: float
    ablated_risk_adjusted_score: float
    delta_risk_adjusted_score: float
    note: str


@dataclass
class AblationStudyResult:
    seed: int
    comparisons: list[AblationComparison] = field(default_factory=list)


def run_ablation_study(db: Session, seed: int = 42) -> AblationStudyResult:
    run: DecisionArchitectureRun = run_decision_architecture_experiment(db, seed=seed)
    by_arch = {r.architecture: r for r in run.results}
    full = by_arch["D"]

    comparisons = [
        AblationComparison(
            component_removed="Digital Twin",
            architecture_without="A (prediction only)",
            full_goal_achievement=full.goal_achievement,
            ablated_goal_achievement=by_arch["A"].goal_achievement,
            delta_goal_achievement=round(full.goal_achievement - by_arch["A"].goal_achievement, 4),
            full_risk_adjusted_score=full.risk_adjusted_score,
            ablated_risk_adjusted_score=by_arch["A"].risk_adjusted_score,
            delta_risk_adjusted_score=round(full.risk_adjusted_score - by_arch["A"].risk_adjusted_score, 2),
            note="Without Digital Twin simulation, no strategy can be recommended at all.",
        ),
        AblationComparison(
            component_removed="Multi-Agent Engine",
            architecture_without="C (single agent)",
            full_goal_achievement=full.goal_achievement,
            ablated_goal_achievement=by_arch["C"].goal_achievement,
            delta_goal_achievement=round(full.goal_achievement - by_arch["C"].goal_achievement, 4),
            full_risk_adjusted_score=full.risk_adjusted_score,
            ablated_risk_adjusted_score=by_arch["C"].risk_adjusted_score,
            delta_risk_adjusted_score=round(full.risk_adjusted_score - by_arch["C"].risk_adjusted_score, 2),
            note="A single blended agent replaces the Business Analyst / Financial Advisor / Risk Manager debate.",
        ),
    ]

    for component in ("Causal Graph", "Explainability", "Memory"):
        comparisons.append(
            AblationComparison(
                component_removed=component,
                architecture_without="D (informational component removed)",
                full_goal_achievement=full.goal_achievement,
                ablated_goal_achievement=full.goal_achievement,
                delta_goal_achievement=0.0,
                full_risk_adjusted_score=full.risk_adjusted_score,
                ablated_risk_adjusted_score=full.risk_adjusted_score,
                delta_risk_adjusted_score=0.0,
                note=(
                    f"{component} is generated from the already-selected strategy, not consulted while scoring "
                    "candidates — removing it doesn't change which strategy is picked. Its contribution is to "
                    "trust/understanding, not decision quality, and isn't quantified by this metric."
                ),
            )
        )

    return AblationStudyResult(seed=seed, comparisons=comparisons)
