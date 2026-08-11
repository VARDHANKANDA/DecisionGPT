"""Goal Planner — turns a natural-language objective into a validated
structured Goal (docs/GOAL_PLANNER_SPECIFICATION.md).

The LLM (via LLMService) only ever parses the sentence's *structure*
(objective/target/horizon). Whether that goal is actually achievable given
the business's real data is decided here, against real KPI/data-sufficiency
checks — the LLM never gets to assert "yes, you have enough data."
"""
from sqlalchemy.orm import Session

from app.analytics import churn_service, kpi_service
from app.core.errors import ValidationFailedError
from app.models.goal import Goal
from app.models.inventory import InventoryRecord
from app.services.llm_service import LLMService, ParsedGoal

SUPPORTED_OBJECTIVES = {
    "increase_revenue",
    "increase_profit",
    "increase_sales",
    "reduce_churn",
    "improve_marketing_roi",
    "reduce_inventory_risk",
}

MIN_TARGET_PERCENT = 1
MAX_TARGET_PERCENT = 500


def _check_kpi_available(db: Session, business_id: str, primary_kpi: str) -> tuple[bool, str | None]:
    if primary_kpi == "churn_rate":
        return churn_service.check_churn_sufficiency(db, business_id)

    if primary_kpi == "inventory_risk":
        has_inventory = db.query(InventoryRecord).filter(InventoryRecord.business_id == business_id).first()
        if not has_inventory:
            return False, "No inventory records on file — upload inventory data to set this goal."
        return True, None

    kpis = kpi_service.compute_kpis(db, business_id)
    if primary_kpi == "revenue":
        return (kpis.revenue > 0, None if kpis.revenue > 0 else "No revenue history on file yet.")
    if primary_kpi == "profit":
        return (kpis.profit is not None, None if kpis.profit is not None else "Profit is unavailable — no products have a unit_cost on file.")
    if primary_kpi == "orders":
        return (kpis.orders > 0, None if kpis.orders > 0 else "No sales history on file yet.")
    if primary_kpi == "marketing_roi":
        return (
            kpis.marketing_roi is not None,
            None if kpis.marketing_roi is not None else "Marketing ROI is unavailable — no campaigns have attributed_revenue on file.",
        )
    return False, f"Unknown KPI '{primary_kpi}'."


def parse_and_validate_goal(db: Session, business_id: str, source_text: str) -> ParsedGoal:
    parsed = LLMService().parse_goal(source_text)

    if parsed.objective is None or parsed.objective not in SUPPORTED_OBJECTIVES:
        raise ValidationFailedError(
            "Could not identify a supported goal from that text.",
            details={"supported_objectives": sorted(SUPPORTED_OBJECTIVES), "parse_warnings": parsed.parse_warnings},
        )
    if parsed.target_value is None or parsed.target_unit is None:
        raise ValidationFailedError(
            "No measurable target found (e.g. 'increase profit by 15%').",
            details={"parse_warnings": parsed.parse_warnings},
        )
    if parsed.target_unit == "percent" and not (MIN_TARGET_PERCENT <= parsed.target_value <= MAX_TARGET_PERCENT):
        raise ValidationFailedError(
            f"Target of {parsed.target_value}% is outside the supported range "
            f"({MIN_TARGET_PERCENT}-{MAX_TARGET_PERCENT}%)."
        )

    available, reason = _check_kpi_available(db, business_id, parsed.primary_kpi)
    if not available:
        raise ValidationFailedError(
            f"This goal needs '{parsed.primary_kpi}', which isn't available yet: {reason}"
        )

    return parsed


def create_goal(db: Session, business_id: str, source_text: str) -> Goal:
    parsed = parse_and_validate_goal(db, business_id, source_text)
    goal = Goal(
        business_id=business_id,
        objective=parsed.objective,
        target_value=parsed.target_value,
        target_unit=parsed.target_unit,
        primary_kpi=parsed.primary_kpi,
        time_horizon=parsed.time_horizon_months,
        constraints_json=parsed.constraints,
        status="active",
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def list_goals(db: Session, business_id: str) -> list[Goal]:
    return db.query(Goal).filter(Goal.business_id == business_id).order_by(Goal.created_at.desc()).all()


def get_goal(db: Session, business_id: str, goal_id: str) -> Goal:
    from app.core.errors import NotFoundError

    goal = db.get(Goal, goal_id)
    if goal is None or goal.business_id != business_id:
        raise NotFoundError(f"Goal {goal_id} not found.")
    return goal
