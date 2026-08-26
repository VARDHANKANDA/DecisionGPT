"""Auth service — register / authenticate users (Phase 4)."""
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError, ValidationFailedError
from app.core.security import create_token, hash_password, verify_password
from app.models.user import ROLE_SME, ROLES, User


class AuthError(AppError):
    code = "AUTH_FAILED"
    http_status = 401


def register(db: Session, *, email: str, password: str, full_name: str | None = None, role: str = ROLE_SME) -> User:
    email = email.strip().lower()
    if role not in ROLES:
        raise ValidationFailedError(f"Unknown role '{role}'.")
    if db.query(User).filter(User.email == email).first() is not None:
        raise ValidationFailedError("An account with this email already exists.")
    try:
        pw_hash = hash_password(password)
    except ValueError as exc:
        raise ValidationFailedError(str(exc))

    user = User(email=email, password_hash=pw_hash, full_name=full_name, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, *, email: str, password: str) -> tuple[User, str]:
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise AuthError("Incorrect email or password.")
    token = create_token(user_id=user.id, role=user.role)
    return user, token


def get_user(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    return user
