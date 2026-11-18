"""outcome tracking: forecast fingerprint column with a partial unique index

A forecast snapshot is identified by the fingerprint of the forecast that was shown. It was kept only inside ``config_json``, so two
simultaneous saves of the same forecast could both insert. The fingerprint becomes a column with a partial unique index per business.

Existing rows are backfilled from ``config_json.fingerprint``. If a business somehow holds two snapshots with the same fingerprint, the
earliest keeps the value and the later ones keep NULL (they stay readable; nothing is deleted or merged).

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-16
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tracked_expectations", sa.Column("fingerprint", sa.String(64), nullable=True))
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, business_id, config_json FROM tracked_expectations WHERE source_kind = 'forecast' ORDER BY created_at, id"
    )).fetchall()
    seen: set[tuple[str, str]] = set()
    for rid, business_id, cfg in rows:
        try:
            data = json.loads(cfg) if isinstance(cfg, (str, bytes)) else (cfg or {})
        except ValueError:
            continue
        fp = (data or {}).get("fingerprint")
        if not fp or (str(business_id), fp) in seen:
            continue
        seen.add((str(business_id), fp))
        bind.execute(sa.text("UPDATE tracked_expectations SET fingerprint = :fp WHERE id = :id"), {"fp": fp, "id": rid})
    op.create_index(
        "uq_tracked_expectations_forecast_fingerprint", "tracked_expectations", ["business_id", "fingerprint"], unique=True,
        sqlite_where=sa.text("fingerprint IS NOT NULL"), postgresql_where=sa.text("fingerprint IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_tracked_expectations_forecast_fingerprint", table_name="tracked_expectations")
    op.drop_column("tracked_expectations", "fingerprint")
