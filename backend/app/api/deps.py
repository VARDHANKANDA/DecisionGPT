"""Shared FastAPI dependencies."""
from fastapi import Header

from app.core.config import get_settings
from app.core.errors import BusinessAccessDeniedError


def require_research_access(x_research_token: str | None = Header(default=None)) -> None:
    """Gate for every /api/v1/research/** endpoint.

    The Research Console is a private, platform-administrator-only surface
    (docs/PRD.md §8 "Research Console — Scope") and must never be reachable
    from the normal SME navigation or API surface.
    """
    settings = get_settings()
    if not settings.research_console_enabled:
        raise BusinessAccessDeniedError("The Research Console is disabled.")
    if not x_research_token or x_research_token != settings.research_console_token:
        raise BusinessAccessDeniedError("Missing or invalid research console credentials.")
