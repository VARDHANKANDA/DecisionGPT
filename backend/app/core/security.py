"""Password hashing + signed bearer tokens — standard-library only, no new
dependency. PBKDF2-HMAC-SHA256 for passwords; a compact HMAC-signed JSON
token for sessions (issued by /api/v1/auth/login, TTL from settings).

This is deliberately simple and self-contained for a research prototype.
docs/DEPLOYMENT.md §6 already flags that a production deployment should
move to a vetted auth stack (OAuth/OIDC, managed sessions, rotation).
"""
import base64
import hashlib
import hmac
import json
import os
import time

from app.core.config import get_settings

_PBKDF2_ROUNDS = 240_000


def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
        return hmac.compare_digest(dk, expected)
    except Exception:  # noqa: BLE001 - any malformed hash => not a match
        return False


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_token(*, user_id: str, role: str, ttl_seconds: int | None = None) -> str:
    settings = get_settings()
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + (ttl_seconds or settings.jwt_ttl_seconds),
    }
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(settings.jwt_secret.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64url(sig)}"


def decode_token(token: str) -> dict | None:
    settings = get_settings()
    try:
        body, sig = token.split(".")
        expected = hmac.new(settings.jwt_secret.encode(), body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url_decode(sig), expected):
            return None
        payload = json.loads(_b64url_decode(body))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:  # noqa: BLE001
        return None
