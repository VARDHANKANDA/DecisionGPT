from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
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

    # --- Full traceability record (docs/RESEARCH_TRACEABILITY.md) -------
    # Every field below lets a stored decision be reproduced and inspected
    # without re-deriving anything. All nullable so older rows still load.
    business_state_version: Mapped[str | None] = mapped_column(String(64))
    business_state_json: Mapped[dict | None] = mapped_column(JSON)
    candidate_strategy_ids_json: Mapped[list | None] = mapped_column(JSON)
    simulation_ids_json: Mapped[list | None] = mapped_column(JSON)
    agent_run_ids_json: Mapped[list | None] = mapped_column(JSON)
    model_versions_json: Mapped[dict | None] = mapped_column(JSON)
    assumptions_json: Mapped[list | None] = mapped_column(JSON)
    uncertainty_json: Mapped[dict | None] = mapped_column(JSON)
    causal_context_json: Mapped[dict | None] = mapped_column(JSON)
    debate_json: Mapped[dict | None] = mapped_column(JSON)
    strategy_generation_json: Mapped[dict | None] = mapped_column(JSON)
    prompt_version: Mapped[str | None] = mapped_column(String(50))


# Recognised outcome sources. Only ``real_indian_sme`` counts as real-world
# evidence for the validation study; everything else is excluded from Table 2.
OUTCOME_SOURCE_REAL_INDIAN_SME = "real_indian_sme"
OUTCOME_SOURCE_SYNTHETIC = "synthetic"
OUTCOME_SOURCE_DEMO = "demo"
OUTCOME_SOURCE_UNKNOWN = "unknown"
REAL_SME_OUTCOME_CATEGORY = "REAL_INDIAN_SME_OUTCOME"


class DecisionOutcome(UUIDPKMixin, Base):
    __tablename__ = "decision_outcomes"

    decision_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actual_outcome_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    goal_achieved: Mapped[bool | None] = mapped_column(Boolean)
    goal_achievement_score: Mapped[float | None] = mapped_column(Numeric(6, 4))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # --- Real-SME outcome provenance / horizon (migration 0007) --------
    # All nullable; populated only for records imported through the real
    # Indian SME outcome workflow. The existing record_outcome() path leaves
    # them None and is unaffected.
    outcome_horizon_days: Mapped[int | None] = mapped_column(Integer)
    outcome_status: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(String(40), index=True)
    business_country: Mapped[str | None] = mapped_column(String(8))
    business_industry: Mapped[str | None] = mapped_column(String(80))
    data_consent_status: Mapped[str | None] = mapped_column(String(40))
    anonymization_status: Mapped[str | None] = mapped_column(String(40))
    collection_method: Mapped[str | None] = mapped_column(String(60))
    collection_date: Mapped[date | None] = mapped_column(Date)
