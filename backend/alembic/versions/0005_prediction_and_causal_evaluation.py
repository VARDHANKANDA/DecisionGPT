"""prediction_evaluations + causal_evidence_updates (research feedback loop)

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid():
    return postgresql.UUID(as_uuid=False)


def upgrade() -> None:
    op.create_table(
        "prediction_evaluations",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("business_id", _uuid(), nullable=False),
        sa.Column("decision_id", _uuid(), sa.ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outcome_id", _uuid(), sa.ForeignKey("decision_outcomes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("simulation_id", _uuid()),
        sa.Column("strategy_id", _uuid()),
        sa.Column("strategy_name", sa.String(255)),
        sa.Column("method", sa.String(80), nullable=False),
        sa.Column("causal_graph_version", sa.String(50)),
        sa.Column("model_versions_json", sa.JSON(), nullable=False),
        sa.Column("dataset_version", sa.String(120)),
        sa.Column("predicted_revenue_change", sa.Numeric(16, 2)),
        sa.Column("actual_revenue_change", sa.Numeric(16, 2)),
        sa.Column("revenue_error", sa.Numeric(16, 2)),
        sa.Column("revenue_abs_pct_error", sa.Numeric(10, 4)),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_prediction_evaluations_business_id", "prediction_evaluations", ["business_id"])
    op.create_index("ix_prediction_evaluations_decision_id", "prediction_evaluations", ["decision_id"])
    op.create_index(
        "ix_prediction_evaluations_outcome_id", "prediction_evaluations", ["outcome_id"], unique=True
    )

    op.create_table(
        "causal_evidence_updates",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("business_id", _uuid(), nullable=False),
        sa.Column("causal_graph_id", _uuid(), nullable=False),
        sa.Column("graph_version", sa.String(50), nullable=False),
        sa.Column("source_node", sa.String(100), nullable=False),
        sa.Column("target_node", sa.String(100), nullable=False),
        sa.Column("previous_evidence", sa.String(30), nullable=False),
        sa.Column("new_evidence", sa.String(30), nullable=False),
        sa.Column("method", sa.String(80), nullable=False),
        sa.Column("rationale", sa.Text()),
        sa.Column("supporting_decision_ids_json", sa.JSON(), nullable=False),
        sa.Column("supporting_outcome_ids_json", sa.JSON(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consistent_direction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_causal_evidence_updates_business_id", "causal_evidence_updates", ["business_id"])
    op.create_index("ix_causal_evidence_updates_causal_graph_id", "causal_evidence_updates", ["causal_graph_id"])


def downgrade() -> None:
    op.drop_table("causal_evidence_updates")
    op.drop_table("prediction_evaluations")
