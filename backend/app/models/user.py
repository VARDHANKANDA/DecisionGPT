"""User accounts + roles (Phase 4 — Security & Access).

Two roles:
  - ``sme``   : an SME operator. Can only touch businesses they own.
  - ``admin`` : a researcher/platform admin. Can reach the Research Console
                (datasets, training, experiments) but has no automatic
                access to any SME's business data.
"""
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import TimestampMixin, UpdatedAtMixin, UUIDPKMixin

ROLE_SME = "sme"
ROLE_ADMIN = "admin"
ROLES = {ROLE_SME, ROLE_ADMIN}


class User(UUIDPKMixin, TimestampMixin, UpdatedAtMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=ROLE_SME, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
