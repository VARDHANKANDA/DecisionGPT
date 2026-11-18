from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import GUID
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class Forecast(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "forecasts"

    model_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("models.id", ondelete="SET NULL"), index=True
    )
    forecast_type: Mapped[str] = mapped_column(String(50), nullable=False)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    predicted_value: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    lower_bound: Mapped[float | None] = mapped_column(Numeric(14, 4))
    upper_bound: Mapped[float | None] = mapped_column(Numeric(14, 4))
