from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_research_access
from app.db.session import get_db
from app.models.user import User
from app.schemas.model import ModelOut
from app.services import model_lifecycle_service, model_registry_service

router = APIRouter(dependencies=[Depends(require_research_access)])


def _actor(user: User | None) -> str:
    # an admin account, or the static research token (scripts/CI); never anonymous
    return (getattr(user, "email", None) or "research-token") if user is not None else "research-token"


class ReasonIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class RollbackIn(BaseModel):
    model_name: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)


@router.get("/models", response_model=list[ModelOut])
def list_models(
    model_type: str | None = None, status: str | None = None, db: Session = Depends(get_db)
):
    return model_registry_service.list_models(db, model_type=model_type, status=status)


@router.post("/models/sync", response_model=list[ModelOut])
def sync_models(db: Session = Depends(get_db)):
    """Register file-based training manifests (models/registry_index.jsonl) in the models table as CANDIDATES. Registering does not
    deploy: a later version never replaces the active one (only the first version of a name, when nothing is deployed, is activated and
    logged). Training-Center models are registered directly and are never touched by this sync."""
    return model_registry_service.sync_from_file_registry(db)


@router.post("/models/rollback", response_model=ModelOut)
def rollback_model(payload: RollbackIn, user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    """Re-activate the version that was active before the current one (its artifact must still load)."""
    return model_lifecycle_service.rollback(db, payload.model_name, _actor(user), payload.reason)


@router.get("/models/{model_id}", response_model=ModelOut)
def get_model(model_id: str, db: Session = Depends(get_db)):
    return model_registry_service.get_model(db, model_id)


@router.post("/models/{model_id}/validate")
def validate_model(model_id: str, user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    """Run the automated promotion checks. A passing candidate becomes 'validated'; a failing one 'rejected'. Neither is deployed."""
    return model_lifecycle_service.validate_candidate(db, model_id, _actor(user))


@router.get("/models/{model_id}/history")
def model_history(model_id: str, db: Session = Depends(get_db)):
    model = model_registry_service.get_model(db, model_id)
    events = model_lifecycle_service.history(db, model_name=model.model_name)
    return [
        {"id": str(e.id), "event": e.event, "version": e.version, "from_status": e.from_status, "to_status": e.to_status, "actor": e.actor,
         "reason": e.reason, "details": e.details_json, "at": e.created_at, "seq": e.seq}
        for e in events
    ]


@router.post("/models/{model_id}/promote", response_model=ModelOut)
def promote_model(model_id: str, payload: ReasonIn, user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    """Make a VALIDATED model the ACTIVE one for its model_name (archives the previous active version atomically).
    Needs a reason; the actor and reason are recorded. Only ACTIVE models are used by the production pipeline."""
    return model_registry_service.promote_model(db, model_id, _actor(user), payload.reason)


@router.post("/models/{model_id}/archive", response_model=ModelOut)
def archive_model(model_id: str, payload: ReasonIn | None = None, user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    return model_registry_service.archive_model(db, model_id, _actor(user), payload.reason if payload else None)
