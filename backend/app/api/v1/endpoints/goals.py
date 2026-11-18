from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.goal import GoalCreateRequest, GoalOut
from app.services import goal_service

router = APIRouter()


@router.post("/businesses/{business_id}/goals", response_model=GoalOut, status_code=201)
def create_goal(business_id: str, payload: GoalCreateRequest, db: Session = Depends(get_db)):
    return goal_service.create_goal(db, business_id, payload.text)


@router.get("/businesses/{business_id}/goals", response_model=list[GoalOut])
def list_goals(business_id: str, db: Session = Depends(get_db)):
    return goal_service.list_goals(db, business_id)


@router.get("/businesses/{business_id}/goals/{goal_id}", response_model=GoalOut)
def get_goal(business_id: str, goal_id: str, db: Session = Depends(get_db)):
    return goal_service.get_goal(db, business_id, goal_id)
