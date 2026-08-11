from datetime import date

from pydantic import BaseModel, ConfigDict


class KPIOut(BaseModel):
    period_start: date | None
    period_end: date | None
    revenue: float
    orders: int
    customers: int
    average_order_value: float | None
    profit: float | None
    marketing_spend: float
    marketing_roi: float | None
    conversion_rate: float | None
    notes: list[str]


class RevenueTrendPointOut(BaseModel):
    date: str
    revenue: float


class ForecastPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    forecast_date: date
    predicted_value: float
    lower_bound: float
    upper_bound: float


class ForecastOut(BaseModel):
    model_name: str
    model_version: str
    metrics: dict
    points: list[ForecastPointOut]


class ChurnPredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    customer_id: str
    external_customer_id: str | None
    churn_probability: float


class ChurnResultOut(BaseModel):
    model_name: str
    model_version: str
    metrics: dict
    predictions: list[ChurnPredictionOut]
