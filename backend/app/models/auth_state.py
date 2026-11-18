"""Server-side authentication state that cannot live in a signed token: revoked token ids (logout) and rate-limit counters.

Both tables are tiny, indexed on their primary key and pruned of expired rows. They live in the application database so that every
worker or replica sees the same state (an in-process limiter would give each replica its own counters).
"""
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import GUID


class RevokedToken(Base):
    """A token id (``jti``) that must no longer be accepted although its signature and expiry are valid (explicit logout)."""

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(GUID(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)  # rows past this are pruned


class RateLimitBucket(Base):
    """A fixed-window counter. ``key`` = scope + keyed hash of the subject (never an email or an address) + window number."""

    __tablename__ = "rate_limit_buckets"

    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_rate_limit_buckets_expires_at", "expires_at"),)
