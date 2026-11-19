import pytest

from app.core.config import get_settings
from app.services.account_sync_service import (
    CANONICAL_DEMO_ACCOUNTS,
    sync_production_demo_accounts,
)

PASSWORDS = {
    "admin@decisiongpt.local": "AdminPass@2026!",
    "researcher@decisiongpt.local": "ResearchPass@2026!",
    "demo@decisiongpt.local": "DemoUser@2026!",
}


@pytest.fixture(autouse=True)
def auth_enabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_enabled", True)


@pytest.fixture(autouse=True)
def synced_db(db_session):
    sync_production_demo_accounts(db_session)
    return db_session


def test_all_three_accounts_can_login_and_verify_roles(client):
    tokens = {}
    for email, pwd in PASSWORDS.items():
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
        assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == email
        expected_role = CANONICAL_DEMO_ACCOUNTS[email]["role"]
        assert data["user"]["role"] == expected_role
        tokens[email] = data["access_token"]

    # Verify /auth/me for each account
    for email, token in tokens.items():
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        me = resp.json()
        assert me["email"] == email
        assert me["role"] == CANONICAL_DEMO_ACCOUNTS[email]["role"]
        assert me["id"] == CANONICAL_DEMO_ACCOUNTS[email]["id"]


def test_role_and_tenancy_isolation(client):
    # Log in as demo user (sme)
    demo_login = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@decisiongpt.local", "password": PASSWORDS["demo@decisiongpt.local"]},
    )
    assert demo_login.status_code == 200
    demo_token = demo_login.json()["access_token"]
    demo_headers = {"Authorization": f"Bearer {demo_token}"}

    # Log in as admin
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@decisiongpt.local", "password": PASSWORDS["admin@decisiongpt.local"]},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Verify each account sees its own authorized identity and role
    me_demo = client.get("/api/v1/auth/me", headers=demo_headers)
    assert me_demo.status_code == 200
    assert me_demo.json()["role"] == "sme"
    assert me_demo.json()["id"] == CANONICAL_DEMO_ACCOUNTS["demo@decisiongpt.local"]["id"]

    me_admin = client.get("/api/v1/auth/me", headers=admin_headers)
    assert me_admin.status_code == 200
    assert me_admin.json()["role"] == "admin"
    assert me_admin.json()["id"] == CANONICAL_DEMO_ACCOUNTS["admin@decisiongpt.local"]["id"]


def test_logout_revokes_token(client):
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@decisiongpt.local", "password": PASSWORDS["admin@decisiongpt.local"]},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # /auth/me succeeds initially
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    # Logout
    logout_resp = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 204

    # Subsequent request with revoked token fails with 401
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
