from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import TimestampMixin, UUIDPKMixin


class MarketBenchmark(UUIDPKMixin, TimestampMixin, Base):
    """Public/aggregated Indian market benchmarks — never derived from a
    single business's private data. See docs/DATA_SPECIFICATION.md §9."""

    __tablename__ = "market_benchmarks"

    industry: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    business_size: Mapped[str] = mapped_column(String(50), nullable=False)
    metric: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    median_value: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    lower_quartile: Mapped[float | None] = mapped_column(Numeric(14, 4))
    upper_quartile: Mapped[float | None] = mapped_column(Numeric(14, 4))
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))
    evidence_level: Mapped[str] = mapped_column(String(30), nullable=False)
