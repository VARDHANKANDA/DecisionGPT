from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.ingestion import (
    CapabilitiesOut,
    DataSummaryOut,
    IngestionJobOut,
    MappingConfirmRequest,
)
from app.services import capability_service, data_ingestion_service, data_management_service, training_readiness_service

router = APIRouter()


@router.post("/businesses/{business_id}/data/upload", response_model=IngestionJobOut)
async def upload_data(
    business_id: str,
    file: UploadFile = File(...),
    data_type: str | None = None,
    allow_duplicate_file: bool = False,
    db: Session = Depends(get_db),
):
    # Read at most limit+1 bytes: an oversized upload is detected without loading it all into memory.
    content = await file.read(get_settings().max_upload_bytes + 1)
    return data_ingestion_service.process_upload(db, business_id, file.filename or "upload", content, data_type, allow_duplicate_file)


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
    return data_ingestion_service.confirm_mapping(db, business_id, job_id, payload.mappings, payload.date_orders)


@router.get("/businesses/{business_id}/data/summary", response_model=DataSummaryOut)
def get_data_summary(business_id: str, db: Session = Depends(get_db)):
    return data_ingestion_service.get_data_summary(db, business_id)


@router.get("/businesses/{business_id}/data/forecast-readiness")
def get_forecast_readiness(business_id: str, db: Session = Depends(get_db)):
    """Facts about this business's stored sales that decide whether it can be forecast from and, later, used to train and evaluate a model:
    target and units, date range, zero-sale days vs gaps, returns, duplicates, price inconsistencies, provenance. Tenant-scoped, read-only."""
    return training_readiness_service.readiness(db, business_id)


@router.get("/businesses/{business_id}/data/capabilities", response_model=CapabilitiesOut)
def get_capabilities(business_id: str, db: Session = Depends(get_db)):
    """Which DecisionGPT features the SME's uploaded data currently unlocks,
    and exactly what to upload for the rest (docs/INDIAN_SME_DATA_ARCHITECTURE.md)."""
    return capability_service.get_capabilities(db, business_id)


# --- "My Data": see, add, edit and delete the data a business already has ---------


class RowsIn(BaseModel):
    rows: list[dict[str, Any]]


class RowChangesIn(BaseModel):
    changes: dict[str, Any]


@router.get("/businesses/{business_id}/data/library")
def get_library(business_id: str, db: Session = Depends(get_db)):
    return data_management_service.library(db, business_id)


@router.get("/businesses/{business_id}/data/uploads", response_model=list[IngestionJobOut])
def list_uploads(business_id: str, db: Session = Depends(get_db)):
    return data_management_service.upload_history(db, business_id)


@router.get("/businesses/{business_id}/data/tables/{table_type}")
def get_table(business_id: str, table_type: str, offset: int = 0, limit: int = 25, db: Session = Depends(get_db)):
    return data_management_service.list_rows(db, business_id, table_type, offset, limit)


@router.post("/businesses/{business_id}/data/tables/{table_type}/rows", status_code=201)
def add_rows(business_id: str, table_type: str, payload: RowsIn, db: Session = Depends(get_db)):
    return data_management_service.add_rows(db, business_id, table_type, payload.rows)


@router.patch("/businesses/{business_id}/data/tables/{table_type}/rows/{row_id}")
def update_row(business_id: str, table_type: str, row_id: str, payload: RowChangesIn, db: Session = Depends(get_db)):
    return data_management_service.update_row(db, business_id, table_type, row_id, payload.changes)


@router.delete("/businesses/{business_id}/data/tables/{table_type}/rows/{row_id}", status_code=204)
def delete_row(business_id: str, table_type: str, row_id: str, db: Session = Depends(get_db)):
    data_management_service.delete_row(db, business_id, table_type, row_id)


@router.delete("/businesses/{business_id}/data/tables/{table_type}")
def clear_table(business_id: str, table_type: str, db: Session = Depends(get_db)):
    return {"deleted": data_management_service.clear_table(db, business_id, table_type)}
