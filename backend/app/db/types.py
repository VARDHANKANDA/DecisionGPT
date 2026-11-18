"""Cross-dialect GUID column type.

Renders as native PostgreSQL UUID in production, and as CHAR(36) on any
other dialect (SQLite) so the same ORM models can be exercised in tests
without a live Postgres instance. Standard SQLAlchemy recipe.
"""
import datetime as _dt
import decimal
import math
import uuid

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import CHAR, JSON, TypeDecorator


class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=False))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value) if isinstance(value, uuid.UUID) else value

    def process_result_value(self, value, dialect):
        return value


def json_safe(value):
    """Convert database/numpy values into plain JSON types (Decimal -> float, dates -> ISO text, NaN/inf -> None)."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, decimal.Decimal):
        f = float(value)
        return f if math.isfinite(f) else None
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [json_safe(v) for v in value]
    item = getattr(value, "item", None)  # numpy scalar
    if callable(item):
        return json_safe(item())
    return str(value)


class SafeJSON(TypeDecorator):
    """JSON column that stores only plain JSON types, so a stray Decimal/date/numpy value can never break a save."""

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return json_safe(value)
