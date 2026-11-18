"""business uploads: identity and storage key of the original file

* ``file_sha256`` / ``file_size``: recognise the same file uploaded twice (confirmed by the person, never silently doubled) and show what was read.
* ``storage_key``: where the unchanged original upload is kept, so a mapping that needs confirmation can be resumed from the original instead of
  from a copy of every row in a JSON column, and the cleaned tables stay traceable to what was actually uploaded.

Additive and nullable: existing jobs are unaffected.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("data_ingestion_jobs", sa.Column("file_sha256", sa.String(64), nullable=True))
    op.add_column("data_ingestion_jobs", sa.Column("file_size", sa.Integer(), nullable=True))
    op.add_column("data_ingestion_jobs", sa.Column("storage_key", sa.String(300), nullable=True))
    op.create_index("ix_data_ingestion_jobs_file_sha256", "data_ingestion_jobs", ["file_sha256"])


def downgrade() -> None:
    op.drop_index("ix_data_ingestion_jobs_file_sha256", table_name="data_ingestion_jobs")
    with op.batch_alter_table("data_ingestion_jobs") as batch:
        batch.drop_column("storage_key")
        batch.drop_column("file_size")
        batch.drop_column("file_sha256")
