"""Research Console — Ablation Studies (docs/PRD.md §14 / docs/EXPERIMENT_PLAN.md §E).

Runs the REAL decision pipeline (app.services.decision_service.analyze_goal)
on one controlled synthetic scenario, once at full strength and once with
each major component switched off via decision_service.PipelineOptions,
then reports the measured differences. No delta is fabricated.

Configurations:
  A. Full DecisionGPT
  B. Without Digital Twin      -> architecture A (forecast only; no strategy can be chosen)
  C. Without Causal Graph      -> PipelineOptions(use_causal_graph=False)
  D. Without Multi-Agent       -> PipelineOptions(use_multi_agent=False)  (single blended agent)
  E. Without Explainability     -> PipelineOptions(use_explainability=False)
  F. Without Memory            -> PipelineOptions(use_memory=False)

E and F act on the decision as *supporting context*, not as inputs to
strategy scoring, so on this synthetic scenario (no recorded outcomes yet,
so no memory insights exist to remove) their measured delta on the
quantitative metrics is genuinely zero — that is the honest result, and it
is reported as such with the reason.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.services import decision_service
from app.services.decision_service import PipelineOptions
from app.services.decision_architecture_service import (
    GOAL_TARGET_PERCENT,
    _cleanup_synthetic_business,
    _goal_achievement,
    _run_architecture_a,
    _seed_synthetic_business,
)


@dataclass
class AblationConfigResult:
    config: str
    label: str
    components_removed: list[str]
    selected_strategy_name: str | None
    expected_benefit: float
    risk_adjusted_score: float
    goal_achievement: float
    confidence: float | None
    note: str = ""


@dataclass
class AblationComparison:
    component_removed: str
    config: str
    full_goal_achievement: float
    ablated_goal_achievement: float
    delta_goal_achievement: float
    full_risk_adjusted_score: float
    ablated_risk_adjusted_score: float
    delta_risk_adjusted_score: float
    full_confidence: float | None
    ablated_confidence: float | None
    delta_confidence: float | None
    note: str


@dataclass
class AblationStudyResult:
    seed: int
    goal_target_percent: float
    configs: list[AblationConfigResult] = field(default_factory=list)
    comparisons: list[AblationComparison] = field(default_factory=list)
    model_versions: dict = field(default_factory=dict)
    label: str = "SYNTHETIC_SCENARIO"


def _run_full_pipeline(db: Session, options: PipelineOptions, config: str, label: str,
                       components_removed: list[str], seed: int, note: str = "") -> tuple[AblationConfigResult, dict]:
    business_id, goal_id = _seed_synthetic_business(db, seed=seed)
    model_versions: dict = {}
    try:
        result = decision_service.analyze_goal(db, business_id, goal_id, options=options)
        outcome = result.expected_outcome
        benefit = outcome["expected_revenue"] - outcome["baseline_revenue"]
        risk_adjusted = benefit * (1 - outcome["risk_score"])
        achievement = _goal_achievement(
            outcome["expected_revenue"], outcome["baseline_revenue"], GOAL_TARGET_PERCENT
        )
        model_versions = result.trace.get("model_versions", {})
        cfg = AblationConfigResult(
            config=config,
            label=label,
            components_removed=components_removed,
            selected_strategy_name=result.selected_strategy_name,
            expected_benefit=round(benefit, 2),
            risk_adjusted_score=round(risk_adjusted, 2),
            goal_achievement=achievement,
            confidence=result.confidence,
            note=note,
        )
    except AppError as exc:
        cfg = AblationConfigResult(
            config=config, label=label, components_removed=components_removed,
            selected_strategy_name=None, expected_benefit=0.0, risk_adjusted_score=0.0,
            goal_achievement=0.0, confidence=None, note=f"{note} ({exc.message})".strip(),
        )
    finally:
        _cleanup_synthetic_business(db, business_id)
    return cfg, model_versions


def run_ablation_study(db: Session, seed: int = 42) -> AblationStudyResult:
    configs: list[AblationConfigResult] = []
    model_versions: dict = {}

    full, mv = _run_full_pipeline(db, PipelineOptions(), "A", "Full DecisionGPT", [], seed)
    model_versions.update(mv)
    configs.append(full)

    # B — without Digital Twin: architecture A (forecast only).
    b_business_id, _ = _seed_synthetic_business(db, seed=seed)
    try:
        arch_a = _run_architecture_a(db, b_business_id)
        configs.append(
            AblationConfigResult(
                config="B", label="Without Digital Twin", components_removed=["digital_twin"],
                selected_strategy_name=None,
                expected_benefit=arch_a.expected_benefit,
                risk_adjusted_score=arch_a.risk_adjusted_score,
                goal_achievement=arch_a.goal_achievement,
                confidence=None,
                note="Digital Twin is the only prediction path a decision uses — without it no strategy "
                "can be recommended at all.",
            )
        )
    finally:
        _cleanup_synthetic_business(db, b_business_id)

    for config, label, opts, removed, note in [
        ("C", "Without Causal Graph", PipelineOptions(use_causal_graph=False), ["causal_graph"], ""),
        ("D", "Without Multi-Agent", PipelineOptions(use_multi_agent=False), ["multi_agent"],
         "A single blended agent replaces the Business Analyst / Financial Advisor / Risk Manager debate."),
        ("E", "Without Explainability", PipelineOptions(use_explainability=False), ["explainability"],
         "Explainability is generated from the already-selected strategy, not consulted while scoring."),
        ("F", "Without Memory", PipelineOptions(use_memory=False), ["memory"],
         "No recorded outcomes exist on this synthetic scenario, so there are no memory insights to remove."),
    ]:
        cfg, mv = _run_full_pipeline(db, opts, config, label, removed, seed, note)
        model_versions.update(mv)
        configs.append(cfg)

    comparisons: list[AblationComparison] = []
    for c in configs:
        if c.config == "A":
            continue
        comparisons.append(
            AblationComparison(
                component_removed=c.label,  # human-readable, e.g. "Without Digital Twin"
                config=c.config,
                full_goal_achievement=full.goal_achievement,
                ablated_goal_achievement=c.goal_achievement,
                delta_goal_achievement=round(full.goal_achievement - c.goal_achievement, 4),
                full_risk_adjusted_score=full.risk_adjusted_score,
                ablated_risk_adjusted_score=c.risk_adjusted_score,
                delta_risk_adjusted_score=round(full.risk_adjusted_score - c.risk_adjusted_score, 2),
                full_confidence=full.confidence,
                ablated_confidence=c.confidence,
                delta_confidence=(
                    round(full.confidence - c.confidence, 4)
                    if full.confidence is not None and c.confidence is not None
                    else None
                ),
                note=c.note,
            )
        )

    return AblationStudyResult(
        seed=seed,
        goal_target_percent=GOAL_TARGET_PERCENT,
        configs=configs,
        comparisons=comparisons,
        model_versions=model_versions,
    )
