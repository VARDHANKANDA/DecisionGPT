"""Shared column mixins for SQLAlchemy models.

UUIDPKMixin gives every table a UUID primary key generated in Python (not
DB-side) so newly-created ORM objects have a usable `id` before flush.
BusinessScopedMixin enforces the "every business-owned table has a
business_id foreign key" rule from docs/DATABASE_SCHEMA.md §2.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.db.types import GUID


def gen_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UUIDPKMixin:
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=gen_uuid)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UpdatedAtMixin:
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class BusinessScopedMixin:
    """Adds a mandatory, indexed business_id FK. Every query against a
    business-scoped table MUST filter by this column — see AGENTS.md."""

    @declared_attr
    def business_id(cls) -> Mapped[str]:  # noqa: N805 (SQLAlchemy convention)
        return mapped_column(
            GUID(),
            ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
