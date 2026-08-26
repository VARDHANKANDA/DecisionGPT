from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_research_access
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.schemas.research import ExperimentRunOut, RunExperimentRequest
from app.services import experiment_service

router = APIRouter(dependencies=[Depends(require_research_access)])


@router.post("/experiments/run", response_model=ExperimentRunOut)
def run_experiment(payload: RunExperimentRequest, db: Session = Depends(get_db)):
    return experiment_service.run_experiment(db, payload.experiment_type, payload.configuration)


@router.get("/experiments", response_model=list[ExperimentRunOut])
def list_experiments(experiment_type: str | None = None, db: Session = Depends(get_db)):
    return experiment_service.list_experiments(db, experiment_type)


@router.get("/experiments/manifest")
def experiment_manifest(db: Session = Depends(get_db)):
    """Reproducibility manifest for every recorded experiment — id, seed,
    dataset version, model versions, config, timings, headline metrics.
    Suitable for a paper's methodology appendix."""
    manifest = experiment_service.build_manifest(db)
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    return manifest


@router.get("/experiments/{experiment_id}", response_model=ExperimentRunOut)
def get_experiment(experiment_id: str, db: Session = Depends(get_db)):
    run = experiment_service.get_experiment(db, experiment_id)
    if run is None:
        raise NotFoundError(f"Experiment {experiment_id} not found.")
    return run
