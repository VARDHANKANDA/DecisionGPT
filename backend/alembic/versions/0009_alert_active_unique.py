"""one active alert per condition

Adds a partial unique index so the same condition can never have two active (open/read) alerts, even if two checks run at once.
Any duplicates already stored are first marked 'cleared' (the earliest one is kept), so the index can be created.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACTIVE = sa.text("status IN ('open', 'read')")


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, business_id, dedupe_key, created_at FROM alerts WHERE status IN ('open', 'read') ORDER BY business_id, dedupe_key, created_at, id")).fetchall()
    seen: set[tuple[str, str]] = set()
    for rid, bid, key, _ in rows:
        if (bid, key) in seen:
            bind.execute(sa.text("UPDATE alerts SET status = 'cleared' WHERE id = :i"), {"i": rid})
        else:
            seen.add((bid, key))
    op.create_index("uq_alert_active_dedupe", "alerts", ["business_id", "dedupe_key"], unique=True, sqlite_where=_ACTIVE, postgresql_where=_ACTIVE)


def downgrade() -> None:
    op.drop_index("uq_alert_active_dedupe", table_name="alerts")
