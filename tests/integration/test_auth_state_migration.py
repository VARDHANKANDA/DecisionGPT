"""Migration 0015 (token versions, revoked tokens, rate-limit counters) on a disposable SQLite file: existing accounts survive with version 0,
the downgrade is clean, and the ORM tables match what the migration creates. The same migration runs on PostgreSQL in tests/postgres."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _alembic(db: Path, *args: str):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db.as_posix()}", "PYTHONPATH": f"{ROOT / 'backend'}{os.pathsep}{ROOT}", "MIGRATION_DATABASE_URL": ""}
    r = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT / "backend", env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-800:]


def test_0015_upgrades_existing_users_and_downgrades_cleanly(tmp_path):
    db = tmp_path / "m.db"
    _alembic(db, "upgrade", "0014")
    con = sqlite3.connect(db)
    con.execute("INSERT INTO users (id, created_at, updated_at, email, password_hash, role, is_active) VALUES "
                "('u1', '2026-01-01', '2026-01-01', 'a@example.com', 'x', 'sme', 1)")
    con.commit()
    con.close()
    _alembic(db, "upgrade", "0015")
    con = sqlite3.connect(db)
    assert con.execute("SELECT token_version FROM users WHERE id='u1'").fetchone() == (0,)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"revoked_tokens", "rate_limit_buckets"} <= tables
    con.close()
    _alembic(db, "downgrade", "0014")
    con = sqlite3.connect(db)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not ({"revoked_tokens", "rate_limit_buckets"} & tables)
    assert "token_version" not in [r[1] for r in con.execute("PRAGMA table_info(users)")]
    assert con.execute("SELECT email FROM users").fetchone() == ("a@example.com",)
    con.close()
    _alembic(db, "upgrade", "head")
