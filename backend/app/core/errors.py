"""Consistent application error type + FastAPI exception handlers.

Matches the error contract in docs/API_SPECIFICATION.md:
    {"error": {"code": "...", "message": "...", "details": {}}}
"""
from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application error. Raise this (or a subclass) from services —
    never leak a raw exception/stack trace to the client."""

    code: str = "APPLICATION_ERROR"
    http_status: int = status.HTTP_400_BAD_REQUEST

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


class BusinessAccessDeniedError(AppError):
    code = "BUSINESS_ACCESS_DENIED"
    http_status = status.HTTP_403_FORBIDDEN


def _error_body(code: str, message: str, details: dict[str, Any]) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.http_status,
            content=_error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_error_body(
                "REQUEST_VALIDATION_ERROR",
                "The request payload failed validation.",
                {"errors": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                "INTERNAL_ERROR",
                "Something went wrong on our side. Please try again.",
                {},
            ),
        )
