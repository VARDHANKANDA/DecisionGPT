"""Auth service - register, authenticate, change password, revoke sessions."""
import logging
from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError, ValidationFailedError
from app.core.security import (
    burn_password_check, check_password_policy, create_token, hash_password, password_needs_rehash, verify_password,
)
from app.models.auth_state import RevokedToken
from app.models.user import ROLE_SME, ROLES, User
from app.services import rate_limit_service as limiter

security_log = logging.getLogger("decisiongpt.security")


class AuthError(AppError):
    code = "AUTH_FAILED"
    http_status = 401


def register(db: Session, *, email: str, password: str, full_name: str | None = None, role: str = ROLE_SME) -> User:
    email = email.strip().lower()
    if role not in ROLES:
        raise ValidationFailedError(f"Unknown role '{role}'.")
    try:
        check_password_policy(password, email=email)
    except ValueError as exc:
        raise ValidationFailedError(str(exc))
    if db.query(User).filter(User.email == email).first() is not None:
        raise ValidationFailedError("An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(password), full_name=full_name, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, *, email: str, password: str, address: str = "unknown") -> tuple[User, str]:
    """Check the credentials. Too many failures for this address / account / pair => RateLimitedError BEFORE the password is looked at.
    An unknown account costs the same hashing time as a wrong password, and both give the identical error."""
    email = email.strip().lower()
    limiter.enforce_login(db, email, address)
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        burn_password_check(password)
        ok = False
    else:
        ok = user.is_active and verify_password(password, user.password_hash)
    if not ok:
        limiter.login_failed(db, email, address)
        security_log.warning("login_failed", extra={"client_address": address})
        raise AuthError("Incorrect email or password.")
    if password_needs_rehash(user.password_hash):       # legacy PBKDF2 or weaker Argon2 parameters: upgrade now that we hold the password
        user.password_hash = hash_password(password)
        db.commit()
    limiter.login_succeeded(db, email, address)
    return user, issue_token(user)


def issue_token(user: User) -> str:
    return create_token(user_id=user.id, token_version=user.token_version)


def revoke_all_sessions(db: Session, user: User) -> None:
    """Invalidate every token already issued to this user (they must sign in again)."""
    user.token_version = int(user.token_version or 0) + 1
    db.commit()


def revoke_token(db: Session, *, jti: str, user_id: str, expires_at: int) -> None:
    """Refuse one token before its expiry (sign-out). Idempotent."""
    if db.get(RevokedToken, jti) is None:
        db.add(RevokedToken(jti=jti, user_id=user_id, expires_at=datetime.fromtimestamp(expires_at, timezone.utc)))
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(timezone.utc)))   # rows past expiry no longer matter
    db.commit()


def change_password(db: Session, user: User, *, current_password: str, new_password: str, address: str = "unknown") -> str:
    """Replace the password, end every other session and return a fresh token for the caller."""
    limiter.enforce_password_change(db, user.id, address)
    if not verify_password(current_password, user.password_hash):
        limiter.password_change_failed(db, user.id)
        raise AuthError("The current password is incorrect.")
    try:
        check_password_policy(new_password, email=user.email)
    except ValueError as exc:
        raise ValidationFailedError(str(exc))
    if verify_password(new_password, user.password_hash):
        raise ValidationFailedError("The new password must be different from the current one.")
    user.password_hash = hash_password(new_password)
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    security_log.warning("password_changed", extra={"user_id": str(user.id)})
    return issue_token(user)


def operator_reset(db: Session, email: str, *, new_password: str | None = None, active: bool | None = None) -> User:
    """Account recovery by whoever operates the deployment (there is no self-service reset: it would need a verified email channel). Sets a new
    password that satisfies the same policy as sign-up and/or activates or deactivates the account, and in every case ends every session the
    account holds. Used by scripts/reset_password.py."""
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if user is None:
        raise NotFoundError("No account with that email.")
    if new_password is not None:
        try:
            check_password_policy(new_password, email=user.email)
        except ValueError as exc:
            raise ValidationFailedError(str(exc))
        user.password_hash = hash_password(new_password)
    if active is not None:
        user.is_active = active
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    security_log.warning("account_changed_by_operator", extra={"user_id": str(user.id), "password_reset": new_password is not None,
                                                              "active": user.is_active})
    return user


def get_user(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    return user
