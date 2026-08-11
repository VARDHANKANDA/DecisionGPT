from sqlalchemy import JSON, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import GUID
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class DigitalTwinState(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "digital_twin_states"

    goal_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("goals.id", ondelete="CASCADE"), index=True
    )
    state_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class DigitalTwinSimulation(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "digital_twin_simulations"

    goal_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("goals.id", ondelete="CASCADE"), index=True
    )
    strategy_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("strategies.id", ondelete="CASCADE"), index=True
    )
    input_state_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    actions_json: Mapped[list] = mapped_column(JSON, default=list)
    output_state_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    risk_score: Mapped[float | None] = mapped_column(Numeric(6, 4))
    model_version: Mapped[str | None] = mapped_column(String(50))
    graph_version: Mapped[str | None] = mapped_column(String(50))
    assumptions_json: Mapped[list] = mapped_column(JSON, default=list)
