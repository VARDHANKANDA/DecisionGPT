"""Shared pytest fixtures for the whole test suite (unit/integration/api/e2e).

Tests run against an in-memory SQLite database rather than requiring a live
Postgres instance — see backend/app/db/types.py's cross-dialect GUID type
and AGENTS.md. Production always runs on Postgres (docker-compose.yml);
SQLite here is a test-only substitute so the suite works without Docker.
"""
import os
from pathlib import Path

# Default DATABASE_URL for testing if unset (so in-memory SQLite is used rather than attempting to connect to PostgreSQL default credentials)
if "DATABASE_URL" not in os.environ and not os.environ.get("DECISIONGPT_TEST_PG_APP_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - populate Base.metadata
from app.core.config import get_settings
from app.db.session import Base, get_db
from app.main import app as fastapi_app
from tests import pg_support


@pytest.fixture(autouse=True)
def _auth_disabled_by_default(monkeypatch):
    """The suite is written against the open API (auth_enabled=False), which is
    also the code default. `backend/.env` may set AUTH_ENABLED=true for local
    SaaS use, so pin it back to False here. Tests that exercise auth override
    this themselves (they set it True in their own fixtures, which run after
    this autouse one)."""
    monkeypatch.setattr(get_settings(), "auth_enabled", False)


@pytest.fixture(autouse=True)
def _cheap_password_hashing_and_open_rate_limits(monkeypatch):
    """Two test-only accommodations, both undone after each test:
    * Argon2id with the RFC 9106 production profile (64 MiB, 3 passes) takes ~50 ms a hash; the suite signs up hundreds of accounts, so
      tests use the smallest legal parameters. tests/unit/test_auth_hardening.py asserts the production profile and exercises the real one.
    * The authentication rate limiter is off, so a test that signs in many times from the one in-process client is not throttled. The
      limiter's own tests switch it on (``rate_limit_on`` fixture) and the hardened-environment validator refuses to start with it off."""
    from argon2 import Parameters, Type

    import app.core.security as security

    monkeypatch.setattr(security, "_PROFILE", Parameters(type=Type.ID, version=19, salt_len=16, hash_len=32, time_cost=1, memory_cost=8, parallelism=1))
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", False)
    monkeypatch.setattr(security, "_dummy", None)


@pytest.fixture(autouse=True)
def _uploads_are_kept_in_a_temporary_folder(monkeypatch, tmp_path):
    """The original of every uploaded file is stored under BUSINESS_UPLOAD_PATH; tests must never write customer-shaped files into the repository."""
    monkeypatch.setattr(get_settings(), "business_upload_path", str(tmp_path / "business_uploads"))


@pytest.fixture(autouse=True)
def _no_live_ai_provider_by_default(monkeypatch):
    """`backend/.env` may hold a real OPENAI_API_KEY for local use (the settings loader finds it from any working directory).
    The suite must never spend credits or depend on the network, so pin the AI path off; tests that exercise it install a
    fake client or set a dummy key themselves (their fixtures run after this one)."""
    monkeypatch.setattr(get_settings(), "openai_api_key", None)
    # the model is also read from backend/.env (a developer may use a reasoning model there, which adds a `reasoning` field to the
    # request); pin the default so assertions about request shape do not depend on the local environment
    monkeypatch.setattr(get_settings(), "openai_model", "gpt-4.1-mini")
    monkeypatch.setattr(get_settings(), "analytics_explain_enabled", True)


@pytest.fixture(autouse=True)
def _training_results_go_to_a_temp_dir(monkeypatch, tmp_path_factory):
    """The trainers write an experiment-result JSON on every ``run()``; tests must not add files to the real experiments/results/."""
    from ml.training import train_churn, train_forecasting

    d = tmp_path_factory.getbasetemp() / "training_results"
    monkeypatch.setattr(train_forecasting, "RESULTS_DIR", d)
    monkeypatch.setattr(train_churn, "RESULTS_DIR", d)


@pytest.fixture(autouse=True)
def _block_outbound_http(monkeypatch):
    """No test may reach the network (and so none can spend API credits): a real httpx socket transport raises. Starlette's TestClient
    uses its own in-process transport and is unaffected; tests that need a provider replace ``OpenAIClient._request``."""
    import httpx

    def blocked(*_a, **_k):
        raise RuntimeError("outbound network access is blocked in tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)

_MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
_REGISTRY_INDEX = _MODELS_DIR / "registry_index.jsonl"


@pytest.fixture(scope="session", autouse=True)
def _ensure_baseline_models():
    """Many tests sync the file model registry and then run forecasting /
    churn / decision code. Ensure deterministic (seed=42) baselines exist."""
    required = [
        _MODELS_DIR / "sales_forecast_naive" / "v1" / "model.joblib",
        _MODELS_DIR / "sales_forecast_linear" / "v1" / "model.joblib",
        _MODELS_DIR / "sales_forecast_xgboost" / "v1" / "model.joblib",
        _MODELS_DIR / "churn_logistic_regression" / "v1" / "model.joblib",
        _MODELS_DIR / "churn_random_forest" / "v1" / "model.joblib",
        _MODELS_DIR / "churn_xgboost" / "v1" / "model.joblib",
    ]
    if _REGISTRY_INDEX.exists() and all(p.exists() for p in required):
        return
    from ml.training.train_churn import run as train_churn
    from ml.training.train_forecasting import run as train_forecasting

    train_forecasting(random_seed=42)
    train_churn(random_seed=42)


@pytest.fixture()
def db_session():
    urls = pg_support.shared_urls()
    if urls:        # DECISIONGPT_TEST_PG_APP_URL / _OWNER_URL: run against a real, migrated PostgreSQL as the least-privilege app role
        pg_support.reset_data(urls[1])
        pg_engine = create_engine(urls[0], pool_pre_ping=True)
        pg_session = sessionmaker(bind=pg_engine, autoflush=False, autocommit=False)()
        try:
            yield pg_session
        finally:
            pg_session.close()
            pg_engine.dispose()
        return
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
