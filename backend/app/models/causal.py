from sqlalchemy import JSON, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import GUID
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class CausalGraph(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "causal_graphs"

    version: Mapped[str] = mapped_column(String(50), nullable=False)
    graph_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    method: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_summary: Mapped[str | None] = mapped_column(Text)


class CausalEdge(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "causal_edges"

    causal_graph_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("causal_graphs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_node: Mapped[str] = mapped_column(String(100), nullable=False)
    target_node: Mapped[str] = mapped_column(String(100), nullable=False)
    relationship: Mapped[str] = mapped_column(String(20), nullable=False)  # positive | negative
    strength: Mapped[float | None] = mapped_column(Numeric(6, 4))
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 4))
    evidence_type: Mapped[str] = mapped_column(String(30), nullable=False)
    time_lag: Mapped[int | None] = mapped_column(Integer)
