"""authentication state: token versions, revoked tokens, rate-limit counters

* ``users.token_version``: a token is accepted only while the version it carries equals the user's current version, so a password change,
  a sign-out of every session, a role change or a deactivation invalidates tokens already issued.
* ``revoked_tokens``: token ids refused although signature and expiry are valid (explicit logout). Rows are pruned after expiry.
* ``rate_limit_buckets``: fixed-window counters for sign-in, sign-up and password-change protection, shared by every worker and replica.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(64), primary_key=True),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_revoked_tokens_expires_at", "revoked_tokens", ["expires_at"])
    op.create_table(
        "rate_limit_buckets",
        sa.Column("key", sa.String(160), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rate_limit_buckets_expires_at", "rate_limit_buckets", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_rate_limit_buckets_expires_at", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
    op.drop_index("ix_revoked_tokens_expires_at", table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("token_version")
