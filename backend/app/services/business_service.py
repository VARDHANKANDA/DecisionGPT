from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.business import Business
from app.schemas.business import BusinessCreate, BusinessUpdate


def create_business(db: Session, payload: BusinessCreate) -> Business:
    business = Business(**payload.model_dump())
    db.add(business)
    db.commit()
    db.refresh(business)
    return business


def get_business(db: Session, business_id: str) -> Business:
    business = db.get(Business, business_id)
    if business is None:
        raise NotFoundError(f"Business {business_id} not found.")
    return business


def update_business(db: Session, business_id: str, payload: BusinessUpdate) -> Business:
    business = get_business(db, business_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(business, field, value)
    db.commit()
    db.refresh(business)
    return business
