from sqlalchemy import JSON, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import GUID
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class AgentRun(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"

    decision_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("decisions.id", ondelete="CASCADE"), index=True
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)


class AgentEvaluation(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "agent_evaluations"

    strategy_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    evaluation_json: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[float | None] = mapped_column(Numeric(6, 4))
    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
