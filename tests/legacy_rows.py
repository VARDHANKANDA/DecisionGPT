"""Simulate records written before a column was kept.

Saved tracking rows are append-only, and in production the database refuses any UPDATE of them (migration 0014). A test that needs "a row
from before cutoffs were recorded" therefore cannot edit a saved row: it replaces every matching row with a copy that has the legacy values,
which is exactly how such a row came to exist (it was inserted that way). DELETE and INSERT are permitted by the triggers on every engine."""
from sqlalchemy import delete, insert, select


def as_legacy(db, model, *conditions, **overrides) -> None:
    table = model.__table__
    rows = [dict(r) for r in db.execute(select(table).where(*conditions)).mappings().all()]
    assert rows, "no row matches the condition"
    ids = [r["id"] for r in rows]
    db.execute(delete(table).where(table.c.id.in_(ids)))
    db.execute(insert(table), [{**r, **overrides} for r in rows])
    db.commit()
    db.expire_all()
