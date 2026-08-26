"""Research Console — dedicated evaluation endpoints (docs Phase 10).

All admin/research-only (require_research_access). Read-only aggregates over
existing records — no new experiment systems, full traceability preserved
(experiment_id / training_run_id / model version / decision_id /
simulation_id / graph_version references are included in the payloads).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_research_access
from app.db.session import get_db
from app.services import (
    agent_evaluation_service,
    causal_graph_evaluation_service,
    digital_twin_evaluation_service,
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
