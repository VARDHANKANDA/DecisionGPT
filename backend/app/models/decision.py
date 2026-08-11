from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import GUID
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class Decision(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "decisions"

    goal_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selected_strategy_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("strategies.id", ondelete="SET NULL")
    )
    expected_outcome_json: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 4))
    reasoning: Mapped[str | None] = mapped_column(Text)
    causal_graph_version: Mapped[str | None] = mapped_column(String(50))


class DecisionOutcome(UUIDPKMixin, Base):
    __tablename__ = "decision_outcomes"

    decision_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actual_outcome_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    goal_achieved: Mapped[bool | None] = mapped_column(Boolean)
    goal_achievement_score: Mapped[float | None] = mapped_column(Numeric(6, 4))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
