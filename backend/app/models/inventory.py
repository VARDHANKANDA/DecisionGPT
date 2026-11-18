from datetime import date

from sqlalchemy import Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import GUID
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class InventoryRecord(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "inventory"

    product_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    stock_level: Mapped[int] = mapped_column(Integer, nullable=False)
    reorder_level: Mapped[int | None] = mapped_column(Integer)
