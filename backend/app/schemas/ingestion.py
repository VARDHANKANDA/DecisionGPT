from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IngestionJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    filename: str
    status: str
    detected_types_json: list
    mapping_json: dict
    summary_json: dict
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class MappingConfirmRequest(BaseModel):
    mappings: dict[str, dict[str, str]]


class DataSummaryOut(BaseModel):
    products: int
    customers: int
    sales: int
    marketing_campaigns: int
    inventory_records: int
