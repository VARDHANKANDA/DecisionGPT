from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import UnauthenticatedError, get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenOut, UserOut
from app.services import auth_service

router = APIRouter()


@router.post("/auth/register", response_model=TokenOut, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = auth_service.register(
        db, email=payload.email, password=payload.password, full_name=payload.full_name, role=payload.role
    )
    _, token = auth_service.authenticate(db, email=payload.email, password=payload.password)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/auth/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user, token = auth_service.authenticate(db, email=payload.email, password=payload.password)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/auth/me", response_model=UserOut)
def me(user: User | None = Depends(get_current_user)):
    if user is None:
        raise UnauthenticatedError("Not authenticated.")
    return user
