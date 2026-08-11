from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class BusinessMemory(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "business_memory"

    memory_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
