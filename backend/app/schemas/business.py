from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BusinessCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    industry: str
    business_type: str
    business_size: str
    country: str = "IN"
    currency: str = "INR"
    description: str | None = None


class BusinessUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    business_type: str | None = None
    business_size: str | None = None
    description: str | None = None


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
