from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import GUID
from app.models.common import TimestampMixin, UUIDPKMixin, UpdatedAtMixin


class Business(UUIDPKMixin, TimestampMixin, UpdatedAtMixin, Base):
    __tablename__ = "businesses"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=False)
    business_type: Mapped[str] = mapped_column(String(100), nullable=False)
    business_size: Mapped[str] = mapped_column(String(50), nullable=False)
    country: Mapped[str] = mapped_column(String(2), default="IN")
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Indian business-profile context (docs/INDIAN_SME_DATA_ARCHITECTURE.md).
    # All optional; used only to condition recommendations, never to invent data.
    state: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100))
    enterprise_type: Mapped[str | None] = mapped_column(String(50))  # Micro / Small / Medium
    organisation_type: Mapped[str | None] = mapped_column(String(100))
    major_activity: Mapped[str | None] = mapped_column(String(100))
    nic_code: Mapped[str | None] = mapped_column(String(20))
    registration_date: Mapped[date | None] = mapped_column(Date)
    business_age_years: Mapped[int | None] = mapped_column(Integer)
    # Owner (Phase 4). Nullable so demo/legacy businesses without an owner
    # still load; access control treats a null owner as "any authenticated
    # SME may claim it on first access" is NOT done — null-owner businesses
    # are only reachable when auth is disabled (tests / local dev).
    owner_user_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
