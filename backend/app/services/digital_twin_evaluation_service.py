"""Research Console — Digital Twin Evaluation (docs/PRD.md §15).

Compares every Digital Twin simulation's predicted revenue change against
the *real, recorded* DecisionOutcome for that decision, across all
businesses (this is the one research view that legitimately reads
business-linked data — it's gated behind the research console token, an
admin-only surface, and reports only aggregate error metrics, never any
single business's numbers, so no business-identifying data leaves this
module). If no business has recorded a real outcome yet, this says so
explicitly rather than inventing or substituting synthetic numbers
(docs/PRD.md §15 "never pretend synthetic data is real business data" —
the corollary is also true: never pretend there's real data when there
isn't).
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.decision import Decision, DecisionOutcome
from app.models.strategy import Strategy


@dataclass
class StrategyEvaluationRow:
    decision_id: str
    strategy_name: str
    predicted_change: float
    actual_change: float
    error: float
    percentage_error: float | None


@dataclass
class DigitalTwinEvaluationResult:
    sample_size: int
    mae: float | None
    rmse: float | None
    mean_percentage_error: float | None
    rows: list[StrategyEvaluationRow]
    label: str = "REAL_RECORDED_OUTCOMES"
    note: str = ""


def run_digital_twin_evaluation(db: Session) -> DigitalTwinEvaluationResult:
    outcomes = db.query(DecisionOutcome).all()
    rows: list[StrategyEvaluationRow] = []

    for outcome in outcomes:
        decision = db.get(Decision, outcome.decision_id)
        if decision is None:
            continue
        expected = decision.expected_outcome_json
        expected_revenue = expected.get("expected_revenue")
        baseline_revenue = expected.get("baseline_revenue")
        actual_revenue = outcome.actual_outcome_json.get("revenue")
        if expected_revenue is None or baseline_revenue is None or actual_revenue is None:
            continue

        strategy = db.get(Strategy, decision.selected_strategy_id)
        predicted_change = expected_revenue - baseline_revenue
        actual_change = actual_revenue - baseline_revenue
        error = actual_change - predicted_change
        pct_error = abs(error) / abs(predicted_change) * 100 if abs(predicted_change) > 1e-9 else None

        rows.append(
            StrategyEvaluationRow(
                decision_id=decision.id,
                strategy_name=strategy.strategy_name if strategy else "unknown",
                predicted_change=round(predicted_change, 2),
                actual_change=round(actual_change, 2),
                error=round(error, 2),
                percentage_error=round(pct_error, 2) if pct_error is not None else None,
            )
        )

    if not rows:
        return DigitalTwinEvaluationResult(
            sample_size=0,
            mae=None,
            rmse=None,
            mean_percentage_error=None,
            rows=[],
            note="No businesses have recorded a real outcome yet — there is nothing to evaluate. This is not "
            "a synthetic substitute; it's an honest empty result.",
        )

    errors = [r.error for r in rows]
    mae = sum(abs(e) for e in errors) / len(errors)
    rmse = (sum(e**2 for e in errors) / len(errors)) ** 0.5
    pct_errors = [r.percentage_error for r in rows if r.percentage_error is not None]
    mean_pct_error = sum(pct_errors) / len(pct_errors) if pct_errors else None

    return DigitalTwinEvaluationResult(
        sample_size=len(rows),
        mae=round(mae, 2),
        rmse=round(rmse, 2),
        mean_percentage_error=round(mean_pct_error, 2) if mean_pct_error is not None else None,
        rows=rows,
        note=f"Computed from {len(rows)} real recorded outcome(s) across all businesses.",
    )
