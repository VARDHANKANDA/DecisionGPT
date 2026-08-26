"""Phase 4 — authentication + role-based access control."""
import pytest

from app.core.config import get_settings


@pytest.fixture()
def auth_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_enabled", True)
    yield


def _register(client, email, password="password123", role="sme"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "role": role, "full_name": "T"},
    )


def test_register_and_login_issue_a_working_token(client):
    r = _register(client, "sme1@example.com")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "sme"
    token = body["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "sme1@example.com"


def test_duplicate_email_is_rejected(client):
    _register(client, "dupe@example.com")
    assert _register(client, "dupe@example.com").status_code == 422


def test_short_password_is_rejected(client):
    assert _register(client, "x@example.com", password="short").status_code == 422


def test_login_wrong_password_401(client):
    _register(client, "u@example.com")
    r = client.post("/api/v1/auth/login", json={"email": "u@example.com", "password": "nope"})
    assert r.status_code == 401


def test_auth_enabled_blocks_unauthenticated_business_creation_path(client, auth_on):
    # With auth on, creating a business still works (owner recorded), but
    # reading it back requires the owner's token.
    token = _register(client, "owner@example.com").json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    bid = client.post(
        "/api/v1/businesses",
        json={"name": "B", "industry": "Retail", "business_type": "D2C", "business_size": "Small (6-25)"},
        headers=auth,
    ).json()["id"]

    # No token -> 401
    assert client.get(f"/api/v1/businesses/{bid}").status_code == 401
    # Owner token -> ok
    assert client.get(f"/api/v1/businesses/{bid}", headers=auth).status_code == 200


def test_research_routes_reject_sme_but_accept_admin(client, auth_on):
    sme = _register(client, "s@example.com", role="sme").json()["access_token"]
    admin = _register(client, "a@example.com", role="admin").json()["access_token"]

    assert client.get("/api/v1/research/overview", headers={"Authorization": f"Bearer {sme}"}).status_code == 403
    assert client.get("/api/v1/research/overview", headers={"Authorization": f"Bearer {admin}"}).status_code == 200


def test_static_research_token_still_works_when_auth_on(client, auth_on):
    r = client.get(
        "/api/v1/research/overview",
        headers={"X-Research-Token": get_settings().research_console_token},
    )
    assert r.status_code == 200
