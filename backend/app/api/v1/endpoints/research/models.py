from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_research_access
from app.db.session import get_db
from app.schemas.model import ModelOut
from app.services import model_registry_service

router = APIRouter(dependencies=[Depends(require_research_access)])


@router.get("/models", response_model=list[ModelOut])
def list_models(model_type: str | None = None, db: Session = Depends(get_db)):
    return model_registry_service.list_models(db, model_type=model_type)


@router.post("/models/sync", response_model=list[ModelOut])
def sync_models(db: Session = Depends(get_db)):
    """Sync file-based training manifests (models/registry_index.jsonl)
    into the models table. Called after running ml/training/*."""
    return model_registry_service.sync_from_file_registry(db)
