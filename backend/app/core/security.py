"""Password hashing and signed session tokens, built on maintained libraries and published standards.

* Passwords: Argon2id (RFC 9106, via ``argon2-cffi``) with the RFC's "low memory" parameters (OWASP's first-choice algorithm). Hashes written
  by the previous implementation (PBKDF2-HMAC-SHA256, 240 000 rounds) still verify and are replaced by an Argon2id hash at the next successful
  sign-in (``password_needs_rehash``), so no user is locked out and no bulk migration is needed.
* Tokens: JSON Web Tokens (RFC 7519) signed with HMAC-SHA256 through ``PyJWT``, following RFC 8725: the algorithm is pinned on verification
  (never read from the token, ``none`` is not accepted), issuer, audience, expiry, not-before, issued-at, subject and a unique id are all required,
  the clock-skew allowance is small and explicit, and a ``kid`` header picks the signing secret so a rotation can keep verifying the
  previous secret (``JWT_SECRET_PREVIOUS``) until old tokens expire.

Authorisation never trusts a claim about the user: the role, the active flag and the token version are read from the database on every request
(``app/api/deps.py``). This module is only about proving that a token is genuine and unexpired.

docs/PRODUCTION_SECURITY_REVIEW.md explains why this is not a hosted identity provider and what that leaves open.
"""
import base64
import hashlib
import hmac
import re
import time
import uuid

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.profiles import RFC_9106_LOW_MEMORY

from app.core.config import get_settings

_PROFILE = RFC_9106_LOW_MEMORY            # m=64 MiB, t=3, p=4; the test suite substitutes a cheap profile (tests/conftest.py)
_LEGACY_PREFIX = "pbkdf2_sha256$"

MIN_PASSWORD_CHARS = 10
MAX_PASSWORD_CHARS = 128                  # bounds the work a single request can demand of the hasher
_COMMON_BASES = {
    "password", "passw0rd", "qwerty", "qwertyuiop", "welcome", "letmein", "admin", "administrator", "iloveyou", "changeme", "dragon",
    "monkey", "football", "baseball", "abc", "abcdef", "abcdefgh", "trustno", "sunshine", "master", "login", "princess", "superman",
    "whatever", "freedom", "shadow", "zaq", "asdfgh", "asdfghjkl", "zxcvbnm", "decisiongpt", "business", "india", "123456", "000000",
}


def check_password_policy(password: str, *, email: str | None = None) -> None:
    """Raise ``ValueError`` with a plain-language reason when the password is not acceptable.

    Length first (NIST SP 800-63B: length matters more than composition), then a screen against the most common choices, the account's own
    email, and passwords that are a single repeated character. It is a screen, not a breached-password check: that needs an outbound lookup
    (docs/PRODUCTION_SECURITY_REVIEW.md lists it as an open item).
    """
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_CHARS:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_CHARS} characters.")
    if len(password) > MAX_PASSWORD_CHARS:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_CHARS} characters.")
    low = password.lower()
    base = re.sub(r"[\d\W_]+$", "", low)                                   # "Password123!" -> "password"
    if len(set(low)) == 1 or base in _COMMON_BASES or low.strip("0123456789") == "":
        raise ValueError("That password is too easy to guess. Choose a longer or less common one.")
    if email:
        local = email.strip().lower().split("@")[0]
        if low == email.strip().lower() or (len(local) >= 4 and local in low):
            raise ValueError("The password must not contain your email address.")


def _hasher() -> PasswordHasher:
    return PasswordHasher.from_parameters(_PROFILE)


def hash_password(password: str) -> str:
    """Argon2id hash (self-describing: parameters and salt are inside the string). No policy is applied here: callers that accept a
    new password from a person call ``check_password_policy`` first."""
    if not password:
        raise ValueError("Password must not be empty.")
    return _hasher().hash(password)


def _verify_legacy_pbkdf2(password: str, stored: str) -> bool:
    try:
        _, rounds, salt_b64, hash_b64 = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(rounds))
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except Exception:  # noqa: BLE001 - any malformed hash => not a match
        return False


def verify_password(password: str, stored: str) -> bool:
    if len(password) > MAX_PASSWORD_CHARS * 2:        # never hash an unbounded input, whatever the caller validated
        return False
    if stored.startswith(_LEGACY_PREFIX):
        return _verify_legacy_pbkdf2(password, stored)
    try:
        return _hasher().verify(stored, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(stored: str) -> bool:
    """True for a legacy PBKDF2 hash or an Argon2 hash made with weaker parameters than the current profile."""
    if stored.startswith(_LEGACY_PREFIX):
        return True
    try:
        return _hasher().check_needs_rehash(stored)
    except InvalidHashError:
        return True


_dummy: str | None = None


def burn_password_check(password: str) -> None:
    """Spend the same hashing time as a real check. Used when the account does not exist, so response time does not reveal whether an
    email is registered."""
    global _dummy
    if _dummy is None or password_needs_rehash(_dummy):
        _dummy = hash_password(uuid.uuid4().hex)
    verify_password(password, _dummy)


# ---------------------------------------------------------------- tokens

ALGORITHM = "HS256"
_REQUIRED = ["exp", "iat", "nbf", "iss", "aud", "sub", "jti"]


def key_id(secret: str) -> str:
    """A short public fingerprint of a signing secret (the ``kid`` header). A truncated SHA-256 of a long random secret reveals nothing usable."""
    return hashlib.sha256(secret.encode()).hexdigest()[:12]


def create_token(*, user_id: str, token_version: int = 0, ttl_seconds: int | None = None) -> str:
    s = get_settings()
    now = int(time.time())
    claims = {
        "iss": s.jwt_issuer, "aud": s.jwt_audience, "sub": str(user_id), "iat": now, "nbf": now,
        "exp": now + (ttl_seconds or s.jwt_ttl_seconds), "jti": uuid.uuid4().hex, "tv": int(token_version),
    }
    return jwt.encode(claims, s.jwt_secret, algorithm=ALGORITHM, headers={"kid": key_id(s.jwt_secret)})


def decode_token(token: str) -> dict | None:
    """The verified claims, or None for anything that is not a genuine, current token for this service (bad signature, wrong algorithm,
    issuer or audience, expired, not yet valid, missing a required claim, signed by an unknown secret)."""
    s = get_settings()
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        secrets = [s.jwt_secret] + ([s.jwt_secret_previous] if s.jwt_secret_previous else [])
        key = next((k for k in secrets if hmac.compare_digest(key_id(k).encode(), str(kid).encode())), None)
        if key is None:
            return None
        claims = jwt.decode(
            token, key, algorithms=[ALGORITHM], audience=s.jwt_audience, issuer=s.jwt_issuer, leeway=s.jwt_leeway_seconds,
            options={"require": _REQUIRED},
        )
    except jwt.PyJWTError:
        return None
    if not isinstance(claims.get("jti"), str) or not isinstance(claims.get("tv"), int) or isinstance(claims.get("tv"), bool):
        return None
    return claims
