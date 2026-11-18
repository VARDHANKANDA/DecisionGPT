"""outcome tracking: database-level append-only protection for historical records

The application already refuses to change saved snapshots, responses and observations (``app/models/tracking.py``), but that guard does not
apply to raw SQL or to another client of the database. These triggers enforce the same rule inside the database:

* ``tracked_expectations``: no UPDATE at all (a saved snapshot or expectation is never edited);
* ``decision_responses``: no UPDATE at all (a change of mind is a new revision);
* ``outcome_observations``: the only permitted UPDATE flips ``is_current`` from true to false on a superseded revision, with every other
  column unchanged (this is what a correction does).

DELETE is deliberately NOT blocked: rows must disappear when their business is deleted (``ON DELETE CASCADE``), and a database administrator
can always remove data. See docs/PRODUCTION_SECURITY_REVIEW.md for the threat model. A migration that must rewrite these tables has to drop the
triggers first and recreate them.

Dialects: SQLite (exercised by the test suite) and PostgreSQL (written for production; NOT executed in this repository's test environment:
verify on a staging PostgreSQL before relying on it).

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-16
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OBSERVATION_COLUMNS = [
    "id", "created_at", "business_id", "expectation_id", "metric", "unit", "scope", "window_start", "window_end", "value", "status",
    "unavailable_reason", "covered_until", "coverage_days", "window_days", "source", "provenance", "revision", "supersedes_id",
    "revision_reason", "note", "recorded_by",
]


def _sqlite_upgrade() -> None:
    for table in ("tracked_expectations", "decision_responses"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only: saved records cannot be changed'); END"
        )
    unchanged = " AND ".join(f"NEW.{c} IS OLD.{c}" for c in OBSERVATION_COLUMNS)
    op.execute(
        "CREATE TRIGGER trg_outcome_observations_append_only BEFORE UPDATE ON outcome_observations "
        f"WHEN NOT (OLD.is_current = 1 AND NEW.is_current = 0 AND {unchanged}) "
        "BEGIN SELECT RAISE(ABORT, 'outcome_observations is append-only: only the current flag of a superseded revision may change'); END"
    )


def _postgres_upgrade() -> None:
    op.execute(
        "CREATE OR REPLACE FUNCTION decisiongpt_block_update() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN RAISE EXCEPTION '% is append-only: saved records cannot be changed', TG_TABLE_NAME "
        "USING ERRCODE = 'integrity_constraint_violation'; END $$"
    )
    for table in ("tracked_expectations", "decision_responses"):
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION decisiongpt_block_update()"
        )
    op.execute(
        "CREATE OR REPLACE FUNCTION decisiongpt_observation_update_guard() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN IF OLD.is_current AND NOT NEW.is_current AND (to_jsonb(NEW) - 'is_current') = (to_jsonb(OLD) - 'is_current') THEN RETURN NEW; END IF; "
        "RAISE EXCEPTION 'outcome_observations is append-only: only the current flag of a superseded revision may change' "
        "USING ERRCODE = 'integrity_constraint_violation'; END $$"
    )
    op.execute(
        "CREATE TRIGGER outcome_observations_append_only BEFORE UPDATE ON outcome_observations FOR EACH ROW "
        "EXECUTE FUNCTION decisiongpt_observation_update_guard()"
    )


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        _sqlite_upgrade()
    elif dialect == "postgresql":
        _postgres_upgrade()
    # other engines are not supported for production; the application-level guard still applies


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for t in ("trg_tracked_expectations_append_only", "trg_decision_responses_append_only", "trg_outcome_observations_append_only"):
            op.execute(f"DROP TRIGGER IF EXISTS {t}")
    elif dialect == "postgresql":
        for table in ("tracked_expectations", "decision_responses", "outcome_observations"):
            op.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table}")
        op.execute("DROP FUNCTION IF EXISTS decisiongpt_block_update()")
        op.execute("DROP FUNCTION IF EXISTS decisiongpt_observation_update_guard()")
