from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

# Indian business-profile context (docs/INDIAN_SME_DATA_ARCHITECTURE.md).
# All optional — used only to condition recommendations, never to invent data.


class BusinessCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    industry: str
    business_type: str
    business_size: str
    country: str = "IN"
    currency: str = "INR"
    description: str | None = None

    state: str | None = None
    district: str | None = None
    city: str | None = None
    enterprise_type: str | None = None
    organisation_type: str | None = None
    major_activity: str | None = None
    nic_code: str | None = None
    registration_date: date | None = None


class BusinessUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    business_type: str | None = None
    business_size: str | None = None
    description: str | None = None

    state: str | None = None
    district: str | None = None
    city: str | None = None
    enterprise_type: str | None = None
    organisation_type: str | None = None
    major_activity: str | None = None
    nic_code: str | None = None
    registration_date: date | None = None


class BusinessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    industry: str
    business_type: str
    business_size: str
    country: str
    currency: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    state: str | None = None
    district: str | None = None
    city: str | None = None
    enterprise_type: str | None = None
    organisation_type: str | None = None
    major_activity: str | None = None
    nic_code: str | None = None
    registration_date: date | None = None
    business_age_years: int | None = None
