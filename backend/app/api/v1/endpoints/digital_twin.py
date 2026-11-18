from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics import digital_twin_service
from app.analytics.digital_twin_service import Action
from app.db.session import get_db
from app.schemas.digital_twin import SimulateRequest, SimulationOut

router = APIRouter()


@router.post("/businesses/{business_id}/digital-twin/simulate", response_model=SimulationOut)
def simulate(business_id: str, payload: SimulateRequest, db: Session = Depends(get_db)):
    actions = [Action(type=a.type, value=a.value) for a in payload.actions]
    result = digital_twin_service.simulate_strategy(db, business_id, actions, goal_id=payload.goal_id, horizon_days=payload.horizon_days)
    return digital_twin_service.api_view(db, business_id, result, payload.horizon_days)


@router.get(
    "/businesses/{business_id}/digital-twin/simulations/{simulation_id}", response_model=SimulationOut
)
def get_simulation(business_id: str, simulation_id: str, db: Session = Depends(get_db)):
    result = digital_twin_service.get_simulation(db, business_id, simulation_id)
    return digital_twin_service.public_view(digital_twin_service.read_with_business_baseline(result))
