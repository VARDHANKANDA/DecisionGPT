from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin, UpdatedAtMixin


class Product(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, UpdatedAtMixin, Base):
    __tablename__ = "products"

    external_product_id: Mapped[str | None] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    unit_cost: Mapped[float | None] = mapped_column(Numeric(12, 2))
    selling_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    stock_quantity: Mapped[int | None] = mapped_column(Integer)
