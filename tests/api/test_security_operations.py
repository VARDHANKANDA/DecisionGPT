"""Operational security: errors reveal nothing internal, authentication failures are uniform, security events are logged without customer data
or secrets, and the interactive API documentation follows the environment."""
import logging

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app as fastapi_app
from tests.api.test_platform_api import P, _owner, auth_on  # noqa: F401  (auth_on is a fixture)


def test_an_unexpected_error_returns_a_generic_body_without_internals(client, db_session, auth_on, monkeypatch):
    from app.services import kpi_monitor_service

    a, ha = _owner(client, "se@example.com", "Boom Co")

    def boom(*args, **kwargs):
        raise RuntimeError("secret-internal-detail D:\\srv\\app\\settings.py password=hunter2")

    monkeypatch.setattr(kpi_monitor_service, "compute", boom, raising=False)
    import app.api.v1.endpoints.platform as platform

    monkeypatch.setattr(platform.dps, "profile", boom)
    tc = TestClient(fastapi_app, raise_server_exceptions=False)
    r = tc.get(f"{P}/{a}/data/profile/sales", headers=ha)
    assert r.status_code == 500
    assert r.json() == {"error": {"code": "INTERNAL_ERROR", "message": "Something went wrong on our side. Please try again.", "details": {}}}
    for leaked in ("secret-internal-detail", "hunter2", "settings.py", "Traceback", "RuntimeError"):
        assert leaked not in r.text


def test_an_unexpected_error_is_logged_for_the_operator_without_its_message(client, db_session, auth_on, monkeypatch, caplog):
    a, ha = _owner(client, "lg@example.com", "Log Co")

    def boom(*args, **kwargs):
        raise RuntimeError("secret-internal-detail password=hunter2 customer=Jane Doe")

    import app.api.v1.endpoints.platform as platform

    monkeypatch.setattr(platform.dps, "profile", boom)
    with caplog.at_level(logging.INFO):
        TestClient(fastapi_app, raise_server_exceptions=False).get(f"{P}/{a}/data/profile/sales", headers=ha)
    (rec,) = [r for r in caplog.records if r.name == "decisiongpt.errors"]
    assert rec.getMessage() == "unhandled_error" and rec.exception_type == "RuntimeError" and rec.request_id and rec.where.endswith(".py:" + rec.where.split(":")[-1])
    assert rec.where.startswith("test_security_operations.py") or rec.where.startswith("platform.py")           # a frame of ours, with a line number
    blob = f"{rec.getMessage()} {rec.__dict__}"
    for leaked in ("secret-internal-detail", "hunter2", "Jane Doe"):
        assert leaked not in blob


def test_malformed_identifiers_are_not_found_not_server_errors(client, db_session, auth_on):
    a, ha = _owner(client, "mf@example.com", "Malformed Co")
    for path in (f"{P}/not-a-uuid", f"{P}/not-a-uuid/goals", f"{P}/{a}/explain/answer/does-not-exist", f"{P}/{a}/decisions/not-a-uuid"):
        r = client.get(path, headers=ha)
        assert r.status_code == 404, (path, r.status_code)
        db_session.rollback()      # the suite shares ONE session across requests; on PostgreSQL a rejected UUID aborts its transaction (each real request has its own)
    assert client.get(f"{P}/not-a-uuid/goals", headers=ha).json()["error"]["message"] == "Business not found."       # the same words as any foreign business


def test_wrong_password_and_unknown_account_are_indistinguishable(client, auth_on):
    client.post("/api/v1/auth/register", json={"email": "real@example.com", "password": "orange-river-4271"})
    wrong = client.post("/api/v1/auth/login", json={"email": "real@example.com", "password": "not-the-password"})
    unknown = client.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": "not-the-password"})
    assert wrong.status_code == unknown.status_code == 401 and wrong.json() == unknown.json()


def test_a_forged_or_expired_token_is_just_unauthenticated(client, auth_on):
    a, ha = _owner(client, "tk@example.com", "Tok")
    for bad in ("Bearer garbage", "Bearer a.b", "Bearer " + ha["Authorization"].split()[1][:-3] + "xyz", "Basic abc"):
        r = client.get(f"{P}/{a}/goals", headers={"Authorization": bad})
        assert r.status_code == 401 and "garbage" not in r.text


def test_security_events_are_logged_without_customer_data_or_secrets(client, auth_on, caplog):
    a, ha = _owner(client, "log-a@example.com", "Logged Co")
    b, hb = _owner(client, "log-b@example.com", "Other Co")
    with caplog.at_level(logging.INFO):
        client.get(f"{P}/{a}/goals", headers=hb)                                       # cross-tenant attempt
        client.get(f"{P}/{a}/goals")                                                   # anonymous attempt
        client.post("/api/v1/auth/login", json={"email": "log-a@example.com", "password": "password-that-is-wrong"})
    events = [r for r in caplog.records if r.name == "decisiongpt.security"]
    assert {r.getMessage() for r in events} >= {"cross_tenant_denied", "unauthenticated_request"}
    blob = "\n".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    token = hb["Authorization"].split()[1]
    for leaked in ("log-a@example.com", "log-b@example.com", "password-that-is-wrong", "orange-river-4271", token, "Logged Co", get_settings().jwt_secret):
        assert leaked not in blob, leaked
    assert all(getattr(r, "request_id", None) for r in events)                         # every event can be correlated with its request


def test_responses_never_contain_server_secrets(client, auth_on):
    s = get_settings()
    secrets = [s.jwt_secret, s.secret_key, s.research_console_token]
    a, ha = _owner(client, "sec@example.com", "Sec")
    bodies = [client.get("/").text, client.get("/api/v1/health").text, client.get("/api/v1/auth/me", headers=ha).text,
              client.get(f"{P}/{a}", headers=ha).text, client.get(f"{P}/{a}/tracking/report", headers=ha).text,
              client.get(f"{P}/{a}", headers={"Authorization": "Bearer x"}).text]
    for body in bodies:
        for secret in secrets:
            assert secret not in body


def test_documentation_follows_the_environment(client):
    s = get_settings()
    assert s.docs_active is True                                                       # development / test default
    assert client.get("/openapi.json").status_code == 200
    root = client.get("/").json()
    assert root["docs"] == "/docs"
    # in a hardened environment the documentation switches are off (the application object is built at import; see test_security_config)
    from app.core.config import Settings

    assert Settings(_env_file=None, environment="production").docs_active is False


def test_cors_allows_only_the_configured_origin_methods_and_headers(client):
    ok = client.options("/api/v1/health", headers={"Origin": get_settings().frontend_origin, "Access-Control-Request-Method": "POST",
                                                   "Access-Control-Request-Headers": "authorization,content-type"})
    assert ok.headers.get("access-control-allow-origin") == get_settings().frontend_origin
    bad = client.options("/api/v1/health", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers
    odd = client.options("/api/v1/health", headers={"Origin": get_settings().frontend_origin, "Access-Control-Request-Method": "TRACE"})
    assert odd.status_code == 400                                                       # a method outside the allow-list is refused
