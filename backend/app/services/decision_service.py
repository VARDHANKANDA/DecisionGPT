"""Multi-Agent Decision Engine orchestration — docs/MULTI_AGENT_SPECIFICATION.md §3:

    Goal -> Candidate Strategies -> Digital Twin
         -> {Business Analyst, Financial Advisor, Risk Manager} -> Strategy Optimizer -> Decision

Every number an agent sees already came from a real, tested analytical
component (app.analytics.digital_twin_service, itself the registered
forecasting model re-run with each strategy's actions) — this module never
invents a strategy's outcome, only generates the candidate action grid and
persists the full chain for traceability (docs/RESEARCH_TRACEABILITY.md).
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.agents import business_analyst, financial_advisor, risk_manager, strategy_optimizer
from app.agents.base import AgentEvaluationResult
from app.analytics import digital_twin_service, forecast_service
from app.analytics.digital_twin_service import Action, SimulationOutput
from app.core.errors import AppError, InsufficientDataError, NotFoundError
from app.models.agent import AgentEvaluation, AgentRun
from app.models.causal import CausalGraph
from app.models.decision import Decision
from app.models.goal import Goal
from app.models.strategy import Strategy
from app.services.llm_service import LLMService

# Docs/DIGITAL_TWIN_SPECIFICATION.md §7's suggested grid (marketing ±5/±10%,
# price ±5%), kept small and fixed — "avoid combinatorial explosion".
# inventory_change is intentionally excluded from the default grid: not
# every business has inventory data on file, and this keeps every candidate
# simulatable for any business that clears the forecast-sufficiency check.
CANDIDATE_GRID: list[list[dict]] = [
    [{"type": "marketing_change", "value": 10}],
    [{"type": "marketing_change", "value": 5}],
    [{"type": "marketing_change", "value": -10}],
    [{"type": "price_change", "value": 5}],
    [{"type": "price_change", "value": -5}],
    [{"type": "marketing_change", "value": 10}, {"type": "price_change", "value": -5}],
]

RISK_LEVEL_MAP = {"LOW": "low", "MODERATE": "medium", "HIGH": "high"}
ACTION_LABELS = {"marketing_change": "Marketing", "price_change": "Price", "inventory_change": "Inventory"}


@dataclass
class StrategyAnalysis:
    strategy_id: str
    strategy_name: str
    actions: list[dict]
    simulation_id: str
    business_analyst: AgentEvaluationResult
    financial_advisor: AgentEvaluationResult
    risk_manager: AgentEvaluationResult
    strategy_score: float
    output: SimulationOutput


@dataclass
class DecisionResult:
    id: str
    business_id: str
    goal_id: str
    selected_strategy_id: str
    selected_strategy_name: str
    selected_strategy_score: float
    expected_outcome: dict
    risk_level: str
    confidence: float
    reasoning: str
    causal_graph_version: str | None
    agent_reviews: dict = field(default_factory=dict)
    alternatives: list[dict] = field(default_factory=list)
    skipped_strategies: list[str] = field(default_factory=list)


def _strategy_name(actions: list[dict]) -> str:
    parts = []
    for a in actions:
        sign = "+" if a["value"] >= 0 else ""
        parts.append(f"{ACTION_LABELS[a['type']]} {sign}{a['value']:g}%")
    return " & ".join(parts)


def _latest_causal_graph_version(db: Session, business_id: str) -> str | None:
    graph = (
        db.query(CausalGraph)
        .filter(CausalGraph.business_id == business_id)
        .order_by(CausalGraph.created_at.desc())
        .first()
    )
    return graph.version if graph else None


def _alt_summary(analysis: StrategyAnalysis) -> dict:
    return {
        "strategy_id": analysis.strategy_id,
        "strategy_name": analysis.strategy_name,
        "actions": analysis.actions,
        "strategy_score": analysis.strategy_score,
        "risk_level": RISK_LEVEL_MAP[analysis.output.risk_level],
        "expected_revenue": analysis.output.expected_revenue,
    }


def analyze_goal(db: Session, business_id: str, goal_id: str) -> DecisionResult:
    goal = db.get(Goal, goal_id)
    if goal is None or goal.business_id != business_id:
        raise NotFoundError(f"Goal {goal_id} not found for this business.")

    # All candidates share the same underlying data-sufficiency requirement
    # (forecast_service.check_forecast_sufficiency) — if the business can't
    # support one simulation it can't support any, so this is checked once,
    # up front, rather than failing candidate-by-candidate.
    sufficient, reason = forecast_service.check_forecast_sufficiency(db, business_id)
    if not sufficient:
        raise InsufficientDataError(reason or "Not enough sales history to analyze this goal.")

    analyses: list[StrategyAnalysis] = []
    skipped: list[str] = []

    for action_dicts in CANDIDATE_GRID:
        actions = [Action(type=a["type"], value=a["value"]) for a in action_dicts]
        strategy_name = _strategy_name(action_dicts)

        strategy_row = Strategy(
            business_id=business_id, goal_id=goal_id, strategy_name=strategy_name, actions_json=action_dicts
        )
        db.add(strategy_row)
        db.flush()

        try:
            simulation = digital_twin_service.simulate_strategy(db, business_id, actions, goal_id=goal_id)
        except AppError as exc:
            skipped.append(f"{strategy_name}: {exc.message}")
            continue

        ba = business_analyst.evaluate(simulation.output, goal)
        fa = financial_advisor.evaluate(simulation.output, goal)
        rm = risk_manager.evaluate(simulation.output, goal)

        for agent_result in (ba, fa, rm):
            db.add(
                AgentEvaluation(
                    strategy_id=strategy_row.id,
                    agent_name=agent_result.agent,
                    evaluation_json={
                        "key_points": agent_result.key_points,
                        "risks": agent_result.risks,
                        "assumptions": agent_result.assumptions,
                    },
                    score=agent_result.score,
                )
            )

        strategy_score = strategy_optimizer.compute_strategy_score(ba.score, fa.score, rm.score)

        analyses.append(
            StrategyAnalysis(
                strategy_id=strategy_row.id,
                strategy_name=strategy_name,
                actions=action_dicts,
                simulation_id=simulation.id,
                business_analyst=ba,
                financial_advisor=fa,
                risk_manager=rm,
                strategy_score=strategy_score,
                output=simulation.output,
            )
        )

    if not analyses:
        db.rollback()
        raise InsufficientDataError(
            "No candidate strategy could be simulated for this business right now.",
            details={"skipped": skipped},
        )

    analyses.sort(key=lambda a: a.strategy_score, reverse=True)
    best = analyses[0]
    # Every candidate in CANDIDATE_GRID was actually simulated and scored —
    # surface all of them (it's a small, fixed grid, not an unbounded list)
    # rather than arbitrarily hiding some from the response.
    alternatives = analyses[1:]

    risk_level = RISK_LEVEL_MAP[best.output.risk_level]
    confidence = best.risk_manager.score

    llm = LLMService()
    agent_reviews = {
        agent.agent: llm.evaluate_agent(
            agent.agent,
            {"key_points": agent.key_points, "risks": agent.risks, "assumptions": agent.assumptions},
        )
        for agent in (best.business_analyst, best.financial_advisor, best.risk_manager)
    }
    reasoning = llm.generate_strategy_explanation(
        {
            "strategy_name": best.strategy_name,
            "expected_revenue": best.output.expected_revenue,
            "risk_level": risk_level,
        }
    )

    causal_graph_version = _latest_causal_graph_version(db, business_id)

    decision_row = Decision(
        business_id=business_id,
        goal_id=goal_id,
        selected_strategy_id=best.strategy_id,
        expected_outcome_json=digital_twin_service.output_to_dict(best.output),
        risk_level=risk_level,
        confidence=confidence,
        reasoning=reasoning,
        causal_graph_version=causal_graph_version,
    )
    db.add(decision_row)
    db.flush()

    for agent in (best.business_analyst, best.financial_advisor, best.risk_manager):
        db.add(
            AgentRun(
                business_id=business_id,
                decision_id=decision_row.id,
                agent_name=agent.agent,
                input_json={"strategy_id": best.strategy_id, "actions": best.actions},
                output_json={
                    "score": agent.score,
                    "key_points": agent.key_points,
                    "risks": agent.risks,
                    "assumptions": agent.assumptions,
                },
            )
        )

    db.commit()
    db.refresh(decision_row)

    return DecisionResult(
        id=decision_row.id,
        business_id=business_id,
        goal_id=goal_id,
        selected_strategy_id=best.strategy_id,
        selected_strategy_name=best.strategy_name,
        selected_strategy_score=best.strategy_score,
        expected_outcome=decision_row.expected_outcome_json,
        risk_level=risk_level,
        confidence=confidence,
        reasoning=reasoning,
        causal_graph_version=causal_graph_version,
        agent_reviews=agent_reviews,
        alternatives=[_alt_summary(a) for a in alternatives],
        skipped_strategies=skipped,
    )


def get_decision(db: Session, business_id: str, decision_id: str) -> Decision:
    decision = db.get(Decision, decision_id)
    if decision is None or decision.business_id != business_id:
        raise NotFoundError(f"Decision {decision_id} not found.")
    return decision


def list_decisions(db: Session, business_id: str) -> list[Decision]:
    return db.query(Decision).filter(Decision.business_id == business_id).order_by(Decision.created_at.desc()).all()
