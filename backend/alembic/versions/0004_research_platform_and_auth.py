"""research platform (datasets/training) + model & experiment lifecycle + users/auth

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid():
    return postgresql.UUID(as_uuid=False)


def upgrade() -> None:
    # --- users -------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("role", sa.String(20), nullable=False, server_default="sme"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    # batch_alter_table so SQLite (dev / tests) can ALTER in a column that
    # carries a FK constraint; on PostgreSQL this is a plain ALTER. The FK
    # must be named for SQLite batch mode.
    with op.batch_alter_table("businesses") as batch:
        batch.add_column(sa.Column("owner_user_id", _uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_businesses_owner_user_id", "users", ["owner_user_id"], ["id"], ondelete="SET NULL"
        )
    op.create_index("ix_businesses_owner_user_id", "businesses", ["owner_user_id"])

    # --- research datasets ----------------------------------------------
    op.create_table(
        "research_datasets",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("dataset_id", sa.String(120), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("domain", sa.String(60), nullable=False),
        sa.Column("source", sa.String(255)),
        sa.Column("license", sa.String(120)),
        sa.Column("created_by", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_research_datasets_dataset_id", "research_datasets", ["dataset_id"], unique=True)
    op.create_index("ix_research_datasets_domain", "research_datasets", ["domain"])

    op.create_table(
        "research_dataset_versions",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("dataset_id", _uuid(), sa.ForeignKey("research_datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("file_type", sa.String(16), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("column_count", sa.Integer(), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("missing_summary_json", sa.JSON(), nullable=False),
        sa.Column("duplicates_summary_json", sa.JSON(), nullable=False),
        sa.Column("quality_report_json", sa.JSON(), nullable=False),
        sa.Column("validation_ok", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_research_dataset_versions_dataset_id", "research_dataset_versions", ["dataset_id"]
    )

    # --- training runs -------------------------------------------------
    op.create_table(
        "training_runs",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column("dataset_version_id", _uuid(), sa.ForeignKey("research_dataset_versions.id", ondelete="SET NULL")),
        sa.Column("platform_domain", sa.String(60)),
        sa.Column("dataset_version_label", sa.String(120)),
        sa.Column("task", sa.String(40), nullable=False),
        sa.Column("model_type", sa.String(60), nullable=False),
        sa.Column("features_json", sa.JSON(), nullable=False),
        sa.Column("target", sa.String(60)),
        sa.Column("parameters_json", sa.JSON(), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=False, server_default="42"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("model_id", _uuid(), sa.ForeignKey("models.id", ondelete="SET NULL")),
        sa.Column("model_name", sa.String(100)),
        sa.Column("model_version", sa.String(50)),
        sa.Column("artifact_path", sa.String(500)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_by", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_training_runs_task", "training_runs", ["task"])
    op.create_index("ix_training_runs_status", "training_runs", ["status"])

    # --- model registry lifecycle columns ----------------------------
    op.add_column("models", sa.Column("task", sa.String(40), nullable=True))
    op.add_column("models", sa.Column("features_json", sa.JSON(), nullable=True))
    op.add_column("models", sa.Column("training_run_id", sa.String(36), nullable=True))
    op.add_column("models", sa.Column("source", sa.String(40), nullable=True))
    op.add_column("models", sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True))

    # --- experiment runner lifecycle columns -----------------------
    op.add_column("experiment_runs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("experiment_runs", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("experiment_runs", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("experiment_runs", sa.Column("model_versions_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    for col in ("model_versions_json", "error_message", "completed_at", "started_at"):
        op.drop_column("experiment_runs", col)
    for col in ("promoted_at", "source", "training_run_id", "features_json", "task"):
        op.drop_column("models", col)
    op.drop_table("training_runs")
    op.drop_table("research_dataset_versions")
    op.drop_table("research_datasets")
    op.drop_index("ix_businesses_owner_user_id", "businesses")
    with op.batch_alter_table("businesses") as batch:
        batch.drop_constraint("fk_businesses_owner_user_id", type_="foreignkey")
        batch.drop_column("owner_user_id")
    op.drop_table("users")
