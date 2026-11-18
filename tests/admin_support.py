"""Administrators are created out of band (scripts/create_admin.py), never through public sign-up. Tests do the same."""
from app.services import auth_service


def admin_token(client, db_session, email: str = "admin@example.com", password: str = "orange-river-4271") -> str:
    auth_service.register(db_session, email=email, password=password, full_name="Admin", role="admin")
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]
