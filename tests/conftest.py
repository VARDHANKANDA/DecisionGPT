"""Shared pytest fixtures for the whole test suite (unit/integration/api/e2e).

Tests run against an in-memory SQLite database rather than requiring a live
Postgres instance — see backend/app/db/types.py's cross-dialect GUID type
and AGENTS.md. Production always runs on Postgres (docker-compose.yml);
SQLite here is a test-only substitute so the suite works without Docker.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - populate Base.metadata
from app.core.config import get_settings
from app.db.session import Base, get_db
from app.main import app as fastapi_app


@pytest.fixture(autouse=True)
def _auth_disabled_by_default(monkeypatch):
    """The suite is written against the open API (auth_enabled=False), which is
    also the code default. `backend/.env` may set AUTH_ENABLED=true for local
    SaaS use, so pin it back to False here. Tests that exercise auth override
    this themselves (they set it True in their own fixtures, which run after
    this autouse one)."""
    monkeypatch.setattr(get_settings(), "auth_enabled", False)

_REGISTRY_INDEX = Path(__file__).resolve().parents[1] / "models" / "registry_index.jsonl"


@pytest.fixture(scope="session", autouse=True)
def _ensure_baseline_models():
    """Many tests sync the file model registry and then run forecasting /
    churn / decision code. The trained artifacts are build products, not
    source (``models/`` is gitignored), so on a fresh checkout train the
    deterministic (seed=42) baselines once before the suite runs."""
    if _REGISTRY_INDEX.exists():
        return
    from ml.training.train_churn import run as train_churn
    from ml.training.train_forecasting import run as train_forecasting

    train_forecasting(random_seed=42)
    train_churn(random_seed=42)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()
