from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_research_access
from app.db.session import get_db
from app.schemas.model import ModelOut
from app.services import model_registry_service

router = APIRouter(dependencies=[Depends(require_research_access)])


@router.get("/models", response_model=list[ModelOut])
def list_models(
    model_type: str | None = None, status: str | None = None, db: Session = Depends(get_db)
):
    return model_registry_service.list_models(db, model_type=model_type, status=status)


@router.post("/models/sync", response_model=list[ModelOut])
def sync_models(db: Session = Depends(get_db)):
    """Sync file-based training manifests (models/registry_index.jsonl)
    into the models table. Called after running ml/training/* from the CLI.
    Training-Center models are registered directly and are never touched
    by this sync."""
    return model_registry_service.sync_from_file_registry(db)


@router.get("/models/{model_id}", response_model=ModelOut)
def get_model(model_id: str, db: Session = Depends(get_db)):
    return model_registry_service.get_model(db, model_id)


@router.post("/models/{model_id}/promote", response_model=ModelOut)
def promote_model(model_id: str, db: Session = Depends(get_db)):
    """Make this the ACTIVE model for its model_name (archives siblings).
    Only ACTIVE models are used by the production DecisionGPT pipeline."""
    return model_registry_service.promote_model(db, model_id)


@router.post("/models/{model_id}/archive", response_model=ModelOut)
def archive_model(model_id: str, db: Session = Depends(get_db)):
    return model_registry_service.archive_model(db, model_id)
