"""Research Console — dedicated evaluation endpoints (docs Phase 10).

All admin/research-only (require_research_access). Read-only aggregates over
existing records — no new experiment systems, full traceability preserved
(experiment_id / training_run_id / model version / decision_id /
simulation_id / graph_version references are included in the payloads).
"""
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_research_access, verify_business_access
from app.db.session import get_db
from app.services import (
    agent_evaluation_service,
    causal_graph_evaluation_service,
    digital_twin_evaluation_service,
    evaluation_console_service,
    forecast_validation_service,
    model_reevaluation_service,
    model_performance_service,
    paper_results_service,
)

router = APIRouter(dependencies=[Depends(require_research_access)])


@router.get("/model-performance")
def model_performance(
    task: str | None = None,
    dataset_version: str | None = None,
    model_name: str | None = None,
    training_run_id: str | None = None,
    db: Session = Depends(get_db),
):
    return model_performance_service.get_model_performance(
        db, task=task, dataset_version=dataset_version, model_name=model_name, training_run_id=training_run_id
    )


@router.get("/verified-results")
def verified_results():
    return model_performance_service.get_verified_research_results()


@router.get("/digital-twin-evaluation")
def digital_twin_evaluation(db: Session = Depends(get_db)):
    return digital_twin_evaluation_service.get_evaluation_report(db)


@router.post("/digital-twin-evaluation/backfill")
def digital_twin_evaluation_backfill(db: Session = Depends(get_db)):
    created = digital_twin_evaluation_service.backfill(db)
    return {"evaluations_created": created}


@router.get("/causal-evaluation")
def causal_evaluation(db: Session = Depends(get_db)):
    return causal_graph_evaluation_service.get_causal_graph_evaluation(db)


@router.get("/agent-evaluation")
def agent_evaluation(db: Session = Depends(get_db)):
    return agent_evaluation_service.get_agent_evaluation(db)


@router.get("/paper-results")
def paper_results(db: Session = Depends(get_db)):
    return paper_results_service.get_paper_results(db)


# ------------------------------------------------------------------------------------------------ evaluation metrics page
@router.get("/evaluation")
def evaluation_overview(db: Session = Depends(get_db)):
    """Every recorded evaluation metric as shared-registry cards, with training, benchmark and production evidence kept apart."""
    return evaluation_console_service.overview(db)


@router.get("/evaluation/business/{business_id}", dependencies=[Depends(verify_business_access)])
def evaluation_business(business_id: str, db: Session = Depends(get_db)):
    """The newest stored validation reports of one business the caller owns (never another tenant's)."""
    return evaluation_console_service.business_validation(db, business_id)


@router.post("/evaluation/business/{business_id}/run", dependencies=[Depends(verify_business_access)])
def evaluation_business_run(business_id: str, kind: Literal["forecast", "customer"] = "forecast", db: Session = Depends(get_db)):
    """Run (and store) a read-only validation on the caller's own business, then return it presented. Changes no model."""
    if kind == "forecast":
        report = forecast_validation_service.run_forecast_validation(db, business_id)
    else:
        report = forecast_validation_service.run_customer_score_validation(db, business_id)
    return evaluation_console_service.present_run(report, kind)


# ------------------------------------------------------------------------------------------------ re-evaluation of registered forecasting models
@router.post("/evaluation/models/run-pending")
def evaluation_models_run_pending(db: Session = Depends(get_db)):
    """Re-score every registered forecasting model whose WAPE was never recorded (and never attempted) on its held-out test block. Trains nothing."""
    return model_reevaluation_service.reevaluate_pending(db)


@router.post("/evaluation/models/{model_id}/run")
def evaluation_model_run(model_id: str, db: Session = Depends(get_db)):
    """Re-score ONE registered forecasting model on its held-out test block and store the verified (or failed/unavailable) outcome. Trains nothing and
    calls no external service; the model and its recorded training metrics are unchanged."""
    record = model_reevaluation_service.reevaluate_model(db, model_id)
    return {"model_id": model_id, "status": record["status"], "reason": record.get("reason"), "evaluated_at": record.get("evaluated_at"), "verification": record.get("verification")}
