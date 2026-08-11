from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ingestion import DataSummaryOut, IngestionJobOut, MappingConfirmRequest
from app.services import data_ingestion_service

router = APIRouter()


@router.post("/businesses/{business_id}/data/upload", response_model=IngestionJobOut)
async def upload_data(
    business_id: str,
    file: UploadFile = File(...),
    data_type: str | None = None,
    db: Session = Depends(get_db),
):
    content = await file.read()
    return data_ingestion_service.process_upload(db, business_id, file.filename, content, data_type)


@router.get("/businesses/{business_id}/data/jobs/{job_id}", response_model=IngestionJobOut)
def get_job(business_id: str, job_id: str, db: Session = Depends(get_db)):
    return data_ingestion_service.get_job(db, business_id, job_id)


@router.post("/businesses/{business_id}/data/mapping", response_model=IngestionJobOut)
def confirm_mapping(
    business_id: str,
    job_id: str,
    payload: MappingConfirmRequest,
    db: Session = Depends(get_db),
):
    return data_ingestion_service.confirm_mapping(db, business_id, job_id, payload.mappings)


@router.get("/businesses/{business_id}/data/summary", response_model=DataSummaryOut)
def get_data_summary(business_id: str, db: Session = Depends(get_db)):
    return data_ingestion_service.get_data_summary(db, business_id)
