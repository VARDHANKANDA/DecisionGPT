from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_research_access
from app.db.session import get_db
from app.schemas.research import RunTrainingRequest, TrainingRunOut
from app.services import training_service

router = APIRouter(dependencies=[Depends(require_research_access)])


@router.get("/training/tasks")
def training_tasks():
    """What the current architecture can actually train — no fabricated tasks."""
    return training_service.supported_tasks()


@router.post("/training/run", response_model=TrainingRunOut)
def run_training(payload: RunTrainingRequest, db: Session = Depends(get_db)):
    return training_service.start_training(
        db,
        task=payload.task,
        model_type=payload.model_type,
        dataset_version_id=payload.dataset_version_id,
        platform_domain=payload.platform_domain,
        parameters=payload.parameters,
        random_seed=payload.seed,
    )


@router.get("/training/runs", response_model=list[TrainingRunOut])
def list_training_runs(task: str | None = None, db: Session = Depends(get_db)):
    return training_service.list_training_runs(db, task=task)


@router.get("/training/runs/{run_id}", response_model=TrainingRunOut)
def get_training_run(run_id: str, db: Session = Depends(get_db)):
    return training_service.get_training_run(db, run_id)
