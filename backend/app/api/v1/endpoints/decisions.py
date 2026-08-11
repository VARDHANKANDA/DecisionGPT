from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.decision import AnalyzeGoalRequest, DecisionOut, DecisionSummaryOut
from app.services import decision_service

router = APIRouter()


@router.post("/businesses/{business_id}/decisions/analyze", response_model=DecisionOut)
def analyze_goal(business_id: str, payload: AnalyzeGoalRequest, db: Session = Depends(get_db)):
    return decision_service.analyze_goal(db, business_id, payload.goal_id)


@router.get("/businesses/{business_id}/decisions", response_model=list[DecisionSummaryOut])
def list_decisions(business_id: str, db: Session = Depends(get_db)):
    return decision_service.list_decisions(db, business_id)


@router.get("/businesses/{business_id}/decisions/{decision_id}", response_model=DecisionSummaryOut)
def get_decision(business_id: str, decision_id: str, db: Session = Depends(get_db)):
    return decision_service.get_decision(db, business_id, decision_id)
