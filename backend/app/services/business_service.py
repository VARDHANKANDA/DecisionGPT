from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.business import Business
from app.schemas.business import BusinessCreate, BusinessUpdate


def _age_years(registration_date: date | None) -> int | None:
    if registration_date is None:
        return None
    return max(0, (date.today() - registration_date).days // 365)


def create_business(db: Session, payload: BusinessCreate, owner_user_id: str | None = None) -> Business:
    business = Business(**payload.model_dump(), owner_user_id=owner_user_id)
    business.business_age_years = _age_years(payload.registration_date)
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
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(business, field, value)
    if "registration_date" in updates:
        business.business_age_years = _age_years(updates["registration_date"])
    db.commit()
    db.refresh(business)
    return business
