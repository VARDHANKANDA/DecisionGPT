from sqlalchemy import ForeignKey, String, Text
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
    # Owner (Phase 4). Nullable so demo/legacy businesses without an owner
    # still load; access control treats a null owner as "any authenticated
    # SME may claim it on first access" is NOT done — null-owner businesses
    # are only reachable when auth is disabled (tests / local dev).
    owner_user_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
