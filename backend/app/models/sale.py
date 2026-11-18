from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import GUID
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class Sale(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "sales"

    customer_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("customers.id", ondelete="SET NULL"), index=True
    )
    product_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    sale_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    discount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    revenue: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
