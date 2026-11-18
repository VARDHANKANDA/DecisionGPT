"""User accounts + roles (Phase 4 — Security & Access).

Two roles:
  - ``sme``   : an SME operator. Can only touch businesses they own.
  - ``admin`` : a researcher/platform admin. Can reach the Research Console
                (datasets, training, experiments) but has no automatic
                access to any SME's business data.
"""
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import TimestampMixin, UpdatedAtMixin, UUIDPKMixin

ROLE_SME = "sme"
ROLE_RESEARCHER = "researcher"
ROLE_ADMIN = "admin"
ROLES = {ROLE_SME, ROLE_RESEARCHER, ROLE_ADMIN}


class User(UUIDPKMixin, TimestampMixin, UpdatedAtMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=ROLE_SME, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Bumped on password change, sign-out of every session, role change and deactivation. A token carries the value it was issued under
    # and is rejected as soon as it no longer matches, so a signed token cannot outlive a privilege or credential change.
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
