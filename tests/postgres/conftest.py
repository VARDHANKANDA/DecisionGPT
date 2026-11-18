"""Tests that need a real PostgreSQL. They are skipped (and reported as skipped, never as passed) unless DECISIONGPT_PG_ADMIN_URL points at a
disposable server whose role may create roles and databases, and `psql` is available (it applies deploy/postgres/app-role.sql)."""
import pytest
from sqlalchemy import create_engine

from tests import pg_support


def pytest_collection_modifyitems(config, items):
    reason = None
    if not pg_support.admin_url():
        reason = f"{pg_support.ADMIN_ENV} is not set: no PostgreSQL available (see tests/pg_support.py)"
    elif not pg_support.psql_path():
        reason = "psql was not found (set PSQL or put it on PATH)"
    if reason:
        skip = pytest.mark.skip(reason=reason)
        for item in items:
            if "tests/postgres" in str(item.fspath).replace("\\", "/"):
                item.add_marker(skip)


@pytest.fixture(scope="session")
def pg():
    p = pg_support.provision(pg_support.admin_url())
    yield p
    p.drop()


@pytest.fixture()
def owner_engine(pg):
    e = create_engine(pg.owner_url)
    yield e
    e.dispose()


@pytest.fixture()
def app_engine(pg):
    pg_support.reset_data(pg.owner_url)
    e = create_engine(pg.app_url)
    yield e
    e.dispose()


@pytest.fixture()
def blank():
    """A separate, UNMIGRATED database, for migration-path tests."""
    p = pg_support.provision(pg_support.admin_url(), migrate=False, app_role_sql=False)
    yield p
    p.drop()
