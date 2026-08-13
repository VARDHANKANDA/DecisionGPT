"""Research Console — Decision Architecture Experiment (docs/PRD.md §13)
and Ablation Studies (docs/PRD.md §14).

Compares architectures on the *same* synthetic scenario and the *same*
candidate strategy grid, always calling the real production code for each
component (forecast_service, digital_twin_service, the real agents) — no
architecture's result is hand-typed:

    A. Prediction only            — forecast_service, no strategy selected.
    B. Prediction + Digital Twin  — highest-expected-revenue candidate, no agent scoring.
    C. + Single agent             — app.agents.single_agent picks the best candidate.
    D. Full DecisionGPT           — the real production multi-agent pipeline (decision_service).

Ablation reuses the same machinery: "without Digital Twin" has no
predictive-simulation component to remove (Digital Twin is the *only*
prediction path decisions use — see docs/AI_MODULE_SPECIFICATION.md §6
"reuse validated predictive components"), so it is represented by
architecture A; "without Multi-Agent" by architecture C (single agent
still exists, just not three); "without Explainability"/"without Memory"
are measured by disabling the corresponding decision_service inputs
(the causal graph version + memory insights lookup) since those don't
change the selected strategy's numbers, only its supporting context.

Every run uses a synthetic research business (docs/EXPERIMENT_PLAN.md §8
"use controlled synthetic scenarios") — clearly labeled, created fresh and
deleted after the run. This never touches, and is never visible to, a
real SME business (the research console has no way to look one up; it
only ever creates and destroys its own).
"""
import random
import time
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.agents import single_agent
from app.analytics import digital_twin_service, forecast_service
from app.analytics.digital_twin_service import Action
from app.core.errors import AppError
from app.models.agent import AgentEvaluation, AgentRun
from app.models.business import Business
from app.models.causal import CausalEdge, CausalGraph
from app.models.decision import Decision
from app.models.digital_twin import DigitalTwinSimulation, DigitalTwinState
from app.models.goal import Goal
from app.models.marketing import MarketingCampaign
from app.models.memory import BusinessMemory
from app.models.product import Product
from app.models.sale import Sale
from app.models.strategy import Strategy
from app.services.decision_service import CANDIDATE_GRID, strategy_name_for_actions

SYNTHETIC_BUSINESS_NAME_PREFIX = "Research Synthetic Business"
GOAL_TARGET_PERCENT = 15.0


@dataclass
class ArchitectureResult:
    architecture: str
    label: str
    selected_strategy_name: str | None
    expected_benefit: float
    risk_adjusted_score: float
    goal_achievement: float
    latency_seconds: float
    note: str = ""


@dataclass
class DecisionArchitectureRun:
    seed: int
    goal_target_percent: float
    results: list[ArchitectureResult]
    label: str = "SYNTHETIC_SCENARIO"


def _seed_synthetic_business(db: Session, seed: int) -> tuple[str, str]:
    rng = random.Random(seed)

    business = Business(
        name=f"{SYNTHETIC_BUSINESS_NAME_PREFIX} ({seed})",
        industry="Research",
        business_type="Synthetic",
        business_size="N/A",
        country="IN",
        currency="INR",
        description="Ephemeral business created for a Decision Architecture / Ablation research run.",
    )
    db.add(business)
    db.flush()

    product = Product(
        business_id=business.id, external_product_id="R000", name="Research Product",
        unit_cost=200, selling_price=500,
    )
    db.add(product)
    db.flush()

    today = date.today()
    start = today - timedelta(days=90)
    for day_offset in range(90):
        sale_date = start + timedelta(days=day_offset)
        promo = day_offset % 10 == 0
        price = 450 if promo else 500
        quantity = rng.randint(8, 14) + (4 if promo else 0)
        db.add(
            Sale(
                business_id=business.id, product_id=product.id, sale_date=sale_date,
                quantity=quantity, unit_price=price, discount=0, revenue=price * quantity,
            )
        )
        if day_offset % 3 == 0:
            db.add(
                MarketingCampaign(
                    business_id=business.id, campaign_date=sale_date, channel="Research",
                    spend=1000 + rng.randint(-200, 200), impressions=5000, clicks=200, conversions=15,
                    attributed_revenue=6000,
                )
            )

    goal = Goal(
        business_id=business.id, objective="increase_revenue", target_value=GOAL_TARGET_PERCENT,
        target_unit="percent", primary_kpi="revenue", time_horizon=2, status="active",
    )
    db.add(goal)
    db.commit()
    return business.id, goal.id


def _cleanup_synthetic_business(db: Session, business_id: str) -> None:
    strategy_ids = [s.id for s in db.query(Strategy.id).filter(Strategy.business_id == business_id).all()]
    if strategy_ids:
        db.query(AgentEvaluation).filter(AgentEvaluation.strategy_id.in_(strategy_ids)).delete(
            synchronize_session=False
        )
    causal_graph_ids = [
        g.id for g in db.query(CausalGraph.id).filter(CausalGraph.business_id == business_id).all()
    ]
    if causal_graph_ids:
        db.query(CausalEdge).filter(CausalEdge.causal_graph_id.in_(causal_graph_ids)).delete(
            synchronize_session=False
        )
    for model in (
        AgentRun, Decision, Strategy, DigitalTwinSimulation, DigitalTwinState,
        CausalGraph, BusinessMemory, MarketingCampaign, Sale, Product, Goal,
    ):
        db.query(model).filter(model.business_id == business_id).delete(synchronize_session=False)
    db.query(Business).filter(Business.id == business_id).delete()
    db.commit()


def _goal_achievement(expected_revenue: float, baseline_revenue: float, target_percent: float) -> float:
    if baseline_revenue <= 1e-9:
        return 0.0
    actual_percent = (expected_revenue - baseline_revenue) / baseline_revenue * 100
    return round(min(1.0, max(0.0, actual_percent / target_percent)), 4)


def _simulate_all_candidates(db: Session, business_id: str) -> list[tuple[str, "digital_twin_service.SimulationResult"]]:
    results = []
    for action_dicts in CANDIDATE_GRID:
        actions = [Action(type=a["type"], value=a["value"]) for a in action_dicts]
        try:
            sim = digital_twin_service.simulate_strategy(db, business_id, actions)
            results.append((strategy_name_for_actions(action_dicts), sim))
        except AppError:
            continue
    return results


def _run_architecture_a(db: Session, business_id: str) -> ArchitectureResult:
    start = time.perf_counter()
    try:
        forecast_service.forecast_sales(db, business_id, horizon_days=14)
        note = "Forecast only produced — this architecture has no mechanism to recommend a strategy."
    except AppError as exc:
        note = f"Forecast failed: {exc.message}"
    return ArchitectureResult(
        "A", "Prediction only", None, 0.0, 0.0, 0.0, round(time.perf_counter() - start, 4), note
    )


def _run_architecture_b(db: Session, business_id: str, target_percent: float) -> ArchitectureResult:
    start = time.perf_counter()
    candidates = _simulate_all_candidates(db, business_id)
    if not candidates:
        return ArchitectureResult("B", "Prediction + Digital Twin", None, 0.0, 0.0, 0.0, round(time.perf_counter() - start, 4))
    name, best = max(candidates, key=lambda item: item[1].output.expected_revenue)
    benefit = best.output.expected_revenue - best.output.baseline_revenue
    risk_adjusted = benefit * (1 - best.output.risk_score)
    achievement = _goal_achievement(best.output.expected_revenue, best.output.baseline_revenue, target_percent)
    return ArchitectureResult(
        "B", "Prediction + Digital Twin", name, round(benefit, 2), round(risk_adjusted, 2), achievement,
        round(time.perf_counter() - start, 4),
    )


def _run_architecture_c(db: Session, business_id: str, target_percent: float) -> ArchitectureResult:
    start = time.perf_counter()
    candidates = _simulate_all_candidates(db, business_id)
    if not candidates:
        return ArchitectureResult("C", "Prediction + Digital Twin + Single Agent", None, 0.0, 0.0, 0.0, round(time.perf_counter() - start, 4))
    scored = [(name, sim, single_agent.evaluate(sim.output)) for name, sim in candidates]
    name, best_sim, _ = max(scored, key=lambda item: item[2].score)
    benefit = best_sim.output.expected_revenue - best_sim.output.baseline_revenue
    risk_adjusted = benefit * (1 - best_sim.output.risk_score)
    achievement = _goal_achievement(best_sim.output.expected_revenue, best_sim.output.baseline_revenue, target_percent)
    return ArchitectureResult(
        "C", "Prediction + Digital Twin + Single Agent", name, round(benefit, 2), round(risk_adjusted, 2),
        achievement, round(time.perf_counter() - start, 4),
    )


def _run_architecture_d(db: Session, business_id: str, goal_id: str, target_percent: float) -> ArchitectureResult:
    from app.services import decision_service

    start = time.perf_counter()
    try:
        result = decision_service.analyze_goal(db, business_id, goal_id)
    except AppError as exc:
        return ArchitectureResult(
            "D", "Full DecisionGPT", None, 0.0, 0.0, 0.0, round(time.perf_counter() - start, 4), exc.message
        )
    outcome = result.expected_outcome
    benefit = outcome["expected_revenue"] - outcome["baseline_revenue"]
    risk_adjusted = benefit * (1 - outcome["risk_score"])
    achievement = _goal_achievement(outcome["expected_revenue"], outcome["baseline_revenue"], target_percent)
    return ArchitectureResult(
        "D", "Full DecisionGPT", result.selected_strategy_name, round(benefit, 2), round(risk_adjusted, 2),
        achievement, round(time.perf_counter() - start, 4),
    )


def run_decision_architecture_experiment(db: Session, seed: int = 42) -> DecisionArchitectureRun:
    business_id, goal_id = _seed_synthetic_business(db, seed)
    try:
        results = [
            _run_architecture_a(db, business_id),
            _run_architecture_b(db, business_id, GOAL_TARGET_PERCENT),
            _run_architecture_c(db, business_id, GOAL_TARGET_PERCENT),
            _run_architecture_d(db, business_id, goal_id, GOAL_TARGET_PERCENT),
        ]
    finally:
        _cleanup_synthetic_business(db, business_id)

    return DecisionArchitectureRun(seed=seed, goal_target_percent=GOAL_TARGET_PERCENT, results=results)
