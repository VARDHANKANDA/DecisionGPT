from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import UnauthenticatedError, claims_from_request, get_current_user, require_authenticated
from app.core.client_ip import client_address
from app.core.errors import BusinessAccessDeniedError
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest, TokenOut, UpdateProfileRequest, UserOut
from app.services import auth_service
from app.services import rate_limit_service as limiter

router = APIRouter()


@router.post("/auth/register", response_model=TokenOut, status_code=201)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    limiter.enforce_register(db, client_address(request))
    if payload.role != "sme":
        # public sign-up only ever creates a business account; administrators are created out of band (scripts/create_admin.py)
        raise BusinessAccessDeniedError("Only business accounts can be created through sign-up.")
    user = auth_service.register(
        db, email=payload.email, password=payload.password, full_name=payload.full_name, role=payload.role
    )
    return TokenOut(access_token=auth_service.issue_token(user), user=UserOut.model_validate(user))


@router.post("/auth/login", response_model=TokenOut)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user, token = auth_service.authenticate(db, email=payload.email, password=payload.password, address=client_address(request))
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/auth/me", response_model=UserOut)
def me(user: User | None = Depends(get_current_user)):
    if user is None:
        raise UnauthenticatedError("Not authenticated.")
    return user


@router.patch("/auth/profile", response_model=UserOut)
def update_profile(payload: UpdateProfileRequest, user: User | None = Depends(require_authenticated), db: Session = Depends(get_db)):
    if user is None:
        raise UnauthenticatedError("A valid bearer token is required.")
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip() or None
        db.commit()
        db.refresh(user)
    return user


@router.post("/auth/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)):
    """End THIS session: the presented token is refused from now on. Always 204, so the response says nothing about whether the token was valid."""
    claims = claims_from_request(request)
    if claims:
        auth_service.revoke_token(db, jti=claims["jti"], user_id=claims["sub"], expires_at=int(claims["exp"]))
    return Response(status_code=204)


@router.post("/auth/logout-all", status_code=204)
def logout_all(user: User | None = Depends(require_authenticated), db: Session = Depends(get_db)):
    """End EVERY session of the signed-in user, on every device."""
    if user is None:
        raise UnauthenticatedError("A valid bearer token is required.")
    auth_service.revoke_all_sessions(db, user)
    return Response(status_code=204)


@router.post("/auth/change-password", response_model=TokenOut)
def change_password(payload: ChangePasswordRequest, request: Request, user: User | None = Depends(require_authenticated),
                    db: Session = Depends(get_db)):
    """Needs the current password. Every other session ends; the response carries a fresh token for this one."""
    if user is None:
        raise UnauthenticatedError("A valid bearer token is required.")
    token = auth_service.change_password(
        db, user, current_password=payload.current_password, new_password=payload.new_password, address=client_address(request)
    )
    return TokenOut(access_token=token, user=UserOut.model_validate(user))
