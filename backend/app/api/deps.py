"""Shared FastAPI dependencies — auth + access control (Phase 4).

When ``settings.auth_enabled`` is False (default; local dev + tests) these
dependencies are permissive no-ops, so the existing open API keeps working.
When it is True:
  - every ``/businesses/{business_id}/**`` route requires a bearer token
    whose user *owns* that business;
  - every ``/research/**`` route requires a bearer token for an ``admin``
    user (the legacy ``X-Research-Token`` header still works too).
"""
import hmac
import logging
import uuid

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, BusinessAccessDeniedError, NotFoundError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.auth_state import RevokedToken
from app.models.business import Business
from app.models.user import ROLE_ADMIN, ROLE_RESEARCHER, User


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


def claims_from_request(request: Request) -> dict | None:
    """Verified token claims from the Authorization header (signature, algorithm, issuer, audience and expiry checked), or None. No database."""
    token = _bearer(request.headers.get("authorization"))
    return decode_token(token) if token else None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """Resolve the bearer token to a User, or None when there is no acceptable token. Never raises - routes decide whether a user is required.

    A token that is genuine and unexpired is still refused when the user's ``token_version`` has moved on (password change, sign-out of every
    session, role change, deactivation) or its id is on the revocation list (sign-out). Role and active state always come from the database."""
    claims = claims_from_request(request)
    if not claims:
        return None
    user = db.get(User, claims["sub"])
    if user is None or not user.is_active or int(user.token_version or 0) != claims["tv"]:
        return None
    if db.get(RevokedToken, claims["jti"]) is not None:
        return None
    return user


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


security_log = logging.getLogger("decisiongpt.security")


def _event(request: Request | None, event: str, **fields) -> None:
    """A security event without customer data: what happened, the route template's method and the request id. No body, no query, no email."""
    security_log.warning(
        event, extra={"request_id": getattr(getattr(request, "state", None), "request_id", None), "method": getattr(request, "method", None),
                      **fields},
    )


def require_authenticated(request: Request, user: User | None = Depends(get_current_user)) -> User | None:
    """With authentication on, the caller must hold a valid token (401 otherwise). With it off (local development / isolated tests) this is
    a no-op and returns whoever is resolved, possibly nobody."""
    if get_settings().auth_enabled and (user is None or not user.is_active):
        _event(request, "unauthenticated_request")
        raise UnauthenticatedError("A valid bearer token is required.")
    return user


def verify_business_access(
    business_id: str,
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Router-level guard for every ``/businesses/{business_id}/**`` route.

    Order matters: with authentication on the caller is authenticated FIRST (401, revealing nothing about any business), and a business that
    does not exist and a business the caller does not own produce the SAME response (404 "Business not found."), so neither an anonymous
    nor a signed-in caller can probe which business ids exist. The business id comes from the path and is never trusted without this check.
    """
    settings = get_settings()
    if settings.auth_enabled and (user is None or not user.is_active):
        _event(request, "unauthenticated_request")
        raise UnauthenticatedError("A valid bearer token is required.")
    try:
        uuid.UUID(str(business_id))
    except ValueError:
        raise NotFoundError("Business not found.")     # cannot be a business id: the same answer as an id that matches nothing
    business = db.get(Business, business_id)
    if business is None:
        raise NotFoundError("Business not found.")
    if settings.auth_enabled and business.owner_user_id != user.id:
        _event(request, "cross_tenant_denied", user_id=str(user.id))
        raise NotFoundError("Business not found.")


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

    if user is not None and user.role in (ROLE_ADMIN, ROLE_RESEARCHER) and user.is_active:
        return
    if x_research_token and hmac.compare_digest(x_research_token.encode(), settings.research_console_token.encode()):
        return
    raise BusinessAccessDeniedError("Missing or invalid research console credentials.")


def research_access_granted(user: User | None, x_research_token: str | None) -> bool:
    """The same rule as ``require_research_access`` (an active admin/researcher account, or the static research token) without raising. Used by routes that
    are open to business owners but may show research-level results only to people who could open the Research Console. Kept beside the gate it
    mirrors; tests/api/test_evaluation_chat.py proves the two agree for every kind of caller."""
    settings = get_settings()
    if not settings.research_console_enabled:
        return False
    if user is not None and user.role in (ROLE_ADMIN, ROLE_RESEARCHER) and user.is_active:
        return True
    return bool(x_research_token and hmac.compare_digest(x_research_token.encode(), settings.research_console_token.encode()))
