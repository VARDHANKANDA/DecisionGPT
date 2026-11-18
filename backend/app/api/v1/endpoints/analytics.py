from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics import breakdown_service, churn_service, forecast_service, kpi_service
from app.db.session import get_db
from app.schemas.analytics import (
    ChannelPerformanceOut,
    ChurnResultOut,
    CustomerSummaryOut,
    ForecastOut,
    InventoryStatusOut,
    KPIOut,
    PeriodComparisonOut,
    ProductPerformanceOut,
    RevenueTrendPointOut,
    UnitsHistoryPointOut,
)

router = APIRouter()


@router.get("/businesses/{business_id}/analytics/kpis", response_model=KPIOut)
def get_kpis(business_id: str, period_days: int | None = None, db: Session = Depends(get_db)):
    return kpi_service.compute_kpis(db, business_id, period_days)


@router.get("/businesses/{business_id}/analytics/revenue-trend", response_model=list[RevenueTrendPointOut])
def get_revenue_trend(business_id: str, days: int = 90, db: Session = Depends(get_db)):
    return kpi_service.revenue_trend(db, business_id, days)


@router.get("/businesses/{business_id}/analytics/period-comparison", response_model=PeriodComparisonOut)
def get_period_comparison(business_id: str, days: int = 30, db: Session = Depends(get_db)):
    return kpi_service.period_over_period(db, business_id, days)


@router.get("/businesses/{business_id}/analytics/products", response_model=list[ProductPerformanceOut])
def get_top_products(business_id: str, limit: int = 10, db: Session = Depends(get_db)):
    return breakdown_service.top_products(db, business_id, limit)


@router.get("/businesses/{business_id}/analytics/marketing-channels", response_model=list[ChannelPerformanceOut])
def get_marketing_channels(business_id: str, db: Session = Depends(get_db)):
    return breakdown_service.marketing_by_channel(db, business_id)


@router.get("/businesses/{business_id}/analytics/customers", response_model=CustomerSummaryOut)
def get_customer_summary(business_id: str, db: Session = Depends(get_db)):
    return breakdown_service.customer_summary(db, business_id)


@router.get("/businesses/{business_id}/analytics/inventory", response_model=list[InventoryStatusOut])
def get_inventory_status(business_id: str, db: Session = Depends(get_db)):
    return breakdown_service.inventory_status(db, business_id)


@router.get("/businesses/{business_id}/analytics/units-history", response_model=list[UnitsHistoryPointOut])
def get_units_history(business_id: str, days: int = Query(60, ge=7, le=365), db: Session = Depends(get_db)):
    """Real daily units sold (days with no sales count as 0) — the series the forecast continues from."""
    daily = forecast_service.build_daily_series(db, business_id)
    if daily.empty:
        return []
    return [
        UnitsHistoryPointOut(date=str(row["date"]), units_sold=float(row["units_sold"]))
        for _, row in daily.tail(days).iterrows()
    ]


@router.post("/businesses/{business_id}/analytics/forecast", response_model=ForecastOut)
def post_forecast(business_id: str, horizon_days: int = Query(14, ge=1, le=forecast_service.MAX_HORIZON_DAYS), db: Session = Depends(get_db)):
    result = forecast_service.forecast_sales(db, business_id, horizon_days)
    return ForecastOut(
        model_name=result.model_name,
        model_version=result.model_version,
        metrics=result.metrics,
        points=result.points,
        warnings=result.warnings,
        interval_method=result.interval_method,
        interval_reliable=result.interval_reliable,
        data_as_of=result.data_as_of,
        trained_on=result.trained_on,
        metrics_scope=result.metrics_scope,
        forecast_basis=result.forecast_basis,
        target=result.target,
        target_unit=result.target_unit,
        aggregation=result.aggregation,
        data_profile=result.data_profile,
        validation=result.validation,
        registered_model_note=result.registered_model_note,
        fingerprint=result.fingerprint,
        dataset_sha256=result.dataset_sha256,
        generated_at=result.generated_at,
        horizon_requested=result.horizon_requested,
        horizon_returned=result.horizon_returned,
        forecast_start=result.forecast_start,
        forecast_end=result.forecast_end,
        data_cutoff=result.data_as_of,
        references=result.references,
    )


@router.post("/businesses/{business_id}/analytics/churn", response_model=ChurnResultOut)
def post_churn(business_id: str, db: Session = Depends(get_db)):
    predictions, model_row = churn_service.predict_churn(db, business_id)
    info = churn_service.describe_scores(model_row)
    return ChurnResultOut(
        model_name=model_row.model_name,
        model_version=model_row.version,
        metrics=model_row.metrics_json,
        predictions=predictions,
        score_meaning=info["score_meaning"],
        label_provenance=info["label_provenance"],
        trained_on=model_row.dataset_version,
        warnings=info["warnings"] + ([w] if (w := churn_service.data_age_warning(db, business_id)) else []),
    )
