"""Multi-Agent Decision Engine orchestration — docs/MULTI_AGENT_SPECIFICATION.md §3-§4:

    Goal
     -> goal-aware candidate strategies (strategy_generation_service)
     -> Digital Twin simulation per candidate (with causal context attached)
     -> Round 1: Business Analyst / Financial Advisor / Risk Manager (independent)
     -> Round 2: structured peer review / debate
     -> Strategy Optimizer: resolve conflicts, pick best, derive documented confidence
     -> Decision (persisted with a full reproducible trace)

Every number an agent sees already came from a real, tested analytical
component (app.analytics.digital_twin_service, itself the registered
forecasting model re-run with each strategy's actions). This module never
invents a strategy's outcome or a confidence value — see
docs/RESEARCH_TRACEABILITY.md and AGENTS.md.
"""
import hashlib
import json
from dataclasses import dataclass, field
from datetime import timedelta

import pandas as pd
from sqlalchemy.orm import Session

from app.agents import (
    business_analyst,
    financial_advisor,
    risk_manager,
    single_agent,
    strategy_optimizer,
)
from app.agents.base import AgentEvaluationResult, PeerReview
from app.agents.strategy_optimizer import ResolvedDecision
from app.analytics import (
    causal_context_service,
    digital_twin_service,
    explainability_service,
    forecast_service,
)
from app.analytics.causal_context_service import CausalContext
from app.analytics.digital_twin_service import Action, SimulationOutput
from app.analytics.explainability_service import Explanation
from app.core.errors import AppError, InsufficientDataError, NotFoundError
from app.models.agent import AgentEvaluation, AgentRun
from app.models.causal import CausalGraph
from app.models.decision import Decision
from app.models.goal import Goal
from app.models.ml_model import MLModel
from app.models.strategy import Strategy
from app.services import memory_service, strategy_generation_service
from app.services.llm_service import LLMService

LLM_PROMPT_VERSION = "decision-v2"

# Retained for the Research Console's Decision Architecture experiment
# (a deliberately fixed, goal-agnostic grid used only for controlled A/B/C/D
# comparison — the SME pipeline no longer uses it).
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
class PipelineOptions:
    """Component toggles for ablation studies (docs/PRD.md §14). Default =
    Full DecisionGPT. Every toggle runs the *real* pipeline with that
    component removed — never a fabricated delta."""

    use_causal_graph: bool = True
    use_multi_agent: bool = True  # False -> single blended agent, no debate
    use_memory: bool = True
    use_explainability: bool = True  # informational only; doesn't change the selected strategy

    def label(self) -> str:
        off = [
            name
            for name, on in (
                ("causal_graph", self.use_causal_graph),
                ("multi_agent", self.use_multi_agent),
                ("memory", self.use_memory),
                ("explainability", self.use_explainability),
            )
            if not on
        ]
        return "full" if not off else "without_" + "+".join(off)


@dataclass
class StrategyAnalysis:
    strategy_id: str
    strategy_name: str
    rationale: str
    actions: list[dict]
    simulation_id: str
    causal_context: CausalContext
    round1: dict[str, AgentEvaluationResult]
    reviews: list[PeerReview]
    resolved: ResolvedDecision
    output: SimulationOutput

    @property
    def business_analyst(self) -> AgentEvaluationResult | None:
        return self.round1.get("business_analyst")

    @property
    def financial_advisor(self) -> AgentEvaluationResult | None:
        return self.round1.get("financial_advisor")

    @property
    def risk_manager(self) -> AgentEvaluationResult | None:
        return self.round1.get("risk_manager")

    @property
    def strategy_score(self) -> float:
        return self.resolved.final_score

    @property
    def is_multi_agent(self) -> bool:
        return "single_agent" not in self.round1


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
    memory_insights: list[str] = field(default_factory=list)
    causal_context: dict = field(default_factory=dict)
    debate: dict = field(default_factory=dict)
    strategy_generation: dict = field(default_factory=dict)
    trace: dict = field(default_factory=dict)


def strategy_name_for_actions(actions: list[dict]) -> str:
    parts = []
    for a in actions:
        sign = "+" if a["value"] >= 0 else ""
        parts.append(f"{ACTION_LABELS[a['type']]} {sign}{a['value']:g}%")
    return " & ".join(parts)


def _state_version(state: dict) -> str:
    """Stable short hash of the business-state snapshot a decision was made
    against — lets a stored decision be checked for reproducibility."""
    blob = json.dumps(state, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


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
        "rationale": analysis.rationale,
        "actions": analysis.actions,
        "strategy_score": analysis.strategy_score,
        "confidence": analysis.resolved.confidence,
        "risk_level": RISK_LEVEL_MAP[analysis.output.risk_level],
        "expected_revenue": analysis.output.expected_revenue,
        "conflicts": analysis.resolved.conflicts,
    }


def _goal_projection(goal: Goal, output: SimulationOutput) -> dict:
    """How far the selected strategy is projected to move the goal's own
    primary KPI — surfaced so a no-op / negative recommendation is never
    presented as if it advanced the goal."""
    kpi = goal.primary_kpi
    if kpi == "profit" and output.expected_profit is not None and output.baseline_profit is not None:
        base, exp = output.baseline_profit, output.expected_profit
        basis = "profit"
    elif kpi in ("orders", "sales"):
        base, exp = output.baseline_units_sold, output.expected_units_sold
        basis = "units_sold"
    else:
        base, exp = output.baseline_revenue, output.expected_revenue
        basis = "revenue"
    delta = exp - base
    rel = (delta / base) if abs(base) > 1e-9 else 0.0
    return {
        "primary_kpi": kpi,
        "projected_on": basis,
        "baseline": round(base, 2),
        "projected": round(exp, 2),
        "delta": round(delta, 2),
        "relative_change": round(rel, 4),
        "improves_goal": delta > 1e-6,
    }


def _evaluation_json(result: AgentEvaluationResult, round_no: int) -> dict:
    return {
        "round": round_no,
        "score": result.score,
        "key_points": result.key_points,
        "risks": result.risks,
        "assumptions": result.assumptions,
    }


def _score_candidate(
    output: SimulationOutput, goal: Goal, ctx, options: PipelineOptions
) -> tuple[dict[str, AgentEvaluationResult], list[PeerReview], ResolvedDecision]:
    """Round 1 + round 2 + optimizer for a single simulated candidate,
    honouring the pipeline component toggles."""
    agent_ctx = ctx if (ctx is not None and getattr(ctx, "built", False) and options.use_causal_graph) else None
    causal_factor = (
        causal_context_service.evidence_confidence_factor(ctx)
        if (ctx is not None and options.use_causal_graph)
        else 1.0
    )

    if not options.use_multi_agent:
        sa = single_agent.evaluate(output)
        resolved = strategy_optimizer.resolve_single(sa, output, causal_evidence_factor=causal_factor)
        return {"single_agent": sa}, [], resolved

    ba = business_analyst.evaluate(output, goal, causal_context=agent_ctx)
    fa = financial_advisor.evaluate(output, goal, causal_context=agent_ctx)
    rm = risk_manager.evaluate(output, goal, causal_context=agent_ctx)
    round1 = {"business_analyst": ba, "financial_advisor": fa, "risk_manager": rm}
    reviews = [
        risk_manager.review(rm, {"business_analyst": ba, "financial_advisor": fa}, output),
        financial_advisor.review(fa, {"business_analyst": ba, "risk_manager": rm}, output),
        business_analyst.review(ba, {"financial_advisor": fa, "risk_manager": rm}, output),
    ]
    resolved = strategy_optimizer.resolve(round1, reviews, output, causal_evidence_factor=causal_factor)
    return round1, reviews, resolved


def analyze_goal(
    db: Session, business_id: str, goal_id: str, options: PipelineOptions | None = None
) -> DecisionResult:
    options = options or PipelineOptions()
    goal = db.get(Goal, goal_id)
    if goal is None or goal.business_id != business_id:
        raise NotFoundError(f"Goal {goal_id} not found for this business.")

    sufficient, reason = forecast_service.check_forecast_sufficiency(db, business_id)
    if not sufficient:
        raise InsufficientDataError(reason or "Not enough sales history to analyze this goal.")

    gen = strategy_generation_service.generate_candidates(db, business_id, goal)
    if not gen.candidates:
        raise InsufficientDataError(
            "No candidate strategy could be generated for this goal with the data on file.",
            details={"excluded": gen.excluded, "notes": gen.notes, "objective": gen.objective},
        )

    business_state = digital_twin_service.get_current_state(db, business_id)
    state_version = _state_version(business_state)

    analyses: list[StrategyAnalysis] = []
    skipped: list[str] = []
    candidate_strategy_ids: list[str] = []
    simulation_ids: list[str] = []
    model_versions: dict[str, str] = {}

    for cand in gen.candidates:
        actions = [Action(type=a["type"], value=a["value"]) for a in cand.actions]

        strategy_row = Strategy(
            business_id=business_id,
            goal_id=goal_id,
            strategy_name=cand.name,
            description=cand.rationale,
            actions_json=cand.actions,
        )
        db.add(strategy_row)
        db.flush()
        candidate_strategy_ids.append(strategy_row.id)

        if options.use_causal_graph:
            ctx = causal_context_service.get_causal_context(
                db, business_id, [a["type"] for a in cand.actions], extra_targets=cand.targets
            )
        else:
            ctx = causal_context_service.disabled_context()

        try:
            simulation = digital_twin_service.simulate_strategy(
                db,
                business_id,
                actions,
                goal_id=goal_id,
                strategy_id=strategy_row.id,
                causal_context=(ctx if options.use_causal_graph else None),
            )
        except AppError as exc:
            skipped.append(f"{cand.name}: {exc.message}")
            continue

        simulation_ids.append(simulation.id)
        model_versions["forecasting"] = f"{simulation.output.model_name}:{simulation.output.model_version}"

        round1, reviews, resolved = _score_candidate(simulation.output, goal, ctx, options)

        # Persist per-strategy agent evaluations (round 1 + round 2).
        for r in round1.values():
            db.add(
                AgentEvaluation(
                    strategy_id=strategy_row.id,
                    agent_name=r.agent,
                    evaluation_json=_evaluation_json(r, 1),
                    score=r.score,
                    prompt_version=LLM_PROMPT_VERSION,
                )
            )
        for rv in reviews:
            db.add(
                AgentEvaluation(
                    strategy_id=strategy_row.id,
                    agent_name=rv.agent,
                    evaluation_json=rv.to_dict(),
                    score=rv.adjusted_score,
                    prompt_version=LLM_PROMPT_VERSION,
                )
            )

        analyses.append(
            StrategyAnalysis(
                strategy_id=strategy_row.id,
                strategy_name=cand.name,
                rationale=cand.rationale,
                actions=cand.actions,
                simulation_id=simulation.id,
                causal_context=ctx,
                round1=round1,
                reviews=reviews,
                resolved=resolved,
                output=simulation.output,
            )
        )

    if not analyses:
        db.rollback()
        raise InsufficientDataError(
            "No candidate strategy could be simulated for this business right now.",
            details={"skipped": skipped, "excluded": gen.excluded},
        )

    analyses.sort(key=lambda a: a.resolved.final_score, reverse=True)
    best = analyses[0]
    alternatives = analyses[1:]

    risk_level = RISK_LEVEL_MAP[best.output.risk_level]
    confidence = best.resolved.confidence  # documented — see ResolvedDecision.confidence_basis

    llm = LLMService()
    agent_reviews = {
        agent.agent: llm.evaluate_agent(
            agent.agent,
            {"key_points": agent.key_points, "risks": agent.risks, "assumptions": agent.assumptions},
        )
        for agent in best.round1.values()
    }
    base_reasoning = llm.generate_strategy_explanation(
        {
            "strategy_name": best.strategy_name,
            "expected_revenue": best.output.expected_revenue,
            "risk_level": risk_level,
        }
    )
    reasoning = f"{base_reasoning} {best.rationale} {best.resolved.resolution_rationale}"

    goal_projection = _goal_projection(goal, best.output)
    if not goal_projection["improves_goal"]:
        reasoning += (
            f" Note: no strategy in the supported action space is projected to improve "
            f"{goal.objective.replace('_', ' ')} for this business given its current data — "
            "the option shown is the least-harmful of those evaluated."
        )

    causal_graph_version = best.causal_context.graph_version or _latest_causal_graph_version(db, business_id)

    memory_insights = (
        memory_service.get_relevant_outcome_insights(
            db, business_id, action_types=[a["type"] for a in best.actions]
        )
        if options.use_memory
        else []
    )

    uncertainty = {
        "risk_level": risk_level,
        "risk_score": best.output.risk_score,
        "revenue_lower_bound": best.output.revenue_lower_bound,
        "revenue_upper_bound": best.output.revenue_upper_bound,
        "confidence": confidence,
        "confidence_basis": best.resolved.confidence_basis,
    }
    debate = {
        "rounds": 2 if best.is_multi_agent else 1,
        "multi_agent": best.is_multi_agent,
        "selected_strategy_id": best.strategy_id,
        "round1": {a: _evaluation_json(r, 1) for a, r in best.round1.items()},
        "round2_reviews": [rv.to_dict() for rv in best.reviews],
        "resolution": best.resolved.to_dict(),
        "all_candidates": [
            {
                "strategy_id": a.strategy_id,
                "strategy_name": a.strategy_name,
                "final_score": a.resolved.final_score,
                "confidence": a.resolved.confidence,
                "conflicts": a.resolved.conflicts,
            }
            for a in analyses
        ],
    }
    strategy_generation = {
        "objective": gen.objective,
        "candidate_count": len(gen.candidates),
        "excluded": gen.excluded,
        "constraints_applied": gen.constraints_applied,
        "notes": gen.notes,
        "goal_projection": goal_projection,
    }
    pipeline_options = {
        "use_causal_graph": options.use_causal_graph,
        "use_multi_agent": options.use_multi_agent,
        "use_memory": options.use_memory,
        "use_explainability": options.use_explainability,
        "label": options.label(),
    }

    decision_row = Decision(
        business_id=business_id,
        goal_id=goal_id,
        selected_strategy_id=best.strategy_id,
        expected_outcome_json=digital_twin_service.output_to_dict(best.output),
        risk_level=risk_level,
        confidence=confidence,
        reasoning=reasoning,
        causal_graph_version=causal_graph_version,
        business_state_version=state_version,
        business_state_json=business_state,
        candidate_strategy_ids_json=candidate_strategy_ids,
        simulation_ids_json=simulation_ids,
        model_versions_json=model_versions,
        assumptions_json=best.output.assumptions,
        uncertainty_json=uncertainty,
        causal_context_json=best.causal_context.to_dict(),
        debate_json={**debate, "pipeline_options": pipeline_options},
        strategy_generation_json=strategy_generation,
        prompt_version=LLM_PROMPT_VERSION,
    )
    db.add(decision_row)
    db.flush()

    # AgentRun rows for the selected strategy — round 1, round 2, optimizer.
    agent_run_ids: list[str] = []
    for r in best.round1.values():
        run = AgentRun(
            business_id=business_id,
            decision_id=decision_row.id,
            agent_name=r.agent,
            prompt_version=LLM_PROMPT_VERSION,
            input_json={"round": 1, "strategy_id": best.strategy_id, "actions": best.actions},
            output_json=_evaluation_json(r, 1),
        )
        db.add(run)
        db.flush()
        agent_run_ids.append(run.id)
    for rv in best.reviews:
        run = AgentRun(
            business_id=business_id,
            decision_id=decision_row.id,
            agent_name=rv.agent,
            prompt_version=LLM_PROMPT_VERSION,
            input_json={"round": 2, "strategy_id": best.strategy_id},
            output_json=rv.to_dict(),
        )
        db.add(run)
        db.flush()
        agent_run_ids.append(run.id)
    opt_run = AgentRun(
        business_id=business_id,
        decision_id=decision_row.id,
        agent_name="strategy_optimizer",
        prompt_version=LLM_PROMPT_VERSION,
        input_json={"strategy_id": best.strategy_id, "candidates_considered": len(analyses)},
        output_json=best.resolved.to_dict(),
    )
    db.add(opt_run)
    db.flush()
    agent_run_ids.append(opt_run.id)
    decision_row.agent_run_ids_json = agent_run_ids

    if options.use_memory:
        memory_service.log_memory(
            db,
            business_id,
            "decision",
            f"Decision made: selected '{best.strategy_name}' (score {best.resolved.final_score}, "
            f"confidence {confidence}, risk {risk_level}).",
            metadata={"decision_id": decision_row.id, "goal_id": goal_id},
        )

    db.commit()
    db.refresh(decision_row)

    return DecisionResult(
        id=decision_row.id,
        business_id=business_id,
        goal_id=goal_id,
        selected_strategy_id=best.strategy_id,
        selected_strategy_name=best.strategy_name,
        selected_strategy_score=best.resolved.final_score,
        expected_outcome=decision_row.expected_outcome_json,
        risk_level=risk_level,
        confidence=confidence,
        reasoning=reasoning,
        memory_insights=memory_insights,
        causal_graph_version=causal_graph_version,
        agent_reviews=agent_reviews,
        alternatives=[_alt_summary(a) for a in alternatives],
        skipped_strategies=skipped,
        causal_context=best.causal_context.to_dict(),
        debate=debate,
        strategy_generation=strategy_generation,
        trace={
            "business_state_version": state_version,
            "candidate_strategy_ids": candidate_strategy_ids,
            "simulation_ids": simulation_ids,
            "agent_run_ids": agent_run_ids,
            "model_versions": model_versions,
            "prompt_version": LLM_PROMPT_VERSION,
        },
    )


def get_decision(db: Session, business_id: str, decision_id: str) -> Decision:
    decision = db.get(Decision, decision_id)
    if decision is None or decision.business_id != business_id:
        raise NotFoundError(f"Decision {decision_id} not found.")
    return decision


def list_decisions(db: Session, business_id: str) -> list[Decision]:
    return (
        db.query(Decision)
        .filter(Decision.business_id == business_id)
        .order_by(Decision.created_at.desc())
        .all()
    )


def get_decision_trace(db: Session, business_id: str, decision_id: str) -> dict:
    """The complete, inspectable trace for one decision
    (docs/RESEARCH_TRACEABILITY.md "Required Metadata")."""
    decision = get_decision(db, business_id, decision_id)
    strategy = db.get(Strategy, decision.selected_strategy_id) if decision.selected_strategy_id else None
    agent_runs = db.query(AgentRun).filter(AgentRun.decision_id == decision_id).all()

    return {
        "decision_id": decision.id,
        "business_id": decision.business_id,
        "goal_id": decision.goal_id,
        "created_at": decision.created_at,
        "business_state_version": decision.business_state_version,
        "business_state": decision.business_state_json,
        "selected_strategy": {
            "id": strategy.id if strategy else None,
            "name": strategy.strategy_name if strategy else None,
            "actions": strategy.actions_json if strategy else None,
            "rationale": strategy.description if strategy else None,
        },
        "candidate_strategy_ids": decision.candidate_strategy_ids_json or [],
        "simulation_ids": decision.simulation_ids_json or [],
        "agent_run_ids": decision.agent_run_ids_json or [],
        "agent_runs": [
            {
                "id": r.id,
                "agent_name": r.agent_name,
                "prompt_version": r.prompt_version,
                "input": r.input_json,
                "output": r.output_json,
            }
            for r in agent_runs
        ],
        "model_versions": decision.model_versions_json or {},
        "causal_graph_version": decision.causal_graph_version,
        "causal_context": decision.causal_context_json or {},
        "debate": decision.debate_json or {},
        "strategy_generation": decision.strategy_generation_json or {},
        "assumptions": decision.assumptions_json or [],
        "uncertainty": decision.uncertainty_json or {},
        "expected_outcome": decision.expected_outcome_json,
        "reasoning": decision.reasoning,
        "confidence": float(decision.confidence) if decision.confidence is not None else None,
        "prompt_version": decision.prompt_version,
        "reproducible": _check_reproducible(db, decision),
    }


def _check_reproducible(db: Session, decision: Decision) -> dict:
    """A stored decision is 'reproducible' if the model version it used is
    still registered and its recorded business-state hash still matches a
    fresh snapshot of the same business."""
    reasons: list[str] = []
    outcome = decision.expected_outcome_json or {}
    model_row = (
        db.query(MLModel)
        .filter(
            MLModel.model_name == outcome.get("model_name"),
            MLModel.version == outcome.get("model_version"),
        )
        .first()
    )
    if model_row is None:
        reasons.append(
            f"Model {outcome.get('model_name')} v{outcome.get('model_version')} is no longer registered."
        )
    try:
        fresh_state = digital_twin_service.get_current_state(db, decision.business_id)
        if decision.business_state_version and _state_version(fresh_state) != decision.business_state_version:
            reasons.append("Business data has changed since this decision was made.")
    except AppError:
        reasons.append("Business state can no longer be computed.")
    return {"ok": not reasons, "reasons": reasons}


@dataclass
class DecisionExplanation:
    decision_id: str
    explanation: Explanation
    reasoning: str
    agent_reviews: dict[str, str]
    counterfactual: dict
    uncertainty: dict
    assumptions: list[str]
    causal_context: dict = field(default_factory=dict)


def explain_decision(db: Session, business_id: str, decision_id: str) -> DecisionExplanation:
    """docs/PRD.md §28/§30 — recomputed on demand from the decision's stored
    strategy + model reference, against this business's *current* data."""
    decision = get_decision(db, business_id, decision_id)

    strategy = db.get(Strategy, decision.selected_strategy_id)
    if strategy is None or strategy.business_id != business_id:
        raise NotFoundError(f"Strategy for decision {decision_id} not found.")

    outcome = decision.expected_outcome_json
    model_row = (
        db.query(MLModel)
        .filter(MLModel.model_name == outcome.get("model_name"), MLModel.version == outcome.get("model_version"))
        .first()
    )
    if model_row is None:
        raise NotFoundError(
            f"The model used for this decision ({outcome.get('model_name')} v{outcome.get('model_version')}) "
            "is no longer registered."
        )

    baseline_row = scenario_row = None
    history = forecast_service.build_daily_series(db, business_id)
    if not history.empty:
        history = history.copy()
        history["date"] = pd.to_datetime(history["date"])
        units_series = list(history["units_sold"])
        forecast_date = history["date"].iloc[-1] + timedelta(days=1)

        actions = [Action(type=a["type"], value=a["value"]) for a in strategy.actions_json]
        baseline_price, baseline_marketing_spend, scenario_price, scenario_marketing_spend, _ = (
            digital_twin_service.compute_scenario_inputs(history, actions)
        )
        baseline_row = forecast_service.build_feature_row(
            units_series, forecast_date, baseline_price, baseline_marketing_spend
        )
        scenario_row = forecast_service.build_feature_row(
            units_series, forecast_date, scenario_price, scenario_marketing_spend
        )

    model = forecast_service.load_model(model_row)
    explanation = explainability_service.build_explanation(model_row, model, baseline_row, scenario_row)

    llm = LLMService()
    agent_runs = db.query(AgentRun).filter(AgentRun.decision_id == decision_id).all()
    agent_reviews = {
        run.agent_name: llm.evaluate_agent(run.agent_name, run.output_json)
        for run in agent_runs
        if run.agent_name != "strategy_optimizer"
    }

    counterfactual = {
        "baseline_units_sold": outcome.get("baseline_units_sold"),
        "expected_units_sold": outcome.get("expected_units_sold"),
        "baseline_revenue": outcome.get("baseline_revenue"),
        "expected_revenue": outcome.get("expected_revenue"),
        "baseline_profit": outcome.get("baseline_profit"),
        "expected_profit": outcome.get("expected_profit"),
    }
    uncertainty = decision.uncertainty_json or {
        "risk_level": decision.risk_level,
        "risk_score": float(decision.confidence) if decision.confidence is not None else None,
        "revenue_lower_bound": outcome.get("revenue_lower_bound"),
        "revenue_upper_bound": outcome.get("revenue_upper_bound"),
    }

    return DecisionExplanation(
        decision_id=decision_id,
        explanation=explanation,
        reasoning=decision.reasoning or "",
        agent_reviews=agent_reviews,
        counterfactual=counterfactual,
        uncertainty=uncertainty,
        assumptions=(decision.assumptions_json or outcome.get("assumptions", [])),
        causal_context=decision.causal_context_json or {},
    )
