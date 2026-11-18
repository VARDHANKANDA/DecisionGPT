"""outcome tracking: uniqueness that makes retries and double clicks safe

* one response row per (decision, seq): two concurrent submissions cannot both become the same revision;
* one CURRENT observation per (expectation, metric, window).

Existing rows written by the 0011 service already satisfy both (seq increments and a correction flips ``is_current`` first).

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("uq_decision_responses_decision_seq", "decision_responses", ["decision_id", "seq"], unique=True)
    op.create_index(
        "uq_outcome_observations_current_window", "outcome_observations", ["expectation_id", "metric", "window_start", "window_end"],
        unique=True, sqlite_where=sa.text("is_current = 1"), postgresql_where=sa.text("is_current"),
    )


def downgrade() -> None:
    op.drop_index("uq_outcome_observations_current_window", table_name="outcome_observations")
    op.drop_index("uq_decision_responses_decision_seq", table_name="decision_responses")
