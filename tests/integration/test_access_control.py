"""Phase 4 — business A cannot reach business B's data when auth is on."""
import pytest

from app.core.config import get_settings
from tests.integration.test_analytics import _seed_rich_business


@pytest.fixture()
def auth_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_enabled", True)
    yield


def _signup(client, email):
    token = client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password123", "role": "sme"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_business(client, headers):
    return client.post(
        "/api/v1/businesses",
        json={"name": "B", "industry": "Retail", "business_type": "D2C", "business_size": "Small (6-25)"},
        headers=headers,
    ).json()["id"]


def test_owner_can_access_non_owner_cannot(client, db_session, auth_on):
    from app.services import model_registry_service

    model_registry_service.sync_from_file_registry(db_session)

    alice = _signup(client, "alice@example.com")
    bob = _signup(client, "bob@example.com")

    biz_a = _make_business(client, alice)
    # Alice seeds + analyses her own business (helper posts without auth headers,
    # so temporarily allow it by disabling auth for the data seeding only is not
    # possible here — instead seed via authenticated uploads).
    _seed_rich_business(client, biz_a, headers=alice)

    # Alice: full access
    assert client.get(f"/api/v1/businesses/{biz_a}/analytics/kpis", headers=alice).status_code == 200
    # Bob: forbidden on Alice's business
    r = client.get(f"/api/v1/businesses/{biz_a}/analytics/kpis", headers=bob)
    assert r.status_code == 403
    # Unauthenticated: 401
    assert client.get(f"/api/v1/businesses/{biz_a}/analytics/kpis").status_code == 401

    # Bob cannot upload into Alice's business either.
    up = client.post(
        f"/api/v1/businesses/{biz_a}/data/upload?data_type=sales",
        files={"file": ("s.csv", b"a,b\n1,2\n", "text/csv")},
        headers=bob,
    )
    assert up.status_code == 403


def test_decisions_and_goals_are_owner_scoped(client, db_session, auth_on):
    from app.services import model_registry_service

    model_registry_service.sync_from_file_registry(db_session)
    alice = _signup(client, "a2@example.com")
    bob = _signup(client, "b2@example.com")

    biz_a = _make_business(client, alice)
    _seed_rich_business(client, biz_a, headers=alice)
    goal = client.post(
        f"/api/v1/businesses/{biz_a}/goals",
        json={"text": "Increase revenue by 10% in 2 months"},
        headers=alice,
    ).json()["id"]
    decision = client.post(
        f"/api/v1/businesses/{biz_a}/decisions/analyze", json={"goal_id": goal}, headers=alice
    ).json()["id"]

    assert client.get(f"/api/v1/businesses/{biz_a}/decisions/{decision}/trace", headers=bob).status_code == 403
    assert client.get(f"/api/v1/businesses/{biz_a}/goals", headers=bob).status_code == 403
