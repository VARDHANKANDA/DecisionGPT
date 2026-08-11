from datetime import date

from sqlalchemy import Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class Customer(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    external_customer_id: Mapped[str | None] = mapped_column(String(100), index=True)
    segment: Mapped[str | None] = mapped_column(String(100))
    first_purchase_date: Mapped[date | None] = mapped_column(Date)
    last_purchase_date: Mapped[date | None] = mapped_column(Date)
    purchase_frequency: Mapped[float | None] = mapped_column(Numeric(10, 2))
    monetary_value: Mapped[float | None] = mapped_column(Numeric(14, 2))
    churn_probability: Mapped[float | None] = mapped_column(Numeric(5, 4))
