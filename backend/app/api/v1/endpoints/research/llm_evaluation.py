from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import require_research_access
from app.services import llm_evaluation_status_service

router = APIRouter(dependencies=[Depends(require_research_access)])


@router.get("/llm-evaluation")
def llm_evaluation_status() -> dict[str, Any]:
    """Read-only state of the POS LLM evaluation (never starts a run)."""
    return llm_evaluation_status_service.build_status()
