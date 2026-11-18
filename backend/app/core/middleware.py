"""Request-ID middleware: a unique, sanitised ID on every request/response for traceability (docs/RESEARCH_TRACEABILITY.md) and
structured logging, plus the processing time. Nothing from the request body or query string is logged."""
import logging
import re
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

REQUEST_ID_HEADER = "X-Request-ID"
PROCESS_TIME_HEADER = "X-Process-Time-Ms"
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")  # a caller-supplied ID is kept only if it cannot carry log-injection text

logger = logging.getLogger("decisiongpt.request")

# The id of the request being served, visible to code that has no Request in hand (services, the rate limiter). A log filter copies it onto
# security and error records so every event can be correlated with its access-log line.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "request_id", None) is None:
            record.request_id = request_id_var.get()
        return True


for _name in ("decisiongpt.security", "decisiongpt.errors"):
    logging.getLogger(_name).addFilter(_RequestIdFilter())


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        supplied = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = supplied if _SAFE_ID.match(supplied) else str(uuid.uuid4())
        request.state.request_id = request_id
        request_id_var.set(request_id)
        t0 = time.perf_counter()
        response = await call_next(request)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[PROCESS_TIME_HEADER] = str(ms)
        logger.info(
            "request",
            extra={"request_id": request_id, "method": request.method, "path": request.url.path, "status": response.status_code, "duration_ms": ms},
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Response headers for a JSON API: no sniffing, no framing, no referrer, no caching of any API response (they hold business data and
    session tokens), and a CSP that forbids everything for API responses. The interactive documentation pages (only enabled outside
    staging/production, or by DOCS_ENABLED) load scripts from a CDN and keep the default CSP off. HSTS is sent in hardened environments; it is
    only honoured over https, which the TLS-terminating proxy must provide (docs/DEPLOYMENT.md)."""

    def __init__(self, app, *, hsts: bool = False):
        super().__init__(app)
        self.hsts = hsts

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Cross-Origin-Resource-Policy", "same-site")
        if request.url.path.startswith("/api/"):
            h.setdefault("Cache-Control", "no-store")
            h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        if self.hsts:
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
