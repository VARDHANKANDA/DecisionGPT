from sqlalchemy import JSON, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin, UpdatedAtMixin


class Goal(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, UpdatedAtMixin, Base):
    __tablename__ = "goals"

    objective: Mapped[str] = mapped_column(String(100), nullable=False)
    target_value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    target_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    primary_kpi: Mapped[str] = mapped_column(String(50), nullable=False)
    time_horizon: Mapped[int | None] = mapped_column(Integer)
    constraints_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
