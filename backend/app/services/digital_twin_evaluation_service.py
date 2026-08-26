"""Research Console — Digital Twin Evaluation (docs/PRD.md §15, docs Phase 2/3).

The feedback loop: every time an SME records a real DecisionOutcome,
``evaluate_decision_outcome`` compares what the Digital Twin predicted for
the chosen strategy against what actually happened, for every metric the
decision *and* the outcome both support (revenue always; profit / units
when available), and persists a ``PredictionEvaluation`` row with full
traceability (decision / outcome / simulation / graph-version /
model-version references).

Nothing here fabricates a result. If a business has recorded no matched
outcomes, the summary says so explicitly. One recorded outcome is treated
as a single observational data point — it never "proves" a model or a
causal edge (that conservatism lives in ``causal_feedback_service``).
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.decision import Decision, DecisionOutcome
from app.models.digital_twin import DigitalTwinSimulation
from app.models.evaluation import PREDICTION_EVAL_METHOD, PredictionEvaluation
from app.models.strategy import Strategy

# actual_outcome_json keys we understand, mapped to the predicted-side key
# in expected_outcome_json (baseline_* / expected_*).
_METRIC_KEYS = {
    "revenue": ("baseline_revenue", "expected_revenue"),
    "profit": ("baseline_profit", "expected_profit"),
    "units": ("baseline_units_sold", "expected_units_sold"),
    "orders": ("baseline_units_sold", "expected_units_sold"),
    "sales": ("baseline_units_sold", "expected_units_sold"),
}


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _metric_eval(baseline: float | None, predicted: float | None, actual: float | None) -> dict | None:
    if baseline is None or predicted is None or actual is None:
        return None
    predicted_change = predicted - baseline
    actual_change = actual - baseline
    error = actual_change - predicted_change
    # MAPE is only defined where the actual change is non-zero.
    pct = abs(error) / abs(actual_change) * 100 if abs(actual_change) > 1e-9 else None
    return {
        "predicted_baseline": round(baseline, 2),
        "predicted": round(predicted, 2),
        "actual": round(actual, 2),
        "predicted_change": round(predicted_change, 2),
        "actual_change": round(actual_change, 2),
        "error": round(error, 2),
        "abs_pct_error": round(pct, 4) if pct is not None else None,
    }


def _selected_simulation(db: Session, decision: Decision) -> DigitalTwinSimulation | None:
    if not decision.selected_strategy_id:
        return None
    return (
        db.query(DigitalTwinSimulation)
        .filter(
            DigitalTwinSimulation.business_id == decision.business_id,
            DigitalTwinSimulation.strategy_id == decision.selected_strategy_id,
        )
        .order_by(DigitalTwinSimulation.created_at.desc())
        .first()
    )


def evaluate_decision_outcome(
    db: Session, decision: Decision, outcome: DecisionOutcome
) -> PredictionEvaluation:
    """Create (or refresh) the PredictionEvaluation for one recorded
    outcome. Idempotent on outcome_id — safe to call from the feedback loop
    and from backfill. Adds to the session; the caller commits."""
    existing = (
        db.query(PredictionEvaluation)
        .filter(PredictionEvaluation.outcome_id == outcome.id)
        .first()
    )

    expected = decision.expected_outcome_json or {}
    actual = outcome.actual_outcome_json or {}
    strategy = db.get(Strategy, decision.selected_strategy_id) if decision.selected_strategy_id else None
    simulation = _selected_simulation(db, decision)

    metrics: dict = {}
    seen_units = False
    for actual_key, value in actual.items():
        if actual_key not in _METRIC_KEYS:
            continue
        base_key, pred_key = _METRIC_KEYS[actual_key]
        canonical = "units" if actual_key in ("units", "orders", "sales") else actual_key
        if canonical == "units" and seen_units:
            continue
        result = _metric_eval(_num(expected.get(base_key)), _num(expected.get(pred_key)), _num(value))
        if result is not None:
            metrics[canonical] = result
            if canonical == "units":
                seen_units = True

    revenue = metrics.get("revenue", {})
    model_versions = decision.model_versions_json or {}
    if not model_versions and expected.get("model_name"):
        model_versions = {"forecasting": f"{expected.get('model_name')}:{expected.get('model_version')}"}

    fields = dict(
        business_id=decision.business_id,
        decision_id=decision.id,
        outcome_id=outcome.id,
        simulation_id=simulation.id if simulation else None,
        strategy_id=decision.selected_strategy_id,
        strategy_name=strategy.strategy_name if strategy else None,
        method=PREDICTION_EVAL_METHOD,
        causal_graph_version=decision.causal_graph_version,
        model_versions_json=model_versions,
        dataset_version=(simulation.model_version if simulation else None),
        predicted_revenue_change=revenue.get("predicted_change"),
        actual_revenue_change=revenue.get("actual_change"),
        revenue_error=revenue.get("error"),
        revenue_abs_pct_error=revenue.get("abs_pct_error"),
        metrics_json=metrics,
        recorded_at=outcome.recorded_at or datetime.now(timezone.utc),
    )

    if existing is not None:
        for k, v in fields.items():
            setattr(existing, k, v)
        return existing

    row = PredictionEvaluation(**fields)
    db.add(row)
    return row


def backfill(db: Session) -> int:
    """Compute a PredictionEvaluation for every recorded outcome that
    doesn't have one yet. Returns the number created/updated."""
    evaluated_outcome_ids = {
        oid for (oid,) in db.query(PredictionEvaluation.outcome_id).all()
    }
    outcomes = db.query(DecisionOutcome).all()
    n = 0
    for outcome in outcomes:
        decision = db.get(Decision, outcome.decision_id)
        if decision is None:
            continue
        if outcome.id in evaluated_outcome_ids:
            continue
        evaluate_decision_outcome(db, decision, outcome)
        n += 1
    if n:
        db.commit()
    return n


# --- Reporting ---------------------------------------------------------


@dataclass
class StrategyEvaluationRow:
    decision_id: str
    strategy_name: str
    predicted_change: float | None
    actual_change: float | None
    error: float | None
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
    """Experiment-dispatch entry point (experiment_service). Ensures every
    outcome has a persisted evaluation, then aggregates the revenue-change
    errors."""
    backfill(db)
    evals = (
        db.query(PredictionEvaluation)
        .filter(PredictionEvaluation.revenue_error.isnot(None))
        .order_by(PredictionEvaluation.recorded_at)
        .all()
    )
    rows = [
        StrategyEvaluationRow(
            decision_id=e.decision_id,
            strategy_name=e.strategy_name or "unknown",
            predicted_change=_num(e.predicted_revenue_change),
            actual_change=_num(e.actual_revenue_change),
            error=_num(e.revenue_error),
            percentage_error=_num(e.revenue_abs_pct_error),
        )
        for e in evals
    ]
    if not rows:
        return DigitalTwinEvaluationResult(
            sample_size=0, mae=None, rmse=None, mean_percentage_error=None, rows=[],
            note="No businesses have recorded a matched real outcome yet — there is nothing to "
            "evaluate. This is an honest empty result, not a synthetic substitute.",
        )
    errors = [r.error for r in rows if r.error is not None]
    mae = sum(abs(e) for e in errors) / len(errors)
    rmse = (sum(e**2 for e in errors) / len(errors)) ** 0.5
    pcts = [r.percentage_error for r in rows if r.percentage_error is not None]
    mape = sum(pcts) / len(pcts) if pcts else None
    return DigitalTwinEvaluationResult(
        sample_size=len(rows),
        mae=round(mae, 2),
        rmse=round(rmse, 2),
        mean_percentage_error=round(mape, 2) if mape is not None else None,
        rows=rows,
        note=f"Computed from {len(rows)} real recorded outcome(s) across all businesses.",
    )


def _agg(errors: list[float]) -> dict:
    if not errors:
        return {"mae": None, "rmse": None, "sample_size": 0}
    return {
        "mae": round(sum(abs(e) for e in errors) / len(errors), 2),
        "rmse": round((sum(e**2 for e in errors) / len(errors)) ** 0.5, 2),
        "sample_size": len(errors),
    }


def get_evaluation_report(db: Session) -> dict:
    """Everything the Digital Twin Evaluation page needs, all from stored
    rows."""
    backfill(db)
    evals = db.query(PredictionEvaluation).order_by(PredictionEvaluation.recorded_at).all()

    total_decisions = db.query(Decision).count()
    total_outcomes = db.query(DecisionOutcome).count()
    matched = [e for e in evals if e.revenue_error is not None]

    rows = []
    for e in evals:
        rev = e.metrics_json.get("revenue", {})
        rows.append(
            {
                "evaluation_id": e.id,
                "decision_id": e.decision_id,
                "outcome_id": e.outcome_id,
                "simulation_id": e.simulation_id,
                "strategy_name": e.strategy_name,
                "predicted_baseline": rev.get("predicted_baseline"),
                "predicted": rev.get("predicted"),
                "actual": rev.get("actual"),
                "predicted_change": rev.get("predicted_change"),
                "actual_change": rev.get("actual_change"),
                "error": rev.get("error"),
                "abs_pct_error": rev.get("abs_pct_error"),
                "metrics": e.metrics_json,
                "causal_graph_version": e.causal_graph_version,
                "model_versions": e.model_versions_json,
                "recorded_at": e.recorded_at.isoformat() if e.recorded_at else None,
            }
        )

    revenue_errors = [_num(e.revenue_error) for e in matched if _num(e.revenue_error) is not None]
    revenue_pcts = [
        _num(e.revenue_abs_pct_error) for e in matched if _num(e.revenue_abs_pct_error) is not None
    ]
    profit_errors = [
        m["profit"]["error"]
        for m in (e.metrics_json for e in evals)
        if isinstance(m.get("profit"), dict) and m["profit"].get("error") is not None
    ]

    metrics = {
        "revenue": {
            **_agg(revenue_errors),
            "mape": round(sum(revenue_pcts) / len(revenue_pcts), 2) if revenue_pcts else None,
        },
        "profit": _agg(profit_errors) if profit_errors else {"mae": None, "rmse": None, "sample_size": 0},
    }

    # Charts (only real points).
    predicted_vs_actual = [
        {
            "decision_id": e.decision_id,
            "predicted": e.metrics_json.get("revenue", {}).get("predicted_change"),
            "actual": e.metrics_json.get("revenue", {}).get("actual_change"),
        }
        for e in matched
    ]
    error_over_time = [
        {"recorded_at": e.recorded_at.isoformat() if e.recorded_at else None, "error": _num(e.revenue_error)}
        for e in matched
    ]
    error_distribution = _histogram(revenue_errors)

    empty_state = None
    if not matched:
        empty_state = (
            "No matched predicted and actual outcomes are available yet. An SME must record an actual "
            "decision outcome (Decision History → Record actual outcome) before the Digital Twin's "
            "predictions can be evaluated."
        )

    return {
        "summary": {
            "evaluated_predictions": len(matched),
            "outcomes_recorded": total_outcomes,
            "decisions_awaiting_outcome": max(0, total_decisions - total_outcomes),
            "revenue_mae": metrics["revenue"]["mae"],
            "revenue_mape": metrics["revenue"]["mape"],
        },
        "metrics": metrics,
        "rows": rows,
        "charts": {
            "predicted_vs_actual": predicted_vs_actual,
            "error_over_time": error_over_time,
            "error_distribution": error_distribution,
        },
        "method": PREDICTION_EVAL_METHOD,
        "empty_state": empty_state,
    }


def _histogram(values: list[float], bins: int = 7) -> list[dict]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if abs(hi - lo) < 1e-9:
        return [{"range": f"{lo:.0f}", "count": len(values)}]
    width = (hi - lo) / bins
    buckets = [0] * bins
    for v in values:
        idx = min(bins - 1, int((v - lo) / width))
        buckets[idx] += 1
    return [
        {"range": f"{lo + i * width:.0f}…{lo + (i + 1) * width:.0f}", "count": c}
        for i, c in enumerate(buckets)
    ]
