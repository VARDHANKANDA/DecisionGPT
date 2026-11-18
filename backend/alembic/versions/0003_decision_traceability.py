"""add decision traceability columns + agent_evaluations.prompt/model columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-26

Adds the full reproducible-trace fields to `decisions`
(docs/RESEARCH_TRACEABILITY.md "Required Metadata") plus the
digital_twin_simulations.strategy_id link. All new columns are nullable so
existing rows keep loading.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DECISION_COLUMNS = [
    ("business_state_version", sa.String(64)),
    ("business_state_json", sa.JSON()),
    ("candidate_strategy_ids_json", sa.JSON()),
    ("simulation_ids_json", sa.JSON()),
    ("agent_run_ids_json", sa.JSON()),
    ("model_versions_json", sa.JSON()),
    ("assumptions_json", sa.JSON()),
    ("uncertainty_json", sa.JSON()),
    ("causal_context_json", sa.JSON()),
    ("debate_json", sa.JSON()),
    ("strategy_generation_json", sa.JSON()),
    ("prompt_version", sa.String(50)),
]


def upgrade() -> None:
    for name, col_type in _DECISION_COLUMNS:
        op.add_column("decisions", sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(_DECISION_COLUMNS):
        op.drop_column("decisions", name)
