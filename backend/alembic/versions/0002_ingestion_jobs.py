"""add data_ingestion_jobs table

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_ingestion_jobs",
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("detected_types_json", sa.JSON(), nullable=False),
        sa.Column("mapping_json", sa.JSON(), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_data_ingestion_jobs_business_id", "data_ingestion_jobs", ["business_id"])
    op.create_index("ix_data_ingestion_jobs_status", "data_ingestion_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("data_ingestion_jobs")
