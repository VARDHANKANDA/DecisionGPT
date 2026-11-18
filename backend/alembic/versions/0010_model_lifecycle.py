"""model lifecycle: candidate/validated states, promotion log

Adds ``models.lifecycle_json`` and the append-only ``model_lifecycle_events`` table. Existing rows keep their status; the
file-registry sync no longer activates a later version automatically (see model_registry_service).

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("models", sa.Column("lifecycle_json", sa.JSON(), nullable=True))
    op.create_table(
        "model_lifecycle_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model_id", sa.String(36), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("event", sa.String(40), nullable=False),
        sa.Column("from_status", sa.String(30), nullable=True),
        sa.Column("to_status", sa.String(30), nullable=True),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_model_lifecycle_events_seq", "model_lifecycle_events", ["seq"])
    op.create_index("ix_model_lifecycle_events_model_id", "model_lifecycle_events", ["model_id"])
    op.create_index("ix_model_lifecycle_events_model_name", "model_lifecycle_events", ["model_name"])
    op.create_index("ix_model_lifecycle_events_event", "model_lifecycle_events", ["event"])


def downgrade() -> None:
    op.drop_index("ix_model_lifecycle_events_event", table_name="model_lifecycle_events")
    op.drop_index("ix_model_lifecycle_events_model_name", table_name="model_lifecycle_events")
    op.drop_index("ix_model_lifecycle_events_model_id", table_name="model_lifecycle_events")
    op.drop_index("ix_model_lifecycle_events_seq", table_name="model_lifecycle_events")
    op.drop_table("model_lifecycle_events")
    op.drop_column("models", "lifecycle_json")
