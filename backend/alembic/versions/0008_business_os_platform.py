"""business operating system tables: KPI targets, alerts, saved reports, health snapshots, data-prep runs, analysis runs

Purely additive: seven new business-scoped tables, no change to an existing table, column or behaviour. No backfill is needed — an
existing business simply has no targets, alerts, reports, snapshots, runs or analyses until it creates them.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base(name: str, *cols: sa.Column, uniques: tuple = ()) -> None:
    op.create_table(
        name,
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("business_id", GUID(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        *cols,
        *uniques,
    )


def upgrade() -> None:
    _base(
        "kpi_targets",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kpi_key", sa.String(60), nullable=False),
        sa.Column("target_value", sa.Float(), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("period_days", sa.Integer(), nullable=False),
        uniques=(sa.UniqueConstraint("business_id", "kpi_key", name="uq_kpi_target_business_key"),),
    )
    _base(
        "alert_rules",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rule_key", sa.String(60), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        uniques=(sa.UniqueConstraint("business_id", "rule_key", name="uq_alert_rule_business_key"),),
    )
    _base(
        "alerts",
        sa.Column("rule_key", sa.String(60), nullable=False, index=True),
        sa.Column("dedupe_key", sa.String(200), nullable=False, index=True),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    _base(
        "saved_reports",
        sa.Column("report_type", sa.String(40), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("scope_json", sa.JSON(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
    )
    _base(
        "health_snapshots",
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("period_days", sa.Integer(), nullable=False),
        sa.Column("available_weight", sa.Float(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
    )
    _base(
        "data_prep_runs",
        sa.Column("stage", sa.String(20), nullable=False, index=True),
        sa.Column("table_type", sa.String(40), nullable=True),
        sa.Column("operation", sa.String(60), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("undo_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    _base(
        "analysis_runs",
        sa.Column("kind", sa.String(20), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(30), nullable=True),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("params_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    for name in ("analysis_runs", "data_prep_runs", "health_snapshots", "saved_reports", "alerts", "alert_rules", "kpi_targets"):
        op.drop_table(name)
