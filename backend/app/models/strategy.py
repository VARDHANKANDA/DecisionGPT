from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import GUID
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class Strategy(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "strategies"

    goal_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    strategy_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    actions_json: Mapped[list] = mapped_column(JSON, default=list)
