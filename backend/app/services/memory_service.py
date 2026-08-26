"""Business Memory — docs/PRD.md §29.

Stores goals, decisions and recorded outcomes as a queryable timeline
(BusinessMemory), and lets the Multi-Agent Decision Engine reference real
past outcomes when evaluating a new strategy — e.g. "your previous
marketing increase produced a smaller revenue improvement than the
simulation predicted." Every insight here is generated from an actual
recorded DecisionOutcome; if a business has never recorded an outcome for
a similar action, there is simply nothing to say (see AGENTS.md "no
fabrication" — this module never invents a plausible-sounding memory).
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.models.decision import Decision, DecisionOutcome
from app.models.memory import BusinessMemory
from app.models.strategy import Strategy

MAX_RELEVANT_INSIGHTS = 3


def log_memory(db: Session, business_id: str, memory_type: str, content: str, metadata: dict | None = None) -> BusinessMemory:
    entry = BusinessMemory(business_id=business_id, memory_type=memory_type, content=content, metadata_json=metadata or {})
    db.add(entry)
    return entry


def list_memory(db: Session, business_id: str, memory_type: str | None = None) -> list[BusinessMemory]:
    query = db.query(BusinessMemory).filter(BusinessMemory.business_id == business_id)
    if memory_type is not None:
        query = query.filter(BusinessMemory.memory_type == memory_type)
    return query.order_by(BusinessMemory.created_at.desc()).all()


def _score_outcome(expected: dict, actual: dict) -> tuple[bool | None, float | None]:
    """Documented method: compare the *change* actually observed against
    the change the simulation predicted (both relative to the same
    baseline), rather than the raw revenue numbers.

    goal_achievement_score:
    - 1.0  = actual change exactly matched the prediction
    - >1.0 = outperformed the prediction
    - 0..1 = same direction, smaller than predicted
    - <0   = moved in the opposite direction from what was predicted

    Returns (None, None) when there isn't enough overlap between what the
    decision predicted and what was actually reported to compare honestly
    (e.g. the simulation predicted no change at all).
    """
    expected_revenue = expected.get("expected_revenue")
    baseline_revenue = expected.get("baseline_revenue")
    actual_revenue = actual.get("revenue")
    if expected_revenue is None or baseline_revenue is None or actual_revenue is None:
        return None, None

    predicted_change = expected_revenue - baseline_revenue
    actual_change = actual_revenue - baseline_revenue
    if abs(predicted_change) < 1e-9:
        # The simulation predicted no change. If reality also showed no
        # change, the prediction was exactly accurate (score 1.0) — but no
        # goal gain was made. If reality *did* move, there's no predicted
        # magnitude to score the realised change against.
        if abs(actual_change) < 1e-9:
            return False, 1.0
        return None, None

    score = round(actual_change / predicted_change, 4)
    goal_achieved = actual_change > 0 if predicted_change > 0 else actual_change < 0
    return goal_achieved, score


def _comparison_phrase(score: float) -> str:
    if score >= 1.1:
        return "exceeded what the simulation predicted"
    if score >= 0.8:
        return "was close to what the simulation predicted"
    if score >= 0:
        return "produced a smaller revenue change than the simulation predicted"
    return "moved revenue in the opposite direction from what the simulation predicted"


def _summarize_outcome(strategy_name: str, expected: dict, actual: dict, score: float | None) -> str:
    expected_revenue = expected.get("expected_revenue")
    baseline_revenue = expected.get("baseline_revenue")
    actual_revenue = actual.get("revenue")
    if score is None or expected_revenue is None or baseline_revenue is None or actual_revenue is None:
        return f"Outcome recorded for '{strategy_name}'."

    predicted_change = expected_revenue - baseline_revenue
    actual_change = actual_revenue - baseline_revenue
    return (
        f"Outcome recorded for '{strategy_name}': {_comparison_phrase(score)} "
        f"(predicted revenue change {predicted_change:+,.0f}, actual {actual_change:+,.0f})."
    )


def record_outcome(
    db: Session, business_id: str, decision_id: str, actual_outcome: dict, recorded_at: datetime | None = None
) -> DecisionOutcome:
    decision = db.get(Decision, decision_id)
    if decision is None or decision.business_id != business_id:
        raise NotFoundError(f"Decision {decision_id} not found.")
    if not actual_outcome:
        raise ValidationFailedError("actual_outcome must include at least one observed value.")

    existing = db.query(DecisionOutcome).filter(DecisionOutcome.decision_id == decision_id).first()
    if existing is not None:
        raise ValidationFailedError(f"An outcome has already been recorded for decision {decision_id}.")

    strategy = db.get(Strategy, decision.selected_strategy_id)
    strategy_name = strategy.strategy_name if strategy is not None else "the selected strategy"

    goal_achieved, score = _score_outcome(decision.expected_outcome_json, actual_outcome)

    outcome = DecisionOutcome(
        decision_id=decision_id,
        actual_outcome_json=actual_outcome,
        goal_achieved=goal_achieved,
        goal_achievement_score=score,
        recorded_at=recorded_at or datetime.now(timezone.utc),
    )
    db.add(outcome)

    log_memory(
        db,
        business_id,
        "outcome",
        _summarize_outcome(strategy_name, decision.expected_outcome_json, actual_outcome, score),
        metadata={"decision_id": decision_id},
    )

    db.commit()
    db.refresh(outcome)

    # --- Research feedback loop (docs Phase 3 / Phase 5) --------------
    # Runs in its own transaction AFTER the outcome is safely persisted, so
    # a feedback failure can never lose the SME's recorded outcome. It also
    # never retrains a model and never claims causation from one datapoint.
    _run_feedback_loop(db, business_id, decision_id, outcome.id)
    return outcome


def _run_feedback_loop(db: Session, business_id: str, decision_id: str, outcome_id: str) -> None:
    from app.services import causal_feedback_service, digital_twin_evaluation_service

    try:
        decision = db.get(Decision, decision_id)
        outcome = db.get(DecisionOutcome, outcome_id)
        if decision is None or outcome is None:
            return
        digital_twin_evaluation_service.evaluate_decision_outcome(db, decision, outcome)
        causal_feedback_service.apply_outcome_feedback(db, business_id, decision, outcome)
        db.commit()
    except Exception:  # noqa: BLE001 - feedback is best-effort, never fatal
        db.rollback()


def get_outcome(db: Session, business_id: str, decision_id: str) -> DecisionOutcome:
    decision = db.get(Decision, decision_id)
    if decision is None or decision.business_id != business_id:
        raise NotFoundError(f"Decision {decision_id} not found.")
    outcome = db.query(DecisionOutcome).filter(DecisionOutcome.decision_id == decision_id).first()
    if outcome is None:
        raise NotFoundError(f"No outcome has been recorded for decision {decision_id} yet.")
    return outcome


def get_relevant_outcome_insights(
    db: Session, business_id: str, action_types: list[str], exclude_decision_id: str | None = None
) -> list[str]:
    """Real, recorded outcomes from this business's own past decisions that
    used at least one of the same action types — never a generic or
    templated claim about "similar businesses"."""
    wanted = set(action_types)
    decisions = (
        db.query(Decision)
        .filter(Decision.business_id == business_id)
        .order_by(Decision.created_at.desc())
        .all()
    )

    insights: list[str] = []
    for decision in decisions:
        if exclude_decision_id and decision.id == exclude_decision_id:
            continue
        strategy = db.get(Strategy, decision.selected_strategy_id)
        if strategy is None:
            continue
        strategy_action_types = {a["type"] for a in strategy.actions_json}
        if not (strategy_action_types & wanted):
            continue

        outcome = db.query(DecisionOutcome).filter(DecisionOutcome.decision_id == decision.id).first()
        if outcome is None or outcome.goal_achievement_score is None:
            continue

        expected_revenue = decision.expected_outcome_json.get("expected_revenue")
        baseline_revenue = decision.expected_outcome_json.get("baseline_revenue")
        actual_revenue = outcome.actual_outcome_json.get("revenue")
        if expected_revenue is None or baseline_revenue is None or actual_revenue is None:
            continue
        predicted_change = expected_revenue - baseline_revenue
        actual_change = actual_revenue - baseline_revenue
        verb = "increase" if predicted_change >= 0 else "decrease"

        insights.append(
            f"Your previous '{strategy.strategy_name}' {verb} {_comparison_phrase(float(outcome.goal_achievement_score))} "
            f"(predicted {predicted_change:+,.0f}, actual {actual_change:+,.0f})."
        )
        if len(insights) >= MAX_RELEVANT_INSIGHTS:
            break

    return insights
