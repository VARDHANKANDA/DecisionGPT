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
    mappings: dict[str, dict[str, str]] = {}
    # {table: {field: "day_first" | "month_first"}}: the person's answer when a date like 03/04/2026 could be read two ways
    date_orders: dict[str, dict[str, str]] = {}


class DataSummaryOut(BaseModel):
    products: int
    customers: int
    sales: int
    marketing_campaigns: int
    inventory_records: int
    finance_records: int = 0
    business_profile_set: bool = False


class CapabilityOut(BaseModel):
    feature: str
    enabled: bool
    reason: str
    requires: list[str]


class CapabilitiesOut(BaseModel):
    business_id: str
    data_summary: DataSummaryOut
    capabilities: list[CapabilityOut]
