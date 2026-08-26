from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_research_access
from app.db.session import get_db
from app.schemas.research import ResearchOverviewOut
from app.services import research_overview_service

router = APIRouter(dependencies=[Depends(require_research_access)])


@router.get("/overview", response_model=ResearchOverviewOut)
def research_overview(db: Session = Depends(get_db)):
    return research_overview_service.build_overview(db)
