"""outcome tracking: expectations, decision responses, observations (append-only)

Adds three business-scoped tables beside ``decisions``; no existing table is altered, so a database at 0010 upgrades without touching data.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base() -> list:
    return [
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("business_id", GUID(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True),
    ]


def upgrade() -> None:
    op.create_table(
        "tracked_expectations", *_base(),
        sa.Column("source_kind", sa.String(20), nullable=False, index=True),
        sa.Column("decision_id", GUID(), sa.ForeignKey("decisions.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("metric", sa.String(30), nullable=False, index=True),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("scope", sa.String(30), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("data_cutoff", sa.Date(), nullable=True),
        sa.Column("expected_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("points_json", sa.JSON(), nullable=True),
        sa.Column("interval_reliable", sa.Boolean(), nullable=True),
        sa.Column("interval_method", sa.String(80), nullable=True),
        sa.Column("method", sa.String(80), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("basis", sa.String(40), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("reference_json", sa.JSON(), nullable=True),
        sa.Column("assumptions_json", sa.JSON(), nullable=True),
        sa.Column("limitations_json", sa.JSON(), nullable=True),
        sa.Column("comparable_to_actuals", sa.Boolean(), nullable=False),
        sa.Column("comparability_reason", sa.Text(), nullable=True),
        sa.Column("input_sha256", sa.String(64), nullable=True),
        sa.Column("provenance", sa.String(30), nullable=False),
    )
    op.create_table(
        "decision_responses", *_base(),
        sa.Column("decision_id", GUID(), sa.ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("response", sa.String(20), nullable=False),
        sa.Column("action_status", sa.String(24), nullable=False),
        sa.Column("action_taken_json", sa.JSON(), nullable=True),
        sa.Column("modified_action_json", sa.JSON(), nullable=True),
        sa.Column("action_start", sa.Date(), nullable=True),
        sa.Column("action_end", sa.Date(), nullable=True),
        sa.Column("known_changes_json", sa.JSON(), nullable=True),
        sa.Column("evaluation_design", sa.String(20), nullable=False),
        sa.Column("follow_up_date", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.String(120), nullable=True),
    )
    op.create_table(
        "outcome_observations", *_base(),
        sa.Column("expectation_id", GUID(), sa.ForeignKey("tracked_expectations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("metric", sa.String(30), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("scope", sa.String(30), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("unavailable_reason", sa.Text(), nullable=True),
        sa.Column("covered_until", sa.Date(), nullable=True),
        sa.Column("coverage_days", sa.Integer(), nullable=True),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("provenance", sa.String(30), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", GUID(), nullable=True),
        sa.Column("revision_reason", sa.Text(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, index=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.String(120), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("outcome_observations")
    op.drop_table("decision_responses")
    op.drop_table("tracked_expectations")
