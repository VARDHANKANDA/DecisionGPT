from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, verify_business_access
from app.db.session import get_db
from app.models.user import User
from app.schemas.business import BusinessCreate, BusinessOut, BusinessUpdate
from app.services import business_service, demo_business_service

router = APIRouter()


@router.post("/businesses", response_model=BusinessOut, status_code=201)
def create_business(
    payload: BusinessCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    return business_service.create_business(db, payload, owner_user_id=user.id if user else None)


@router.post("/businesses/demo", response_model=BusinessOut, status_code=201)
def create_demo_business(
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """docs/PRD.md §38 "Try Demo Business" — provisions a fresh synthetic
    Indian D2C business with a full history. Owned by the caller when
    authenticated."""
    business_id = demo_business_service.create_demo_business(db)
    business = business_service.get_business(db, business_id)
    if user is not None:
        business.owner_user_id = user.id
        db.commit()
        db.refresh(business)
    return business


@router.get(
    "/businesses/{business_id}",
    response_model=BusinessOut,
    dependencies=[Depends(verify_business_access)],
)
def get_business(business_id: str, db: Session = Depends(get_db)):
    return business_service.get_business(db, business_id)


@router.patch(
    "/businesses/{business_id}",
    response_model=BusinessOut,
    dependencies=[Depends(verify_business_access)],
)
def update_business(business_id: str, payload: BusinessUpdate, db: Session = Depends(get_db)):
    return business_service.update_business(db, business_id, payload)
