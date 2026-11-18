"""A consistent read snapshot for reports that issue several queries.

Without one, a record committed between two of a report's statements can show up in one list and not in another (an observation whose
expectation the report does not list). Inside ``read_snapshot`` every statement sees the same committed state:

* PostgreSQL: ``REPEATABLE READ``, read-only. No locks are taken on the rows read and writers are never blocked.
* SQLite: an explicit ``BEGIN`` so the reads share one transaction. In WAL mode readers do not block writers; in the default rollback-journal
  mode a writer's commit waits (up to the busy timeout) for the short read to finish.
* Any other engine: no change (the caller still filters orphaned rows defensively).

Supported engines: PostgreSQL (production) and SQLite (local development and tests). Both are exercised: the default suite on SQLite, and
tests/postgres (isolation level, read-only enforcement, concurrent commits) on a real PostgreSQL 15 (docs/PRODUCTION_SECURITY_REVIEW.md).
The caller must have no pending writes: opening a snapshot ends the current (read-only) transaction.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session


@contextmanager
def read_snapshot(db: Session) -> Iterator[Session]:
    dialect = db.get_bind().dialect.name
    db.rollback()                         # end any open transaction so the isolation statement is the first of a new one
    try:
        if dialect == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        elif dialect == "sqlite":
            db.execute(text("BEGIN"))
        yield db
    finally:
        db.rollback()                     # a read-only transaction: nothing to commit, and the connection is released cleanly
