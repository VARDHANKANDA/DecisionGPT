from datetime import date

from sqlalchemy import Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class MarketingCampaign(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "marketing_campaigns"

    campaign_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(100), nullable=False)
    campaign_name: Mapped[str | None] = mapped_column(String(255))
    spend: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    impressions: Mapped[int | None] = mapped_column(Integer)
    clicks: Mapped[int | None] = mapped_column(Integer)
    conversions: Mapped[int | None] = mapped_column(Integer)
    attributed_revenue: Mapped[float | None] = mapped_column(Numeric(14, 2))
