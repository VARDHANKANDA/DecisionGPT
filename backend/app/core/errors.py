"""Consistent application error type + FastAPI exception handlers.

Matches the error contract in docs/API_SPECIFICATION.md:
    {"error": {"code": "...", "message": "...", "details": {}}}
"""
import logging
import traceback
from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError


class AppError(Exception):
    """Base application error. Raise this (or a subclass) from services —
    never leak a raw exception/stack trace to the client."""

    code: str = "APPLICATION_ERROR"
    http_status: int = status.HTTP_400_BAD_REQUEST
    headers: Optional[dict[str, str]] = None  # extra response headers (e.g. Retry-After on a 429)

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    code = "NOT_FOUND"
    http_status = status.HTTP_404_NOT_FOUND


class InsufficientDataError(AppError):
    code = "INSUFFICIENT_DATA"
    http_status = 422


class ValidationFailedError(AppError):
    code = "VALIDATION_FAILED"
    http_status = 422


class ConflictError(AppError):
    """The request is valid but conflicts with the current state (for example a forecast that changed since it was shown)."""

    code = "CONFLICT"
    http_status = status.HTTP_409_CONFLICT


class BusinessAccessDeniedError(AppError):
    code = "BUSINESS_ACCESS_DENIED"
    http_status = status.HTTP_403_FORBIDDEN


logger = logging.getLogger("decisiongpt.errors")


def uuid_or_not_found(value: Any, message: str) -> str:
    """An identifier from outside the application, checked before it reaches a UUID column: text that is not a UUID cannot name a record, so
    it is "not found" (PostgreSQL would otherwise raise a data error where SQLite quietly matches nothing)."""
    import uuid

    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise NotFoundError(message)


def _error_body(code: str, message: str, details: dict[str, Any]) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.http_status,
            content=_error_body(exc.code, exc.message, exc.details),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_error_body(
                "REQUEST_VALIDATION_ERROR",
                "The request payload failed validation.",
                # only where and why: the submitted value ("input") and validator context are NOT echoed back - a rejected password or token
                # would otherwise be returned in the body and copied into client, proxy and access logs
                {"errors": [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]},
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        # Logged so an operator can find the fault, but never the exception message (it can carry SQL parameters, paths or customer data):
        # the exception type, where it was raised, and the request id that correlates it with the access log.
        frames = traceback.extract_tb(exc.__traceback__)
        mine = [f for f in frames if "/app/" in f.filename.replace("\\", "/") and "site-packages" not in f.filename]   # the innermost frame of OUR code
        f = (mine or frames or [None])[-1]
        where = f"{f.filename.replace(chr(92), '/').rsplit('/', 1)[-1]}:{f.lineno}" if f else "unknown"
        logger.error("unhandled_error", extra={"request_id": getattr(request.state, "request_id", None), "exception_type": type(exc).__name__,
                                               "where": where, "method": request.method})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                "INTERNAL_ERROR",
                "Something went wrong on our side. Please try again.",
                {},
            ),
        )

    @app.exception_handler(DataError)
    async def handle_data_error(request: Request, exc: DataError):
        # PostgreSQL refuses text that is not a UUID ("does-not-exist") with a DataError where SQLite just matches nothing. An identifier that
        # cannot be a UUID cannot name an existing record, so it is "not found"; any other data error is an internal fault and is reported as one.
        if "uuid" in str(getattr(exc, "orig", exc)).lower():
            return JSONResponse(status_code=404, content=_error_body("NOT_FOUND", "Not found.", {}))
        return await handle_unexpected_error(request, exc)
