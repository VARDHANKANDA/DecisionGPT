"""Real-PostgreSQL test support.

Nothing here runs unless a PostgreSQL administrator URL is supplied. With ``DECISIONGPT_PG_ADMIN_URL`` set (a role that may create roles and
databases, e.g. a throwaway superuser of a disposable server) ``provision()`` creates a fresh database, an OWNER role and a least-privilege APP
role, runs the real Alembic migrations as the owner, and applies ``deploy/postgres/app-role.sql`` exactly as a deployment would. The test suite
then connects as the app role, so every statement runs with production's privileges.

Run the PostgreSQL tests (CI does the same against a ``postgres:15`` service):

    export DECISIONGPT_PG_ADMIN_URL=postgresql+psycopg://<admin>:<password>@127.0.0.1:5432/postgres
    pytest tests/postgres

Run an existing suite on PostgreSQL instead of SQLite: ``python -m tests.pg_support provision > pg.env; . pg.env; pytest tests/api`` (the
two printed URLs are ``DECISIONGPT_TEST_PG_APP_URL`` / ``DECISIONGPT_TEST_PG_OWNER_URL``).
"""
from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
ADMIN_ENV = "DECISIONGPT_PG_ADMIN_URL"
APP_ENV, OWNER_ENV = "DECISIONGPT_TEST_PG_APP_URL", "DECISIONGPT_TEST_PG_OWNER_URL"


def admin_url() -> str | None:
    return os.environ.get(ADMIN_ENV) or None


def psql_path() -> str | None:
    return os.environ.get("PSQL") or shutil.which("psql")


@dataclass
class Provisioned:
    admin: str
    database: str
    owner_role: str
    app_role: str
    owner_url: str
    app_url: str

    def drop(self) -> None:
        eng = create_engine(self.admin, isolation_level="AUTOCOMMIT")
        with eng.connect() as c:
            c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :d AND pid <> pg_backend_pid()"), {"d": self.database})
            c.execute(text(f'DROP DATABASE IF EXISTS "{self.database}"'))
            for role in (self.app_role, self.owner_role):
                c.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
        eng.dispose()


def run_alembic(url: str, *args: str, cwd: Path = ROOT / "backend", check: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": url, "MIGRATION_DATABASE_URL": url, "PYTHONPATH": f"{ROOT / 'backend'}{os.pathsep}{ROOT}", "OPENAI_API_KEY": ""}
    r = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=900)
    if check and r.returncode != 0:
        raise RuntimeError(f"alembic {' '.join(args)} failed:\n{r.stderr[-1500:]}")
    return r


def provision(admin: str, *, migrate: bool = True, app_role_sql: bool = True) -> Provisioned:
    tag = secrets.token_hex(4)
    db, owner, app = f"dgpt_{tag}", f"dgpt_owner_{tag}", f"dgpt_app_{tag}"
    owner_pw, app_pw = secrets.token_urlsafe(18), secrets.token_urlsafe(18)
    base = make_url(admin)
    eng = create_engine(admin, isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        c.execute(text(f"CREATE ROLE \"{owner}\" LOGIN PASSWORD '{owner_pw}' NOSUPERUSER NOCREATEDB NOCREATEROLE"))
        c.execute(text(f'CREATE DATABASE "{db}" OWNER "{owner}"'))
    eng.dispose()
    owner_url = base.set(username=owner, password=owner_pw, database=db).render_as_string(hide_password=False)
    app_url = base.set(username=app, password=app_pw, database=db).render_as_string(hide_password=False)
    p = Provisioned(admin, db, owner, app, owner_url, app_url)
    try:
        if migrate:
            run_alembic(owner_url, "upgrade", "head")
        if app_role_sql:
            psql = psql_path()
            if not psql:
                raise RuntimeError("psql was not found (set PSQL or put it on PATH); it applies deploy/postgres/app-role.sql")
            admin_db = base.set(database=db)
            env = {**os.environ, "PGPASSWORD": admin_db.password or ""}
            cmd = [psql, "-v", "ON_ERROR_STOP=1", "-q", "-h", admin_db.host or "127.0.0.1", "-p", str(admin_db.port or 5432), "-U", admin_db.username,
                   "-d", db, "-v", f"owner_role={owner}", "-v", f"app_user={app}", "-v", f"app_password={app_pw}", "-f",
                   str(ROOT / "deploy" / "postgres" / "app-role.sql")]
            r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                raise RuntimeError(f"app-role.sql failed: {r.stderr[-800:]}")
    except Exception:
        p.drop()
        raise
    return p


def reset_data(owner_url: str) -> None:
    """Empty every application table (not alembic_version) so each test starts clean. TRUNCATE needs the owner; the app role cannot do it."""
    eng = create_engine(owner_url, isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        names = [r[0] for r in c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'"))]
        if names:
            c.execute(text("TRUNCATE " + ", ".join(f'"{n}"' for n in names) + " RESTART IDENTITY CASCADE"))
    eng.dispose()


def shared_urls() -> tuple[str, str] | None:
    app, owner = os.environ.get(APP_ENV), os.environ.get(OWNER_ENV)
    return (app, owner) if app and owner else None


if __name__ == "__main__":      # python -m tests.pg_support provision  -> shell exports for a throwaway database
    if sys.argv[1:] == ["provision"] and admin_url():
        pr = provision(admin_url())
        print(f"export {APP_ENV}='{pr.app_url}'\nexport {OWNER_ENV}='{pr.owner_url}'\nexport DATABASE_URL='{pr.app_url}'\nexport MIGRATION_DATABASE_URL='{pr.owner_url}'")
    else:
        raise SystemExit(f"usage: {ADMIN_ENV}=... python -m tests.pg_support provision")
