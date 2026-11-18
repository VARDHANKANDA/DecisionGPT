"""Business-OS endpoints: data platform, KPI monitoring, health, alerts, reports, causal / counterfactual analysis, debate, explainability.

All routes are mounted under ``/businesses/{business_id}`` behind ``verify_business_access`` (see api/v1/router.py), and every service call
filters by ``business_id``. Inputs are validated by Pydantic here and again in the services.
"""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models.business import Business
from app.services import (
    alert_service,
    analysis_run_service,
    causal_engine_service,
    counterfactual_service,
    data_platform_service as dps,
    debate_service,
    explain_service,
    forecast_validation_service,
    health_service,
    kpi_monitor_service as kms,
    report_service,
)

router = APIRouter()
B = "/businesses/{business_id}"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------------------------------------ data platform
@router.get(B + "/data/profile/{table}")
def profile(business_id: str, table: str, record: bool = False, db: Session = Depends(get_db)):
    return dps.profile(db, business_id, table, record)


@router.get(B + "/data/preview/{table}")
def preview(business_id: str, table: str, offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=200), search: str | None = Query(None, max_length=100), db: Session = Depends(get_db)):
    return dps.table_preview(db, business_id, table, offset, limit, search)


@router.get(B + "/data/cleaning/{table}")
def cleaning(business_id: str, table: str, db: Session = Depends(get_db)):
    return {"table": table, "proposals": dps.cleaning_proposals(db, business_id, table)}


class CleanApply(_Strict):
    proposal_id: str = Field(min_length=3, max_length=200)
    confirm: bool = False


@router.post(B + "/data/cleaning/apply")
def cleaning_apply(business_id: str, body: CleanApply, db: Session = Depends(get_db)):
    return dps.apply_cleaning(db, business_id, body.proposal_id, body.confirm)


@router.post(B + "/data/runs/{run_id}/revert")
def revert(business_id: str, run_id: str, db: Session = Depends(get_db)):
    return dps.revert_run(db, business_id, run_id)


class ValidateBody(_Strict):
    tables: list[str] | None = Field(default=None, max_length=10)


@router.post(B + "/data/validation/run")
def validation(business_id: str, body: ValidateBody, db: Session = Depends(get_db)):
    return dps.run_validation(db, business_id, body.tables)


@router.get(B + "/data/validation/latest")
def validation_latest(business_id: str, db: Session = Depends(get_db)):
    from app.models.platform import DataPrepRun

    r = db.query(DataPrepRun).filter(DataPrepRun.business_id == business_id, DataPrepRun.stage == "validate").order_by(DataPrepRun.created_at.desc()).first()
    return {"run": None if r is None else dps._run_meta(r)}  # noqa: SLF001


@router.get(B + "/data/transform/options")
def transform_options(business_id: str, db: Session = Depends(get_db)):
    return {"options": dps.transform_options(db, business_id),
            "not_available": ["Joins between tables", "Free-form derived columns", "Any user-written code or SQL (never executed)"]}


class TransformBody(_Strict):
    id: str = Field(min_length=3, max_length=100)
    kind: Literal["standardise_style", "map_values", "recalculate_totals", "aggregate_preview"]
    table: str = Field(max_length=40)
    column: str | None = Field(default=None, max_length=60)
    style: str | None = Field(default=None, max_length=10)
    mapping: dict[str, str] | None = None
    by: str | None = Field(default=None, max_length=10)
    confirm: bool = False


@router.post(B + "/data/transform/preview")
def transform_preview(business_id: str, body: TransformBody, db: Session = Depends(get_db)):
    return dps.transform_preview(db, business_id, body.model_dump(exclude={"confirm"}, exclude_none=True))


@router.post(B + "/data/transform/apply")
def transform_apply(business_id: str, body: TransformBody, db: Session = Depends(get_db)):
    return dps.apply_transform(db, business_id, body.model_dump(exclude={"confirm"}, exclude_none=True), body.confirm)


@router.get(B + "/data/pipeline")
def pipeline(business_id: str, db: Session = Depends(get_db)):
    return dps.pipeline(db, business_id)


@router.get(B + "/data/prep-history")
def prep_history(business_id: str, stage: Literal["profile", "clean", "validate", "transform"] | None = None, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return {"runs": dps.history(db, business_id, limit, stage)}


@router.get(B + "/data/prep-history/{run_id}")
def prep_run(business_id: str, run_id: str, db: Session = Depends(get_db)):
    return dps.get_run(db, business_id, run_id)


# ------------------------------------------------------------------------------------------------ KPI monitoring
@router.get(B + "/kpis")
def kpis(business_id: str, period_days: int = 30, anchor: Literal["today", "latest"] = "today", db: Session = Depends(get_db)):
    return kms.list_kpis(db, business_id, period_days, anchor)


@router.get(B + "/kpis/{key}/trend")
def kpi_trend(business_id: str, key: str, period_days: int = 90, anchor: Literal["today", "latest"] = "today", db: Session = Depends(get_db)):
    return kms.trend(db, business_id, key, period_days, anchor)


class TargetBody(_Strict):
    value: float
    direction: Literal["higher", "lower"] | None = None
    period_days: int = 30


@router.put(B + "/kpis/{key}/target")
def kpi_set_target(business_id: str, key: str, body: TargetBody, db: Session = Depends(get_db)):
    t = kms.set_target(db, business_id, key, body.value, body.direction, body.period_days)
    return {"key": key, "value": t.target_value, "direction": t.direction, "period_days": t.period_days}


@router.delete(B + "/kpis/{key}/target", status_code=204)
def kpi_delete_target(business_id: str, key: str, db: Session = Depends(get_db)):
    kms.delete_target(db, business_id, key)


# ------------------------------------------------------------------------------------------------ business health
@router.get(B + "/health-score")
def health(business_id: str, period_days: int = 30, anchor: Literal["today", "latest"] = "today", save: bool = False, db: Session = Depends(get_db)):
    return health_service.assess(db, business_id, period_days, anchor, save=save)


@router.get(B + "/health-score/history")
def health_history(business_id: str, db: Session = Depends(get_db)):
    return {"snapshots": health_service.history(db, business_id)}


# ------------------------------------------------------------------------------------------------ alerts
@router.get(B + "/alerts")
def alerts(business_id: str, status: Literal["active", "open", "read", "resolved", "cleared"] | None = "active", db: Session = Depends(get_db)):
    return {"alerts": alert_service.list_alerts(db, business_id, status)}


@router.post(B + "/alerts/evaluate")
def alerts_evaluate(business_id: str, anchor: Literal["today", "latest"] = "today", db: Session = Depends(get_db)):
    return alert_service.evaluate(db, business_id, anchor)


class AlertStatus(_Strict):
    status: Literal["read", "resolved"]


@router.post(B + "/alerts/{alert_id}/status")
def alert_status(business_id: str, alert_id: str, body: AlertStatus, db: Session = Depends(get_db)):
    return alert_service.set_status(db, business_id, alert_id, body.status)


@router.get(B + "/alerts/rules")
def alert_rules(business_id: str, db: Session = Depends(get_db)):
    return {"rules": alert_service.rule_settings(db, business_id), "cooldown_hours": alert_service.COOLDOWN_HOURS,
            "monitoring_note": "Rules are checked on demand (when you open Smart Alerts or the Overview, or press Check now). There is no background monitoring."}


class RuleBody(_Strict):
    enabled: bool = True
    threshold: float | None = None


@router.put(B + "/alerts/rules/{rule_key}")
def alert_rule_set(business_id: str, rule_key: str, body: RuleBody, db: Session = Depends(get_db)):
    return alert_service.set_rule(db, business_id, rule_key, body.enabled, body.threshold)


# ------------------------------------------------------------------------------------------------ reports
@router.get(B + "/reports/types")
def report_types(business_id: str):
    return {"types": [{"key": k, "title": v} for k, v in report_service.REPORT_TYPES.items()]}


class ReportBody(_Strict):
    report_type: str
    period_days: int = 30
    anchor: Literal["today", "latest"] = "today"


@router.post(B + "/reports", status_code=201)
def report_create(business_id: str, body: ReportBody, db: Session = Depends(get_db)):
    business = db.get(Business, business_id)
    if business is None:
        raise NotFoundError("Business not found.")
    return report_service.create(db, business, body.report_type, body.period_days, body.anchor)


@router.get(B + "/reports")
def report_list(business_id: str, db: Session = Depends(get_db)):
    return {"reports": report_service.list_reports(db, business_id)}


@router.get(B + "/reports/{report_id}")
def report_get(business_id: str, report_id: str, db: Session = Depends(get_db)):
    return report_service.get(db, business_id, report_id)


@router.delete(B + "/reports/{report_id}", status_code=204)
def report_delete(business_id: str, report_id: str, db: Session = Depends(get_db)):
    report_service.delete(db, business_id, report_id)


# ------------------------------------------------------------------------------------------------ causal & counterfactual
class CausalBody(_Strict):
    method: Literal["association", "did"]
    outcome: str = Field(max_length=30)
    treatment: str | None = Field(default=None, max_length=30)
    controls: list[str] | None = Field(default=None, max_length=5)
    treated: list[str] | None = Field(default=None, max_length=10)
    control: list[str] | None = Field(default=None, max_length=10)
    intervention_date: str | None = Field(default=None, max_length=10)
    window_days: int | None = Field(default=28, ge=7, le=120)


@router.post(B + "/causal/analyze")
def causal_analyze(business_id: str, body: CausalBody, db: Session = Depends(get_db)):
    return causal_engine_service.run(db, business_id, body.model_dump(exclude_none=True))


@router.get(B + "/causal/runs")
def causal_runs(business_id: str, db: Session = Depends(get_db)):
    return {"runs": analysis_run_service.list_runs(db, business_id, "causal")}


@router.get(B + "/causal/runs/{run_id}")
def causal_run(business_id: str, run_id: str, db: Session = Depends(get_db)):
    return analysis_run_service.get(db, business_id, run_id, "causal")


class CounterfactualBody(_Strict):
    mode: Literal["deterministic_scenario", "model_prediction", "causal_counterfactual"]
    lever: Literal["price_change_pct", "marketing_change_pct"] | None = None
    change_pct: float | None = Field(default=None, ge=-90, le=300)
    elasticity: float | None = Field(default=0.0, ge=-5, le=5)
    baseline_days: int | None = 30
    anchor: Literal["today", "latest"] | None = "today"
    analysis_id: str | None = Field(default=None, max_length=60)


@router.post(B + "/counterfactual/run")
def counterfactual_run(business_id: str, body: CounterfactualBody, db: Session = Depends(get_db)):
    return counterfactual_service.run(db, business_id, body.model_dump(exclude_none=True))


@router.get(B + "/counterfactual/runs")
def counterfactual_runs(business_id: str, db: Session = Depends(get_db)):
    return {"runs": analysis_run_service.list_runs(db, business_id, "counterfactual")}


@router.get(B + "/counterfactual/runs/{run_id}")
def counterfactual_get(business_id: str, run_id: str, db: Session = Depends(get_db)):
    return analysis_run_service.get(db, business_id, run_id, "counterfactual")


# ------------------------------------------------------------------------------------------------ multi-agent debate
@router.get(B + "/debate/status")
def debate_status(business_id: str):
    return {"rule_based_available": True, "ai_model_available": False, "ai_model_notice": debate_service.AI_MODEL_UNAVAILABLE,
            "stages": debate_service.STAGES, "agents": [{"key": k, "name": v} for k, v in debate_service.AGENT_NAMES.items()]}


class DebateBody(_Strict):
    question: str = Field(min_length=1, max_length=debate_service.MAX_QUESTION)
    mode: Literal["rule_based", "ai_model"] = "rule_based"
    anchor: Literal["today", "latest"] = "today"


@router.post(B + "/debate/run")
def debate_run(business_id: str, body: DebateBody, db: Session = Depends(get_db)):
    return debate_service.run(db, business_id, body.question, body.mode, body.anchor)


@router.get(B + "/debate/runs")
def debate_runs(business_id: str, db: Session = Depends(get_db)):
    return {"runs": analysis_run_service.list_runs(db, business_id, "debate")}


@router.get(B + "/debate/runs/{run_id}")
def debate_get(business_id: str, run_id: str, db: Session = Depends(get_db)):
    return analysis_run_service.get(db, business_id, run_id, "debate")


# ------------------------------------------------------------------------------------------------ explainability
@router.get(B + "/explain/kpi/{key}")
def explain_kpi(business_id: str, key: str, period_days: int = 30, anchor: Literal["today", "latest"] = "today", db: Session = Depends(get_db)):
    return explain_service.explain_kpi(db, business_id, key, period_days, anchor)


@router.get(B + "/explain/answer/{memory_id}")
def explain_answer(business_id: str, memory_id: str, db: Session = Depends(get_db)):
    return explain_service.explain_answer(db, business_id, memory_id)


# ------------------------------------------------------------------------------------------------ validation on this business's own data
class ForecastValidationBody(_Strict):
    horizons: list[int] | None = Field(default=None, max_length=3)


class CustomerValidationBody(_Strict):
    window_days: int = Field(default=60, ge=14, le=120)


@router.post(B + "/validation/forecast/run")
def validation_forecast_run(business_id: str, body: ForecastValidationBody, db: Session = Depends(get_db)):
    """Backtest this business's forecast against naive / seasonal-naive / trailing-mean references. Read-only: changes no model."""
    return forecast_validation_service.run_forecast_validation(db, business_id, body.horizons)


@router.post(B + "/validation/customer-scores/run")
def validation_customer_run(business_id: str, body: CustomerValidationBody, db: Session = Depends(get_db)):
    """Check the customer score against later inactivity in this business's own sales (a proxy, not churn). Read-only."""
    return forecast_validation_service.run_customer_score_validation(db, business_id, body.window_days)


@router.get(B + "/validation/runs")
def validation_runs(business_id: str, kind: Literal["forecast_eval", "customer_eval"] = "forecast_eval", db: Session = Depends(get_db)):
    return {"runs": analysis_run_service.list_runs(db, business_id, kind)}


@router.get(B + "/validation/runs/{run_id}")
def validation_run(business_id: str, run_id: str, db: Session = Depends(get_db)):
    try:
        return analysis_run_service.get(db, business_id, run_id, "forecast_eval")
    except NotFoundError:
        return analysis_run_service.get(db, business_id, run_id, "customer_eval")
