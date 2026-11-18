"""Authentication abuse protection shared by every worker and replica.

Counters are rows in ``rate_limit_buckets`` updated with a single atomic ``INSERT ... ON CONFLICT DO UPDATE ... RETURNING``, so concurrent
requests (threads, processes, replicas on one PostgreSQL) can neither lose an increment nor read a stale count between check and write. The
state is in the application database on purpose: an in-process limiter would give each of N workers its own budget and reset on restart.

Behaviour:
* fixed windows (a burst straddling a boundary can reach about twice the limit; each limit is small enough that this is acceptable);
* an attempt over the limit is refused with HTTP 429 and ``Retry-After`` BEFORE the password is checked, so a throttled caller learns
  nothing about whether a guess was right;
* nothing is locked: a limit only delays attempts until the window ends, and the counters expire by themselves, so an attacker can slow
  a victim's sign-in from the attacker's own address (and, at the much higher per-account limit, from anywhere) but cannot disable
  the account;
* subjects are stored as keyed hashes (HMAC of the secret) - never an email address or an IP address.

Buckets for sign-in count FAILURES; a successful sign-in clears only the (account, address) bucket, so an attacker cannot reset the
per-address or per-account counters by signing in to an account of their own.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.auth_state import RateLimitBucket

log = logging.getLogger("decisiongpt.security")
_now = time.time                                  # replaced by tests to move through windows deterministically


class RateLimitedError(AppError):
    code = "RATE_LIMITED"
    http_status = 429

    def __init__(self, retry_after: int, scope: str):
        super().__init__("Too many attempts. Please wait before trying again.", {"retry_after_seconds": retry_after})
        self.headers = {"Retry-After": str(retry_after)}
        self.scope = scope


@dataclass(frozen=True)
class Rule:
    scope: str
    limit: int
    window: int


def _subject(scope: str, value: str) -> str:
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, f"{scope}\x00{value}".encode(), hashlib.sha256).hexdigest()[:40]


def _bucket(rule: Rule, value: str, now: float) -> tuple[str, int]:
    index = int(now // rule.window)
    return f"{rule.scope}:{_subject(rule.scope, value)}:{index}", (index + 1) * rule.window


def _upsert(db: Session):
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        return pg_insert
    if dialect == "sqlite":
        return sqlite_insert
    raise RuntimeError(f"rate limiting supports PostgreSQL and SQLite, not {dialect}")


def _prune(db: Session, now: float) -> None:
    if random.random() < 0.02:                    # cheap amortised cleanup; expired windows are never read again
        db.execute(delete(RateLimitBucket).where(RateLimitBucket.expires_at < datetime.fromtimestamp(now - 60, timezone.utc)))


def current(db: Session, rule: Rule, value: str) -> tuple[int, int]:
    """(attempts counted in the current window, seconds until it ends) without recording anything."""
    now = _now()
    key, end = _bucket(rule, value, now)
    count = db.execute(select(RateLimitBucket.count).where(RateLimitBucket.key == key)).scalar() or 0
    return int(count), max(1, int(end - now))


def record(db: Session, rule: Rule, value: str) -> tuple[int, int]:
    """Count one attempt atomically and commit it at once, so the count survives whatever the request does next (including raising).
    Returns (count including this attempt, seconds until the window ends)."""
    now = _now()
    key, end = _bucket(rule, value, now)
    expires = datetime.fromtimestamp(end, timezone.utc)
    stmt = _upsert(db)(RateLimitBucket).values(key=key, count=1, expires_at=expires)
    stmt = stmt.on_conflict_do_update(index_elements=["key"], set_={"count": RateLimitBucket.count + 1}).returning(RateLimitBucket.count)
    count = int(db.execute(stmt).scalar_one())
    _prune(db, now)
    db.commit()
    return count, max(1, int(end - now))


def clear(db: Session, rule: Rule, value: str) -> None:
    key, _ = _bucket(rule, value, _now())
    db.execute(delete(RateLimitBucket).where(RateLimitBucket.key == key))
    db.commit()


def _refuse(rule: Rule, retry_after: int, address: str) -> RateLimitedError:
    log.warning("auth_rate_limited", extra={"scope": rule.scope, "client_address": address, "retry_after": retry_after})
    return RateLimitedError(retry_after, rule.scope)


# ------------------------------------------------------------------ policies

def _rules() -> dict[str, Rule]:
    s = get_settings()
    w = s.rate_limit_window_seconds
    return {
        "login_ip": Rule("login_ip", s.rate_limit_login_per_ip, w),
        "login_account_ip": Rule("login_account_ip", s.rate_limit_login_per_account_ip, w),
        "login_account": Rule("login_account", s.rate_limit_login_per_account, w),
        "register_ip": Rule("register_ip", s.rate_limit_register_per_ip, s.rate_limit_register_window_seconds),
        "password_change": Rule("password_change", s.rate_limit_password_change_per_user, w),
    }


def _login_subjects(email: str, address: str) -> list[tuple[Rule, str]]:
    r = _rules()
    email = email.strip().lower()
    return [(r["login_ip"], address), (r["login_account_ip"], f"{email}|{address}"), (r["login_account"], email)]


def enforce_login(db: Session, email: str, address: str) -> None:
    """Refuse (429) a sign-in attempt when any bucket for this address / account / pair is already full. Call before checking the password."""
    if not get_settings().rate_limit_enabled:
        return
    for rule, value in _login_subjects(email, address):
        count, wait = current(db, rule, value)
        if count >= rule.limit:
            raise _refuse(rule, wait, address)


def login_failed(db: Session, email: str, address: str) -> None:
    if not get_settings().rate_limit_enabled:
        return
    for rule, value in _login_subjects(email, address):
        record(db, rule, value)


def login_succeeded(db: Session, email: str, address: str) -> None:
    if not get_settings().rate_limit_enabled:
        return
    rule, value = _login_subjects(email, address)[1]
    clear(db, rule, value)


def enforce_register(db: Session, address: str) -> None:
    """Every sign-up attempt counts, successful or not (an account-creation flood is abusive even when each request is valid)."""
    if not get_settings().rate_limit_enabled:
        return
    rule = _rules()["register_ip"]
    count, wait = record(db, rule, address)
    if count > rule.limit:
        raise _refuse(rule, wait, address)


def enforce_password_change(db: Session, user_id: str, address: str) -> None:
    if not get_settings().rate_limit_enabled:
        return
    rule = _rules()["password_change"]
    count, wait = current(db, rule, user_id)
    if count >= rule.limit:
        raise _refuse(rule, wait, address)


def password_change_failed(db: Session, user_id: str) -> None:
    if get_settings().rate_limit_enabled:
        record(db, _rules()["password_change"], user_id)
