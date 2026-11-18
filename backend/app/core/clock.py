"""The one place "today" comes from for analytics that resolve relative dates.

Production: ``today()`` is exactly ``date.today()`` — nothing changes by default.

Research / evaluation: code may *explicitly* pin a reference date for the duration of a ``with`` block
(``with reference_date(date(2025, 3, 31)): ...``). The pin lives in a ``ContextVar``, so it is scoped to the block
(and to the current thread / async task); it is never a process-wide switch, nothing in production calls it, and it
is logged at WARNING level whenever it is entered so a pinned clock is always visible in the logs.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date
from typing import Iterator

logger = logging.getLogger(__name__)

_reference: ContextVar[date | None] = ContextVar("decisiongpt_reference_date", default=None)


def today() -> date:
    pinned = _reference.get()
    return pinned if pinned is not None else date.today()


def is_pinned() -> bool:
    return _reference.get() is not None


@contextmanager
def reference_date(value: date) -> Iterator[date]:
    """Pin ``today()`` to ``value`` inside the block (research / tests only)."""
    if not isinstance(value, date):
        raise TypeError("reference_date expects a datetime.date")
    logger.warning("analytics clock pinned to reference date %s (research/evaluation mode)", value.isoformat())
    token = _reference.set(value)
    try:
        yield value
    finally:
        _reference.reset(token)
