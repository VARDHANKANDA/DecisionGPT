"""Authentication abuse protection and session lifecycle over real HTTP: rate limits (enforced, recoverable, not a permanent lockout, shared across
workers, not bypassable with forged proxy headers), logout and revocation, password change, privilege changes taking effect at once, and
responses/logs that never echo a password or token."""
import logging
import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.security import decode_token
from app.db.session import Base
from app.main import app as fastapi_app
from app.models.auth_state import RateLimitBucket, RevokedToken
from app.models.user import User
from app.services import rate_limit_service as limiter
from tests.admin_support import admin_token
from tests.api.test_platform_api import P, auth_on  # noqa: F401  (auth_on is a fixture)

PW = "orange-river-4271"
LOGIN, REGISTER = "/api/v1/auth/login", "/api/v1/auth/register"


class Clock:
    def __init__(self, t: float = 1_800_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture()
def rate_limit_on(monkeypatch):
    """The limiter on, with small limits and a controllable clock."""
    s, clock = get_settings(), Clock()
    for name, value in dict(rate_limit_enabled=True, rate_limit_window_seconds=900, rate_limit_login_per_ip=8, rate_limit_login_per_account_ip=3,
                            rate_limit_login_per_account=6, rate_limit_register_per_ip=4, rate_limit_register_window_seconds=3600,
                            rate_limit_password_change_per_user=3, trusted_proxies="").items():
        monkeypatch.setattr(s, name, value)
    monkeypatch.setattr(limiter, "_now", clock)
    return clock


def _signup(client, email="victim@example.com", pw=PW):
    r = client.post(REGISTER, json={"email": email, "password": pw})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _bad(client, email="victim@example.com", **kw):
    return client.post(LOGIN, json={"email": email, "password": "not-the-right-one"}, **kw)


def _good(client, email="victim@example.com", pw=PW, **kw):
    return client.post(LOGIN, json={"email": email, "password": pw}, **kw)


# ------------------------------------------------------------------ sign-in limits
def test_repeated_failures_are_throttled_with_retry_information_even_for_the_right_password(client, rate_limit_on):
    _signup(client)
    assert [_bad(client).status_code for _ in range(3)] == [401, 401, 401]
    r = _good(client)                                           # the 4th attempt: refused BEFORE the password is looked at
    assert r.status_code == 429
    body = r.json()["error"]
    assert body["code"] == "RATE_LIMITED" and 1 <= body["details"]["retry_after_seconds"] <= 900
    assert r.headers["Retry-After"] == str(body["details"]["retry_after_seconds"])
    assert "victim" not in r.text and "access_token" not in r.text                  # says nothing about the account


def test_the_limit_is_temporary_not_a_lockout(client, rate_limit_on):
    _signup(client)
    for _ in range(3):
        _bad(client)
    assert _good(client).status_code == 429
    rate_limit_on.t += 901                                      # the window passes
    assert _good(client).status_code == 200


def test_a_throttled_caller_cannot_tell_whether_a_guess_was_right(client, rate_limit_on):
    _signup(client)
    for _ in range(3):
        _bad(client)
    right, wrong = _good(client), _bad(client)
    assert right.status_code == wrong.status_code == 429
    assert right.json()["error"]["code"] == wrong.json()["error"]["code"] == "RATE_LIMITED" and "access_token" not in right.text


def test_a_successful_sign_in_clears_only_the_account_and_address_counter(client, rate_limit_on, db_session):
    _signup(client)
    _bad(client), _bad(client)
    assert _good(client).status_code == 200
    assert [_bad(client).status_code for _ in range(3)] == [401, 401, 401]                # the pair budget was restored
    # but the per-address budget (shared by all accounts) is NOT reset by signing in, so an attacker cannot refill it with an account of their own
    ip_rule = limiter._rules()["login_ip"]
    count, _ = limiter.current(db_session, ip_rule, "testclient")
    assert count >= 5


def _proxy_client(peer=("10.0.0.5", 4000), **kw) -> TestClient:
    async def wrap(scope, receive, send):
        if scope.get("type") == "http":
            scope = dict(scope)
            scope["client"] = peer
        await fastapi_app(scope, receive, send)
    return TestClient(wrap, **kw)


def test_failures_against_an_account_throttle_a_different_address_only_at_the_higher_account_limit(client, rate_limit_on, monkeypatch):
    monkeypatch.setattr(get_settings(), "trusted_proxies", "10.0.0.0/8")
    _signup(client)
    proxy = _proxy_client(("10.0.0.5", 4000))
    def from_ip(ip):
        return {"headers": {"X-Forwarded-For": ip}}
    for n in range(6):                                                   # six different attackers, one failure each: no single pair or address is full
        assert _bad(proxy, **from_ip(f"203.0.113.{n + 1}")).status_code == 401
    assert _good(proxy, **from_ip("198.51.100.99")).status_code == 429          # the distributed brake on the account itself has tripped
    other = _proxy_client(("10.0.0.5", 4000)).post(LOGIN, json={"email": "someone-else@example.com", "password": PW},
                                                   headers={"X-Forwarded-For": "198.51.100.99"})
    assert other.status_code == 401                                                # other accounts and addresses are unaffected


def test_one_attacker_address_is_throttled_across_many_accounts(client, rate_limit_on):
    codes = [client.post(LOGIN, json={"email": f"nobody{n}@example.com", "password": PW}).status_code for n in range(10)]
    assert codes[:8] == [401] * 8 and codes[8:] == [429, 429]                       # the per-address limit (8) applies even to accounts that do not exist


def test_an_unknown_account_is_treated_exactly_like_a_wrong_password(client, rate_limit_on, monkeypatch):
    import app.services.auth_service as svc

    calls = []
    monkeypatch.setattr(svc, "burn_password_check", lambda pw: calls.append(pw))
    _signup(client)
    unknown = client.post(LOGIN, json={"email": "ghost@example.com", "password": PW})
    known = _bad(client)
    assert unknown.status_code == known.status_code == 401 and unknown.json() == known.json()
    assert calls == [PW]                                                              # hashing time is spent for an account that does not exist


def test_throttling_applies_in_the_same_way_with_authentication_disabled_or_enabled(client, rate_limit_on, auth_on):
    _signup(client)
    for _ in range(3):
        _bad(client)
    assert _good(client).status_code == 429


# ------------------------------------------------------------------ proxy headers
def test_a_forged_forwarded_for_header_cannot_buy_a_fresh_budget_from_an_untrusted_peer(client, rate_limit_on):
    _signup(client)
    codes = [_bad(client, headers={"X-Forwarded-For": f"203.0.113.{n}"}).status_code for n in range(5)]
    assert codes == [401, 401, 401, 429, 429]                                         # rotating the header changed nothing: the peer is the identity


def test_with_a_trusted_proxy_the_bucket_follows_the_address_the_proxy_appended_not_the_forged_prefix(client, rate_limit_on, monkeypatch):
    monkeypatch.setattr(get_settings(), "trusted_proxies", "10.0.0.0/8")
    _signup(client)
    proxy = _proxy_client(("10.0.0.5", 4000))
    # the attacker rotates the left part of the header; the proxy always appends the attacker's real address, 203.0.113.50
    codes = [_bad(proxy, headers={"X-Forwarded-For": f"9.9.9.{n}, 203.0.113.50"}).status_code for n in range(5)]
    assert codes == [401, 401, 401, 429, 429]
    honest = _good(proxy, headers={"X-Forwarded-For": "198.51.100.7"})             # a different real client of the same proxy is not affected
    assert honest.status_code == 200


# ------------------------------------------------------------------ sign-up limits
def test_account_creation_is_limited_per_address_and_recovers(client, rate_limit_on, db_session):
    assert [client.post(REGISTER, json={"email": f"u{n}@example.com", "password": PW}).status_code for n in range(4)] == [201] * 4
    r = client.post(REGISTER, json={"email": "u9@example.com", "password": PW})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    assert db_session.execute(select(User).where(User.email == "u9@example.com")).first() is None      # the refused attempt created nothing
    rate_limit_on.t += 3601
    assert client.post(REGISTER, json={"email": "u9@example.com", "password": PW}).status_code == 201


def test_an_attempt_to_register_as_administrator_counts_against_the_limit(client, rate_limit_on):
    codes = [client.post(REGISTER, json={"email": f"e{n}@example.com", "password": PW, "role": "admin"}).status_code for n in range(6)]
    assert codes == [403, 403, 403, 403, 429, 429]


# ------------------------------------------------------------------ shared state: concurrency and several workers
def _file_db(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'rl.db').as_posix()}", connect_args={"check_same_thread": False, "timeout": 30})
    Base.metadata.create_all(engine)
    return engine


def test_concurrent_attempts_are_counted_exactly(tmp_path, rate_limit_on):
    engine = _file_db(tmp_path)
    Session = sessionmaker(bind=engine, autoflush=False)
    rule = limiter.Rule("login_ip", 10_000, 900)
    errors = []

    def worker():
        db = Session()
        try:
            for _ in range(25):
                limiter.record(db, rule, "203.0.113.9")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            db.close()

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors, errors
    db = Session()
    assert limiter.current(db, rule, "203.0.113.9")[0] == 200                          # 8 x 25 increments, none lost
    db.close()


def test_concurrent_sign_ups_never_exceed_the_limit(tmp_path, rate_limit_on):
    engine = _file_db(tmp_path)
    Session = sessionmaker(bind=engine, autoflush=False)
    admitted, refused = [], []

    def worker():
        db = Session()
        try:
            limiter.enforce_register(db, "203.0.113.9")
            admitted.append(1)
        except limiter.RateLimitedError:
            refused.append(1)
        finally:
            db.close()

    threads = [threading.Thread(target=worker) for _ in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(admitted) == 4 and len(refused) == 16                                   # exactly the limit got through


def test_two_workers_on_one_database_share_one_budget(tmp_path, rate_limit_on):
    """Each 'worker' has its own engine and session (as separate processes would); an in-memory limiter would give each a full budget."""
    path = f"sqlite:///{(tmp_path / 'shared.db').as_posix()}"
    e1, e2 = create_engine(path, connect_args={"timeout": 30}), create_engine(path, connect_args={"timeout": 30})
    Base.metadata.create_all(e1)
    w1, w2 = sessionmaker(bind=e1, autoflush=False)(), sessionmaker(bind=e2, autoflush=False)()
    for _ in range(2):
        limiter.login_failed(w1, "victim@example.com", "203.0.113.9")
    limiter.login_failed(w2, "victim@example.com", "203.0.113.9")                       # worker 2 sees worker 1's failures
    with pytest.raises(limiter.RateLimitedError):
        limiter.enforce_login(w1, "victim@example.com", "203.0.113.9")
    with pytest.raises(limiter.RateLimitedError):
        limiter.enforce_login(w2, "victim@example.com", "203.0.113.9")


def test_counters_hold_no_email_or_address_and_expired_rows_are_pruned(client, rate_limit_on, db_session, monkeypatch):
    _signup(client)
    _bad(client)
    keys = [k for (k,) in db_session.execute(select(RateLimitBucket.key)).all()]
    assert keys and not any("victim" in k or "example.com" in k or "testclient" in k for k in keys)
    monkeypatch.setattr(limiter.random, "random", lambda: 0.0)                           # force the amortised cleanup
    rate_limit_on.t += 100_000
    _bad(client)
    left = db_session.execute(select(func.count()).select_from(RateLimitBucket)).scalar()
    assert left == 3                                                                      # only the three fresh buckets remain


def test_the_limiter_can_be_turned_off_only_outside_hardened_environments(client, monkeypatch):
    from app.core.security_config import security_problems
    from tests.unit.test_security_config import make

    assert any("RATE_LIMIT_ENABLED" in p for p in security_problems(make(rate_limit_enabled=False)))
    assert security_problems(make(rate_limit_enabled=False, environment="development", auth_enabled=False)) == []
    _signup(client)
    assert all(_bad(client).status_code == 401 for _ in range(10))                       # off (the suite default): never throttled


# ------------------------------------------------------------------ sessions, logout and revocation
def _me(client, token):
    return client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code


def test_logout_ends_this_session_only(client):
    t1 = _signup(client)
    t2 = _good(client).json()["access_token"]
    assert _me(client, t1) == _me(client, t2) == 200
    assert client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {t1}"}).status_code == 204
    assert _me(client, t1) == 401 and _me(client, t2) == 200
    assert client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {t1}"}).status_code == 204       # idempotent
    assert client.post("/api/v1/auth/logout").status_code == 204 and client.post("/api/v1/auth/logout", headers={"Authorization": "Bearer junk"}).status_code == 204


def test_a_revoked_token_is_refused_by_business_routes_when_authentication_is_on(client, auth_on):
    token = _signup(client)
    h = {"Authorization": f"Bearer {token}"}
    bid = client.post(P, json={"name": "B", "industry": "retail", "business_type": "D2C", "business_size": "small"}, headers=h).json()["id"]
    assert client.get(f"{P}/{bid}", headers=h).status_code == 200
    client.post("/api/v1/auth/logout", headers=h)
    assert client.get(f"{P}/{bid}", headers=h).status_code == 401


def test_logout_all_ends_every_session(client, auth_on):
    t1 = _signup(client)
    t2 = _good(client).json()["access_token"]
    assert client.post("/api/v1/auth/logout-all", headers={"Authorization": f"Bearer {t1}"}).status_code == 204
    assert _me(client, t1) == 401 and _me(client, t2) == 401
    assert _good(client).status_code == 200                                              # signing in again works


def test_logout_all_needs_a_signed_in_user_when_authentication_is_on(client, auth_on):
    assert client.post("/api/v1/auth/logout-all").status_code == 401
    assert client.post("/api/v1/auth/change-password", json={"current_password": PW, "new_password": "another-long-pass-1"}).status_code == 401


def test_revocation_rows_expire_with_the_token(client, db_session):
    t = _signup(client)
    client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {t}"})
    row = db_session.execute(select(RevokedToken)).scalar_one()
    assert row.jti == decode_token(t)["jti"] and row.expires_at is not None


def test_changing_the_password_ends_other_sessions_and_returns_a_working_token(client, auth_on):
    t1 = _signup(client)
    other = _good(client).json()["access_token"]
    r = client.post("/api/v1/auth/change-password", headers={"Authorization": f"Bearer {t1}"},
                    json={"current_password": PW, "new_password": "a-brand-new-passphrase"})
    assert r.status_code == 200
    fresh = r.json()["access_token"]
    assert _me(client, t1) == 401 and _me(client, other) == 401 and _me(client, fresh) == 200
    assert _good(client).status_code == 401 and _good(client, pw="a-brand-new-passphrase").status_code == 200


def test_changing_the_password_needs_the_current_one_and_a_policy_compliant_new_one(client, auth_on):
    h = {"Authorization": f"Bearer {_signup(client)}"}
    wrong = client.post("/api/v1/auth/change-password", headers=h, json={"current_password": "nope-nope-nope", "new_password": "a-brand-new-passphrase"})
    assert wrong.status_code == 401
    weak = client.post("/api/v1/auth/change-password", headers=h, json={"current_password": PW, "new_password": "password123"})
    same = client.post("/api/v1/auth/change-password", headers=h, json={"current_password": PW, "new_password": PW})
    assert weak.status_code == 422 and same.status_code == 422
    assert _good(client).status_code == 200                                               # nothing changed


def test_password_change_guesses_are_rate_limited_per_user(client, auth_on, rate_limit_on):
    h = {"Authorization": f"Bearer {_signup(client)}"}
    body = {"current_password": "wrong-wrong-wrong", "new_password": "a-brand-new-passphrase"}
    assert [client.post("/api/v1/auth/change-password", headers=h, json=body).status_code for _ in range(3)] == [401, 401, 401]
    assert client.post("/api/v1/auth/change-password", headers=h, json={**body, "current_password": PW}).status_code == 429


def test_a_deactivated_user_loses_access_at_once(client, db_session):
    t = _signup(client)
    assert _me(client, t) == 200
    user = db_session.execute(select(User)).scalar_one()
    user.is_active = False
    db_session.commit()
    assert _me(client, t) == 401
    assert _good(client).status_code == 401


def test_demoting_an_administrator_removes_research_access_without_waiting_for_the_token_to_expire(client, db_session, auth_on):
    token = admin_token(client, db_session)
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/research/models", headers=h).status_code == 200
    user = db_session.execute(select(User).where(User.role == "admin")).scalar_one()
    user.role = "sme"                                                                       # the role in the database is authoritative, never a claim
    db_session.commit()
    assert client.get("/api/v1/research/models", headers=h).status_code == 403


def test_resetting_an_admin_password_with_the_script_logic_ends_existing_sessions(client, db_session, auth_on):
    token = admin_token(client, db_session)
    user = db_session.execute(select(User)).scalar_one()
    user.token_version += 1                                                                 # what scripts/create_admin.py does on a reset
    db_session.commit()
    assert client.get("/api/v1/research/models", headers={"Authorization": f"Bearer {token}"}).status_code == 403      # research routes answer 403 to anyone without admin credentials


def test_a_legacy_password_hash_is_upgraded_on_the_next_sign_in(client, db_session):
    import base64, hashlib, os

    _signup(client)
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", PW.encode(), salt, 240_000)
    user = db_session.execute(select(User)).scalar_one()
    user.password_hash = f"pbkdf2_sha256$240000${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"
    db_session.commit()
    assert _good(client).status_code == 200                                                 # the old hash still works
    db_session.refresh(user)
    assert user.password_hash.startswith("$argon2id$") and _good(client).status_code == 200


def test_operator_recovery_resets_the_password_and_ends_every_session(client, db_session):
    from app.core.errors import NotFoundError, ValidationFailedError
    from app.services import auth_service

    token = _signup(client)
    assert _me(client, token) == 200
    with pytest.raises(ValidationFailedError, match="too easy"):
        auth_service.operator_reset(db_session, "victim@example.com", new_password="password123")           # same policy as sign-up
    with pytest.raises(NotFoundError):
        auth_service.operator_reset(db_session, "ghost@example.com", new_password="a-fresh-passphrase-9")
    auth_service.operator_reset(db_session, "victim@example.com", new_password="a-fresh-passphrase-9")
    assert _me(client, token) == 401 and _good(client).status_code == 401
    assert _good(client, pw="a-fresh-passphrase-9").status_code == 200


def test_operator_deactivation_blocks_sign_in_and_reactivation_restores_it(client, db_session):
    from app.services import auth_service

    token = _signup(client)
    auth_service.operator_reset(db_session, "victim@example.com", active=False)
    assert _me(client, token) == 401 and _good(client).status_code == 401
    auth_service.operator_reset(db_session, "victim@example.com", active=True)
    assert _good(client).status_code == 200                                                    # the password is unchanged by (de)activation


# ------------------------------------------------------------------ nothing secret in responses or logs
def test_validation_errors_do_not_echo_what_was_submitted(client):
    r = client.post(REGISTER, json={"email": "not-an-email", "password": "x" * 200})
    assert r.status_code == 422 and "x" * 20 not in r.text and '"input"' not in r.text
    r2 = client.post(LOGIN, json={"email": "a@example.com"})
    assert r2.status_code == 422 and "loc" in r2.text


def test_authentication_failures_log_no_password_token_or_email(client, rate_limit_on, caplog):
    token = _signup(client)
    with caplog.at_level(logging.INFO):
        for _ in range(4):
            client.post(LOGIN, json={"email": "victim@example.com", "password": "guess-number-one"})
        client.post("/api/v1/auth/change-password", headers={"Authorization": f"Bearer {token}"},
                    json={"current_password": "guess-number-two", "new_password": "never-seen-in-logs-1"})
    blob = "\n".join(f"{r.getMessage()} {r.__dict__}" for r in caplog.records)
    for leaked in ("guess-number-one", "guess-number-two", "never-seen-in-logs-1", PW, token, "victim@example.com", get_settings().jwt_secret):
        assert leaked not in blob, leaked
    names = {r.getMessage() for r in caplog.records if r.name == "decisiongpt.security"}
    assert {"login_failed", "auth_rate_limited"} <= names
    assert all(getattr(r, "request_id", None) for r in caplog.records if r.name == "decisiongpt.security")


def test_rate_limit_and_auth_responses_are_not_cacheable_and_carry_security_headers(client, rate_limit_on):
    r = client.post(LOGIN, json={"email": "a@example.com", "password": PW})
    assert r.headers["Cache-Control"] == "no-store" and r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY" and "default-src 'none'" in r.headers["Content-Security-Policy"]
    assert "Strict-Transport-Security" not in r.headers                                      # development: only hardened environments send HSTS
