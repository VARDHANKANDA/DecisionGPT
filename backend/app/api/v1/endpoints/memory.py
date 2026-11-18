from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.memory import BusinessMemoryOut, DecisionOutcomeOut, RecordOutcomeRequest
from app.services import memory_service

router = APIRouter()


@router.post("/businesses/{business_id}/decisions/{decision_id}/outcome", response_model=DecisionOutcomeOut)
def record_outcome(business_id: str, decision_id: str, payload: RecordOutcomeRequest, db: Session = Depends(get_db)):
    return memory_service.record_outcome(
        db, business_id, decision_id, payload.actual_outcome, payload.recorded_at
    )


@router.get("/businesses/{business_id}/decisions/{decision_id}/outcome", response_model=DecisionOutcomeOut)
def get_outcome(business_id: str, decision_id: str, db: Session = Depends(get_db)):
    return memory_service.get_outcome(db, business_id, decision_id)


@router.get("/businesses/{business_id}/memory", response_model=list[BusinessMemoryOut])
def list_memory(business_id: str, memory_type: str | None = None, db: Session = Depends(get_db)):
    return memory_service.list_memory(db, business_id, memory_type)
