from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import require_research_access
from app.db.session import get_db
from app.schemas.research import ExportRequest
from app.services import research_export_service

router = APIRouter(dependencies=[Depends(require_research_access)])


@router.post("/export")
def export_table(payload: ExportRequest, db: Session = Depends(get_db)):
    content = research_export_service.export_table(db, payload.table, payload.format, payload.experiment_id)
    media_types = {
        "csv": "text/csv",
        "json": "application/json",
        "markdown": "text/markdown",
        "latex": "text/x-tex",
    }
    return PlainTextResponse(content, media_type=media_types[payload.format])
