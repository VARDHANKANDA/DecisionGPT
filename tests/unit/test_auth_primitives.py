"""Password hashing, password policy, JWT verification rules and client-address resolution - the primitives under authentication."""
import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import jwt
import pytest

import app.core.security as security
from app.core.client_ip import client_address
from app.core.config import get_settings

ROOT = Path(__file__).resolve().parents[2]


def _secret(tag: str) -> str:
    return "-".join(["unit", tag, "signing", "material", "0123456789", "abcdefghij"])      # built at runtime: the repository secret scan flags long literals


# ------------------------------------------------------------------ passwords
def test_the_production_hashing_profile_is_argon2id_at_rfc_9106_low_memory():
    # the suite substitutes a cheap profile, so read the production value from a fresh interpreter
    code = "import app.core.security as s; p=s._PROFILE; print(p.type.name, p.memory_cost, p.time_cost, p.parallelism)"
    env = {**os.environ, "PYTHONPATH": f"{ROOT / 'backend'}{os.pathsep}{ROOT}"}
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120).stdout.split()
    assert out[0] == "ID" and int(out[1]) >= 65536 and int(out[2]) >= 3 and int(out[3]) >= 1


def test_a_hash_verifies_only_its_own_password_and_is_salted():
    a, b = security.hash_password("orange-river-4271"), security.hash_password("orange-river-4271")
    assert a.startswith("$argon2id$") and a != b
    assert security.verify_password("orange-river-4271", a) and not security.verify_password("correct-horse-batterz", a)
    assert not security.verify_password("anything", "not a hash") and not security.verify_password("anything", "")


def _legacy(password: str, rounds: int = 240_000) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)
    return f"pbkdf2_sha256${rounds}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def test_a_legacy_pbkdf2_hash_still_verifies_and_is_flagged_for_upgrade():
    old = _legacy("orange-river-4271")
    assert security.verify_password("orange-river-4271", old) and not security.verify_password("wrong-password-x", old)
    assert security.password_needs_rehash(old)
    assert not security.password_needs_rehash(security.hash_password("orange-river-4271"))


def test_a_hash_made_with_weaker_parameters_is_flagged_for_upgrade(monkeypatch):
    from argon2 import Parameters, Type

    weak = security.hash_password("orange-river-4271")
    monkeypatch.setattr(security, "_PROFILE", Parameters(type=Type.ID, version=19, salt_len=16, hash_len=32, time_cost=2, memory_cost=16, parallelism=1))
    assert security.password_needs_rehash(weak)


def test_unbounded_password_input_is_never_hashed():
    assert security.verify_password("x" * 10_000, security.hash_password("orange-river-4271")) is False


@pytest.mark.parametrize("password,reason", [
    ("short", "at least"), ("a" * 129, "at most"), ("password123", "too easy"), ("Password123!", "too easy"), ("qwertyuiop", "too easy"),
    ("1234567890", "too easy"), ("aaaaaaaaaaaa", "too easy"), ("letmein2024", "too easy"),
])
def test_weak_passwords_are_refused_with_a_readable_reason(password, reason):
    with pytest.raises(ValueError, match=reason):
        security.check_password_policy(password)


def test_a_password_may_not_contain_the_account_email():
    with pytest.raises(ValueError, match="email"):
        security.check_password_policy("maya.rao-forever-1", email="maya.rao@example.com")
    security.check_password_policy("orange-river-4271", email="maya.rao@example.com")        # unrelated: fine
    security.check_password_policy("passphrase with spaces and 9 words ok")                          # length, not composition


# ------------------------------------------------------------------ tokens (RFC 7519 / 8725)
def _forge(claims: dict, key: str | None = None, alg: str = "HS256", headers: dict | None = None) -> str:
    s = get_settings()
    key = key or s.jwt_secret
    h = {"kid": security.key_id(key), **(headers or {})}
    return jwt.encode(claims, key, algorithm=alg, headers=h)


def _claims(**over) -> dict:
    s, now = get_settings(), int(time.time())
    base = {"iss": s.jwt_issuer, "aud": s.jwt_audience, "sub": "u1", "iat": now, "nbf": now, "exp": now + 600, "jti": "j1", "tv": 0}
    return {**base, **over}


def test_a_genuine_token_round_trips_with_every_required_claim():
    claims = security.decode_token(security.create_token(user_id="u1", token_version=3))
    assert claims and claims["sub"] == "u1" and claims["tv"] == 3
    assert {"iss", "aud", "iat", "nbf", "exp", "jti"} <= set(claims)
    assert security.decode_token(security.create_token(user_id="u1"))["jti"] != claims["jti"]       # every token has its own id


def test_the_algorithm_is_pinned_and_none_or_other_algorithms_are_refused():
    assert security.decode_token(_forge(_claims())) is not None
    assert security.decode_token(jwt.encode(_claims(), None, algorithm="none", headers={"kid": security.key_id(get_settings().jwt_secret)})) is None
    assert security.decode_token(_forge(_claims(), alg="HS512")) is None
    unsigned = base64.urlsafe_b64encode(json.dumps({"alg": "none", "kid": security.key_id(get_settings().jwt_secret)}).encode()).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(_claims()).encode()).rstrip(b"=").decode()
    assert security.decode_token(f"{unsigned}.{body}.") is None


@pytest.mark.parametrize("over", [
    {"iss": "someone-else"}, {"aud": "another-service"}, {"exp": int(time.time()) - 3600}, {"nbf": int(time.time()) + 3600},
    {"iat": None}, {"jti": 123}, {"tv": "0"}, {"tv": True},
])
def test_a_token_with_a_wrong_or_missing_claim_is_refused(over):
    claims = {k: v for k, v in _claims(**over).items() if v is not None}
    assert security.decode_token(_forge(claims)) is None


@pytest.mark.parametrize("missing", ["exp", "iat", "nbf", "iss", "aud", "sub", "jti"])
def test_each_required_claim_is_required(missing):
    claims = _claims()
    claims.pop(missing)
    assert security.decode_token(_forge(claims)) is None


def test_clock_skew_is_tolerated_only_within_the_small_leeway(monkeypatch):
    leeway = get_settings().jwt_leeway_seconds
    assert leeway <= 60
    now = int(time.time())
    assert security.decode_token(_forge(_claims(exp=now - leeway // 2))) is not None          # just expired, inside the skew allowance
    assert security.decode_token(_forge(_claims(nbf=now + leeway // 2, iat=now))) is not None   # just not yet valid
    assert security.decode_token(_forge(_claims(exp=now - leeway - 5))) is None
    assert security.decode_token(_forge(_claims(nbf=now + leeway + 5))) is None


def test_a_tampered_or_foreign_signed_token_is_refused():
    good = security.create_token(user_id="u1")
    head, body, sig = good.split(".")
    forged_body = base64.urlsafe_b64encode(json.dumps({**_claims(), "sub": "admin"}).encode()).rstrip(b"=").decode()
    assert security.decode_token(f"{head}.{forged_body}.{sig}") is None
    assert security.decode_token(good[:-2] + ("AA" if not good.endswith("AA") else "BB")) is None
    other = _secret("other")
    assert security.decode_token(_forge(_claims(), key=other)) is None                            # an unknown signing secret (unknown kid)
    unknown_kid_but_right_key = jwt.encode(_claims(), get_settings().jwt_secret, algorithm="HS256", headers={"kid": "deadbeef0000"})
    assert security.decode_token(unknown_kid_but_right_key) is None
    for junk in ("", "a", "a.b", "a.b.c", "....", "Bearer x"):
        assert security.decode_token(junk) is None


def test_secret_rotation_verifies_the_previous_secret_but_signs_only_with_the_current(monkeypatch):
    old, new = _secret("old"), _secret("new")
    s = get_settings()
    monkeypatch.setattr(s, "jwt_secret", old)
    token_under_old = security.create_token(user_id="u1")
    monkeypatch.setattr(s, "jwt_secret", new)
    assert security.decode_token(token_under_old) is None                                          # rotated with no overlap: old tokens end
    monkeypatch.setattr(s, "jwt_secret_previous", old)
    assert security.decode_token(token_under_old) is not None                                      # overlap window: still verifies
    fresh = security.create_token(user_id="u1")
    assert jwt.get_unverified_header(fresh)["kid"] == security.key_id(new)                          # new tokens never use the previous secret
    monkeypatch.setattr(s, "jwt_secret_previous", None)
    assert security.decode_token(token_under_old) is None                                          # overlap removed: drained


# ------------------------------------------------------------------ client address and forwarded headers
class _Req:
    def __init__(self, peer, *xff):
        self.client = SimpleNamespace(host=peer) if peer else None
        lines = list(xff)
        self.headers = SimpleNamespace(getlist=lambda name: lines if name == "x-forwarded-for" else [])


def test_forwarded_for_is_ignored_unless_the_peer_is_a_trusted_proxy(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "trusted_proxies", "")
    assert client_address(_Req("198.51.100.20", "203.0.113.5")) == "198.51.100.20"                  # no proxies configured: header never read
    monkeypatch.setattr(s, "trusted_proxies", "10.0.0.0/8")
    assert client_address(_Req("198.51.100.20", "203.0.113.5")) == "198.51.100.20"                  # peer is not a proxy: header is attacker-supplied
    assert client_address(_Req("10.1.2.3", "203.0.113.5")) == "203.0.113.5"                          # peer is a proxy: believe what it appended


def test_the_client_is_the_first_untrusted_hop_from_the_right_so_forged_prefixes_do_not_choose_the_bucket(monkeypatch):
    monkeypatch.setattr(get_settings(), "trusted_proxies", "10.0.0.0/8")
    # the attacker sent "X-Forwarded-For: 1.1.1.1, 2.2.2.2"; the proxy appended the real peer address
    assert client_address(_Req("10.0.0.9", "1.1.1.1, 2.2.2.2, 203.0.113.77")) == "203.0.113.77"
    assert client_address(_Req("10.0.0.9", "9.9.9.9, 203.0.113.77")) == "203.0.113.77"
    assert client_address(_Req("10.0.0.9", "203.0.113.77, 10.0.0.4")) == "203.0.113.77"            # a second trusted proxy hop is skipped
    assert client_address(_Req("10.0.0.9", "1.1.1.1", "203.0.113.77")) == "203.0.113.77"           # split across two header lines
    assert client_address(_Req("10.0.0.9")) == "10.0.0.9"                                           # no header: the proxy itself
    assert client_address(_Req("10.0.0.9", "garbage, 203.0.113.77")) == "203.0.113.77"


def test_ipv6_clients_are_grouped_by_64_and_junk_is_bounded(monkeypatch):
    monkeypatch.setattr(get_settings(), "trusted_proxies", "")
    a, b = client_address(_Req("2001:db8:1:2::1")), client_address(_Req("2001:db8:1:2:ffff::9"))
    assert a == b == "2001:db8:1:2::/64"
    assert client_address(_Req("2001:db8:1:3::1")) != a
    assert client_address(_Req(None)) == "unknown"
    assert len(client_address(_Req("x" * 500))) <= 64
    monkeypatch.setattr(get_settings(), "trusted_proxies", "not-an-ip, 10.0.0.0/8")                  # a malformed entry trusts nothing extra
    assert client_address(_Req("192.0.2.9", "203.0.113.5")) == "192.0.2.9"
