from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.business import BusinessCreate, BusinessOut, BusinessUpdate
from app.services import business_service, demo_business_service

router = APIRouter()


@router.post("/businesses", response_model=BusinessOut, status_code=201)
def create_business(payload: BusinessCreate, db: Session = Depends(get_db)):
    return business_service.create_business(db, payload)


@router.post("/businesses/demo", response_model=BusinessOut, status_code=201)
def create_demo_business(db: Session = Depends(get_db)):
    """docs/PRD.md §38 "Try Demo Business" — provisions a fresh synthetic
    Indian D2C business with a full history, every time it's called (never
    reuses a shared demo record, so one visitor's exploration never
    affects another's)."""
    business_id = demo_business_service.create_demo_business(db)
    return business_service.get_business(db, business_id)


@router.get("/businesses/{business_id}", response_model=BusinessOut)
def get_business(business_id: str, db: Session = Depends(get_db)):
    return business_service.get_business(db, business_id)


@router.patch("/businesses/{business_id}", response_model=BusinessOut)
def update_business(business_id: str, payload: BusinessUpdate, db: Session = Depends(get_db)):
    return business_service.update_business(db, business_id, payload)
