"""sync production demo users

Synchronizes the three institutional demo user accounts (Admin, Researcher, SME)
into the users table with exact IDs, roles, and Argon2id password hashes.
Strictly idempotent: checks if the account email/ID exists and does not overwrite existing users.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-19
"""
from typing import Sequence, Union
import datetime

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID
from app.services.account_sync_service import CANONICAL_DEMO_ACCOUNTS

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.datetime.now(datetime.timezone.utc)

    # Query existing user emails and ids
    existing = bind.execute(sa.text("SELECT id, email FROM users")).fetchall()
    existing_emails = {row[1].lower() for row in existing if row[1]}
    existing_ids = {str(row[0]).lower() for row in existing if row[0]}

    users_table = sa.table(
        "users",
        sa.column("id", GUID()),
        sa.column("email", sa.String(255)),
        sa.column("password_hash", sa.String(255)),
        sa.column("full_name", sa.String(255)),
        sa.column("role", sa.String(20)),
        sa.column("is_active", sa.Boolean()),
        sa.column("token_version", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    for email, data in CANONICAL_DEMO_ACCOUNTS.items():
        if email.lower() not in existing_emails and data["id"].lower() not in existing_ids:
            op.bulk_insert(
                users_table,
                [
                    {
                        "id": data["id"],
                        "email": data["email"],
                        "password_hash": data["password_hash"],
                        "full_name": data["full_name"],
                        "role": data["role"],
                        "is_active": data["is_active"],
                        "token_version": data["token_version"],
                        "created_at": now,
                        "updated_at": now,
                    }
                ],
            )


def downgrade() -> None:
    # Non-destructive downgrade: preserve accounts so credentials and test records are never lost
    pass
