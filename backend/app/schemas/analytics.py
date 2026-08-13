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


class PeriodComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    current_revenue: float
    previous_revenue: float
    change_absolute: float
    change_pct: float | None
    current_orders: int
    previous_orders: int


class ProductPerformanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    name: str
    units_sold: int
    revenue: float


class ChannelPerformanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    channel: str
    spend: float
    attributed_revenue: float | None
    roi: float | None
    campaigns: int


class CustomerSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_customers: int
    customers_with_purchase_history: int
    avg_monetary_value: float | None
    avg_purchase_frequency: float | None
    new_customers_last_30_days: int


class InventoryStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    product_name: str
    current_stock: int
    reorder_level: int | None
    low_stock: bool
