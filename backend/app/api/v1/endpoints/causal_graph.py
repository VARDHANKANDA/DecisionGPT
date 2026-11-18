from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics import causal_graph_service
from app.db.session import get_db
from app.schemas.causal_graph import CausalGraphOut

router = APIRouter()


@router.post("/businesses/{business_id}/causal-graph/build", response_model=CausalGraphOut)
def build_causal_graph(business_id: str, db: Session = Depends(get_db)):
    return causal_graph_service.build_causal_graph(db, business_id)


@router.get("/businesses/{business_id}/causal-graph", response_model=CausalGraphOut)
def get_causal_graph(business_id: str, db: Session = Depends(get_db)):
    return causal_graph_service.get_latest_causal_graph(db, business_id)
