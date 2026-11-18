"""indian SME data layer: business-profile context + finance_records

Adds optional Indian business-profile columns to ``businesses`` and a new
``finance_records`` table (docs/INDIAN_SME_DATA_ARCHITECTURE.md). Purely
additive; every new column is nullable. No existing column or table changes.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid():
    return postgresql.UUID(as_uuid=False)


_PROFILE_COLUMNS = [
    ("state", sa.String(100)),
    ("district", sa.String(100)),
    ("city", sa.String(100)),
    ("enterprise_type", sa.String(50)),
    ("organisation_type", sa.String(100)),
    ("major_activity", sa.String(100)),
    ("nic_code", sa.String(20)),
    ("registration_date", sa.Date()),
    ("business_age_years", sa.Integer()),
]


def upgrade() -> None:
    # batch_alter_table so SQLite (dev / tests) can ALTER columns in too.
    with op.batch_alter_table("businesses") as batch:
        for name, col_type in _PROFILE_COLUMNS:
            batch.add_column(sa.Column(name, col_type, nullable=True))

    op.create_table(
        "finance_records",
        sa.Column("id", _uuid(), primary_key=True),
        sa.Column(
            "business_id",
            _uuid(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("revenue", sa.Numeric(18, 2)),
        sa.Column("cogs", sa.Numeric(18, 2)),
        sa.Column("gross_profit", sa.Numeric(18, 2)),
        sa.Column("operating_expenses", sa.Numeric(18, 2)),
        sa.Column("net_profit", sa.Numeric(18, 2)),
        sa.Column("cash_balance", sa.Numeric(18, 2)),
        sa.Column("accounts_receivable", sa.Numeric(18, 2)),
        sa.Column("accounts_payable", sa.Numeric(18, 2)),
        sa.Column("inventory_value", sa.Numeric(18, 2)),
        sa.Column("loan_amount", sa.Numeric(18, 2)),
        sa.Column("interest_rate", sa.Numeric(8, 4)),
        sa.Column("emi", sa.Numeric(18, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_finance_records_business_id", "finance_records", ["business_id"])
    op.create_index("ix_finance_records_period_date", "finance_records", ["period_date"])


def downgrade() -> None:
    op.drop_table("finance_records")
    with op.batch_alter_table("businesses") as batch:
        for name, _ in reversed(_PROFILE_COLUMNS):
            batch.drop_column(name)
