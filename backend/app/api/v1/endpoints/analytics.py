from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics import churn_service, forecast_service, kpi_service
from app.db.session import get_db
from app.schemas.analytics import ChurnResultOut, ForecastOut, KPIOut, RevenueTrendPointOut

router = APIRouter()


@router.get("/businesses/{business_id}/analytics/kpis", response_model=KPIOut)
def get_kpis(business_id: str, period_days: int | None = None, db: Session = Depends(get_db)):
    return kpi_service.compute_kpis(db, business_id, period_days)


@router.get("/businesses/{business_id}/analytics/revenue-trend", response_model=list[RevenueTrendPointOut])
def get_revenue_trend(business_id: str, days: int = 90, db: Session = Depends(get_db)):
    return kpi_service.revenue_trend(db, business_id, days)


@router.post("/businesses/{business_id}/analytics/forecast", response_model=ForecastOut)
def post_forecast(business_id: str, horizon_days: int = 14, db: Session = Depends(get_db)):
    result = forecast_service.forecast_sales(db, business_id, horizon_days)
    return ForecastOut(
        model_name=result.model_name,
        model_version=result.model_version,
        metrics=result.metrics,
        points=result.points,
    )


@router.post("/businesses/{business_id}/analytics/churn", response_model=ChurnResultOut)
def post_churn(business_id: str, db: Session = Depends(get_db)):
    predictions, model_row = churn_service.predict_churn(db, business_id)
    return ChurnResultOut(
        model_name=model_row.model_name,
        model_version=model_row.version,
        metrics=model_row.metrics_json,
        predictions=predictions,
    )
