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


class UnitsHistoryPointOut(BaseModel):
    date: str
    units_sold: float


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
    # Honest-uncertainty and provenance fields (additive; older clients ignore them).
    warnings: list[str] = []
    interval_method: str = "model_test_rmse"
    interval_reliable: bool = False
    data_as_of: date | None = None
    trained_on: str | None = None
    metrics_scope: str = "model's own held-out test set (not this business)"
    # business-specific forecast description
    forecast_basis: str = "registered_model"  # business_specific_validated | business_specific_baseline | limited_estimate
    target: str = "units_sold"
    target_unit: str = "units per calendar day (all products)"
    aggregation: str = "business_daily_total"
    data_profile: dict = {}
    validation: dict = {}
    registered_model_note: str | None = None
    # provenance (additive): identifies exactly what was forecast so it can be saved and later evaluated
    fingerprint: str | None = None
    dataset_sha256: str | None = None
    generated_at: str | None = None
    horizon_requested: int | None = None
    horizon_returned: int | None = None
    forecast_start: date | None = None
    forecast_end: date | None = None
    data_cutoff: date | None = None
    references: dict = {}


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
    # What the number is, and what it is not (additive fields).
    score_meaning: str = ""
    label_provenance: str = "unknown"
    trained_on: str | None = None
    metrics_scope: str = "model's own held-out test set (not this business)"
    warnings: list[str] = []


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
