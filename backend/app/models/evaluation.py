"""Research-side evaluation records.

- ``PredictionEvaluation``: one row per recorded DecisionOutcome, comparing
  what the Digital Twin predicted for the chosen strategy against what the
  SME actually reported. Written by the feedback loop in
  ``memory_service.record_outcome`` (docs Phase 3). Fully traceable:
  keeps decision / outcome / simulation / graph-version / model-version
  references so the Research Dashboard never has to re-derive anything.

- ``CausalEvidenceUpdate``: an append-only log of every conservative
  evidence-level change made to a causal edge from real outcome feedback
  (docs Phase 5). One real outcome never proves causation, so this
  mechanism only ever moves an edge ASSUMED -> OBSERVATIONAL, and records
  exactly which decisions/outcomes and which method justified it.
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import GUID
from app.models.common import TimestampMixin, UUIDPKMixin

PREDICTION_EVAL_METHOD = "revenue_change_vs_recorded_outcome_v1"
CAUSAL_FEEDBACK_METHOD = "outcome_direction_consistency_v1"


class PredictionEvaluation(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "prediction_evaluations"

    business_id: Mapped[str] = mapped_column(GUID(), index=True, nullable=False)
    decision_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("decisions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    outcome_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("decision_outcomes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    simulation_id: Mapped[str | None] = mapped_column(GUID())
    strategy_id: Mapped[str | None] = mapped_column(GUID())
    strategy_name: Mapped[str | None] = mapped_column(String(255))

    method: Mapped[str] = mapped_column(String(80), nullable=False, default=PREDICTION_EVAL_METHOD)
    causal_graph_version: Mapped[str | None] = mapped_column(String(50))
    model_versions_json: Mapped[dict] = mapped_column(JSON, default=dict)
    dataset_version: Mapped[str | None] = mapped_column(String(120))

    # Denormalised primary error (revenue change) for cheap aggregation.
    predicted_revenue_change: Mapped[float | None] = mapped_column(Numeric(16, 2))
    actual_revenue_change: Mapped[float | None] = mapped_column(Numeric(16, 2))
    revenue_error: Mapped[float | None] = mapped_column(Numeric(16, 2))
    revenue_abs_pct_error: Mapped[float | None] = mapped_column(Numeric(10, 4))

    # Per-metric detail (revenue / profit / units): predicted_baseline,
    # predicted, actual, error, pct_error — whichever the decision + outcome
    # both support.
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CausalEvidenceUpdate(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "causal_evidence_updates"

    business_id: Mapped[str] = mapped_column(GUID(), index=True, nullable=False)
    causal_graph_id: Mapped[str] = mapped_column(GUID(), index=True, nullable=False)
    graph_version: Mapped[str] = mapped_column(String(50), nullable=False)
    source_node: Mapped[str] = mapped_column(String(100), nullable=False)
    target_node: Mapped[str] = mapped_column(String(100), nullable=False)

    previous_evidence: Mapped[str] = mapped_column(String(30), nullable=False)
    new_evidence: Mapped[str] = mapped_column(String(30), nullable=False)
    method: Mapped[str] = mapped_column(String(80), nullable=False, default=CAUSAL_FEEDBACK_METHOD)
    rationale: Mapped[str | None] = mapped_column(Text)

    supporting_decision_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    supporting_outcome_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    consistent_direction_count: Mapped[int] = mapped_column(Integer, default=0)
