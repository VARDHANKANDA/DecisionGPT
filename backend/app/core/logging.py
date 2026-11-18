"""Structured logging setup.

Every log record can carry request_id/business_id/goal_id/decision_id via
the `extra=` kwarg — handlers below render them if present so traceability
fields (see docs/RESEARCH_TRACEABILITY.md) show up in every log line without
every call site needing custom formatting logic.
"""
import logging
import sys

from app.core.config import get_settings

TRACE_FIELDS = ("request_id", "business_id", "goal_id", "decision_id")


class TraceFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        trace = " ".join(
            f"{field}={getattr(record, field)}"
            for field in TRACE_FIELDS
            if hasattr(record, field)
        )
        base = super().format(record)
        return f"{base} {trace}".rstrip()


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        TraceFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
