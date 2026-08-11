import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    dependencies = {}

    try:
        db.execute(text("SELECT 1"))
        dependencies["database"] = "ok"
    except Exception as exc:  # pragma: no cover - only hit when DB is actually down
        logger.warning("Database health check failed: %s", exc)
        dependencies["database"] = "unavailable"

    status = "ok" if all(v == "ok" for v in dependencies.values()) else "degraded"
    return {"status": status, "dependencies": dependencies}
