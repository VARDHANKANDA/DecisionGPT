"""real Indian SME decision-outcome provenance + horizon capture

Adds optional provenance / horizon / source columns to ``decision_outcomes``
so a genuine (anonymised) Indian SME decision outcome can be recorded with the
metadata the research validation needs (docs/REAL_INDIAN_SME_OUTCOME_VALIDATION.md).
Purely additive; every new column is nullable. No existing column, table or
behaviour changes — the existing ``memory_service.record_outcome`` path is
untouched and older rows load unchanged.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OUTCOME_COLUMNS = [
    ("outcome_horizon_days", sa.Integer()),
    ("outcome_status", sa.String(40)),      # achieved | partially_achieved | not_achieved | inconclusive
    ("notes", sa.Text()),
    ("source_type", sa.String(40)),         # real_indian_sme | synthetic | demo | unknown
    ("business_country", sa.String(8)),
    ("business_industry", sa.String(80)),
    ("data_consent_status", sa.String(40)),
    ("anonymization_status", sa.String(40)),
    ("collection_method", sa.String(60)),
    ("collection_date", sa.Date()),
]


def upgrade() -> None:
    with op.batch_alter_table("decision_outcomes") as batch:
        for name, col_type in _OUTCOME_COLUMNS:
            batch.add_column(sa.Column(name, col_type, nullable=True))
    op.create_index(
        "ix_decision_outcomes_source_type", "decision_outcomes", ["source_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_decision_outcomes_source_type", table_name="decision_outcomes")
    with op.batch_alter_table("decision_outcomes") as batch:
        for name, _ in reversed(_OUTCOME_COLUMNS):
            batch.drop_column(name)
