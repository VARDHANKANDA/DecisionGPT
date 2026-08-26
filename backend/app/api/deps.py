"""Shared FastAPI dependencies — auth + access control (Phase 4).

When ``settings.auth_enabled`` is False (default; local dev + tests) these
dependencies are permissive no-ops, so the existing open API keeps working.
When it is True:
  - every ``/businesses/{business_id}/**`` route requires a bearer token
    whose user *owns* that business;
  - every ``/research/**`` route requires a bearer token for an ``admin``
    user (the legacy ``X-Research-Token`` header still works too).
"""
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, BusinessAccessDeniedError, NotFoundError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.business import Business
from app.models.user import ROLE_ADMIN, User


class UnauthenticatedError(AppError):
    code = "UNAUTHENTICATED"
    http_status = 401


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    """Resolve the bearer token to a User, or None when no/invalid token.
    Never raises — routes decide whether a user is required."""
    token = _bearer(authorization)
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    return db.get(User, payload.get("sub"))


def require_user(user: User | None = Depends(get_current_user)) -> User:
    settings = get_settings()
    if not settings.auth_enabled:
        return user  # may be None — auth disabled
    if user is None or not user.is_active:
        raise UnauthenticatedError("A valid bearer token is required.")
    return user


def require_admin(user: User | None = Depends(get_current_user)) -> User | None:
    settings = get_settings()
    if not settings.auth_enabled:
        return user
    if user is None or user.role != ROLE_ADMIN or not user.is_active:
        raise BusinessAccessDeniedError("Admin (researcher) access is required.")
    return user


def verify_business_access(
    business_id: str,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Router-level guard for every ``/businesses/{business_id}/**`` route.
    Confirms the business exists and, when auth is on, that the caller owns
    it. Never trusts ``business_id`` from the client without this check
    (docs Phase 4 requirement)."""
    settings = get_settings()
    business = db.get(Business, business_id)
    if business is None:
        raise NotFoundError(f"Business {business_id} not found.")
    if not settings.auth_enabled:
        return
    if user is None or not user.is_active:
        raise UnauthenticatedError("A valid bearer token is required.")
    if business.owner_user_id != user.id:
        raise BusinessAccessDeniedError("You do not have access to this business.")


def require_research_access(
    x_research_token: str | None = Header(default=None),
    user: User | None = Depends(get_current_user),
) -> None:
    """Gate for every ``/api/v1/research/**`` endpoint (docs/PRD.md §8).

    Accepts EITHER a valid admin bearer token OR the static
    ``X-Research-Token`` header (kept for CI/scripts and backwards
    compatibility). SME users can never reach these routes.
    """
    settings = get_settings()
    if not settings.research_console_enabled:
        raise BusinessAccessDeniedError("The Research Console is disabled.")

    if user is not None and user.role == ROLE_ADMIN and user.is_active:
        return
    if x_research_token and x_research_token == settings.research_console_token:
        return
    raise BusinessAccessDeniedError("Missing or invalid research console credentials.")
