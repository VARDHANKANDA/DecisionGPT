"""Sales forecasting inference for a single business.

Reuses the exact feature engineering used to train the registered model
(ml/features/forecasting_features.py) — training and inference must build
features the same way or the model's learned weights are meaningless. This
is why ml/ is importable from the backend at runtime (see AGENTS.md /
docs/AI_MODULE_SPECIFICATION.md §11 "Inference: Business Data -> Feature
Pipeline -> Model -> Prediction").

Forecasting is refused (not guessed) when the business doesn't have enough
history — see docs/DATA_SPECIFICATION.md §4.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy.orm import Session

from app.core.errors import InsufficientDataError
from app.models.marketing import MarketingCampaign
from app.models.ml_model import MLModel
from app.models.sale import Sale
from app.services.model_registry_service import select_best_model

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FORECAST_MODEL_CANDIDATES = ["sales_forecast_naive", "sales_forecast_linear", "sales_forecast_xgboost"]

MIN_HISTORY_DAYS = 35
MIN_DISTINCT_SALE_DAYS = 20
ROLLING_WINDOW = 28
RECENT_MARKETING_WINDOW_DAYS = 7
UNCERTAINTY_Z = 1.28  # ~80% interval, assuming ~normal residuals


@dataclass
class ForecastPoint:
    forecast_date: date
    predicted_value: float
    lower_bound: float
    upper_bound: float


@dataclass
class ForecastResult:
    model_name: str
    model_version: str
    metrics: dict
    points: list[ForecastPoint] = field(default_factory=list)


def load_model(model_row: MLModel):
    return joblib.load(PROJECT_ROOT / model_row.model_path)


def build_daily_series(db: Session, business_id: str) -> pd.DataFrame:
    sales = (
        db.query(Sale)
        .filter(Sale.business_id == business_id)
        .order_by(Sale.sale_date)
        .all()
    )
    if not sales:
        return pd.DataFrame()

    sales_df = pd.DataFrame(
        [{"date": s.sale_date, "units": s.quantity, "revenue": float(s.revenue)} for s in sales]
    )
    daily = sales_df.groupby("date").agg(units_sold=("units", "sum"), revenue=("revenue", "sum")).reset_index()
    daily["price"] = (daily["revenue"] / daily["units_sold"]).round(2)

    full_range = pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")
    daily = daily.set_index("date")
    daily.index = pd.to_datetime(daily.index)
    daily = daily.reindex(full_range)
    daily["units_sold"] = daily["units_sold"].fillna(0)
    daily["price"] = daily["price"].ffill().bfill()
    daily = daily.reset_index().rename(columns={"index": "date"})

    campaigns = (
        db.query(MarketingCampaign)
        .filter(MarketingCampaign.business_id == business_id)
        .all()
    )
    if campaigns:
        mk_df = pd.DataFrame([{"date": c.campaign_date, "spend": float(c.spend)} for c in campaigns])
        mk_daily = mk_df.groupby("date")["spend"].sum().reset_index()
        mk_daily["date"] = pd.to_datetime(mk_daily["date"])
        daily = daily.merge(mk_daily, on="date", how="left")
        daily["spend"] = daily["spend"].fillna(0.0)
    else:
        daily["spend"] = 0.0

    daily["series_id"] = business_id
    daily["marketing_spend"] = daily["spend"]
    daily["promotion_flag"] = 0
    daily["date"] = daily["date"].dt.strftime("%Y-%m-%d")
    return daily[["series_id", "date", "units_sold", "price", "marketing_spend", "promotion_flag"]]


def recent_marketing_spend(history: pd.DataFrame, window: int = RECENT_MARKETING_WINDOW_DAYS) -> float:
    """Marketing spend to project forward as "business as usual".

    Unlike price (forward/back-filled in build_daily_series from real
    observed prices), a day with no campaign row is filled with a real 0 —
    campaigns aren't run daily for most businesses. Reading only the single
    last calendar day would make the projection's marketing assumption
    depend on whether a campaign happened to land on that exact day, so we
    average over a trailing window instead.
    """
    return round(float(history["marketing_spend"].tail(window).mean()), 2)


def check_forecast_sufficiency(db: Session, business_id: str) -> tuple[bool, str | None]:
    daily = build_daily_series(db, business_id)
    if daily.empty:
        return False, "No sales history on file yet."
    span_days = len(daily)
    distinct_sale_days = int((daily["units_sold"] > 0).sum())
    if span_days < MIN_HISTORY_DAYS:
        return False, f"Only {span_days} days of sales history on file — at least {MIN_HISTORY_DAYS} are needed."
    if distinct_sale_days < MIN_DISTINCT_SALE_DAYS:
        return False, (
            f"Only {distinct_sale_days} days with recorded sales — at least {MIN_DISTINCT_SALE_DAYS} are needed "
            "for a reliable forecast."
        )
    return True, None


def build_feature_row(series: list[float], forecast_date, price: float, marketing_spend: float) -> pd.DataFrame:
    """The exact feature row the model sees for one prediction step, given
    the units-sold history so far. Exposed (not just inlined in
    run_recursive_forecast) so explainability_service can compute SHAP
    values against the identical row a forecast/simulation actually used —
    an explanation of a feature row the model never saw would be
    meaningless.
    """
    from ml.features.forecasting_features import FEATURE_COLUMNS

    lag_1 = series[-1]
    lag_7 = series[-7] if len(series) >= 7 else series[0]
    rolling_mean_7 = sum(series[-7:]) / min(7, len(series))
    rolling_mean_28 = sum(series[-28:]) / min(28, len(series))

    return pd.DataFrame(
        [
            {
                "lag_1": lag_1,
                "lag_7": lag_7,
                "rolling_mean_7": rolling_mean_7,
                "rolling_mean_28": rolling_mean_28,
                "day_of_week": forecast_date.dayofweek,
                "is_weekend": int(forecast_date.dayofweek >= 5),
                "month": forecast_date.month,
                "price": price,
                "marketing_spend": marketing_spend,
                "promotion_flag": 0,
            }
        ]
    )[FEATURE_COLUMNS]


def run_recursive_forecast(
    model,
    units_series: list[float],
    last_date,
    price: float,
    marketing_spend: float,
    horizon_days: int,
    rmse: float = 0.0,
) -> list[ForecastPoint]:
    """The shared transition function `F` — the same trained model, fed
    forward one day at a time with the previous step's own prediction as
    the next lag feature. `price` and `marketing_spend` are held constant
    across the horizon; the Digital Twin (docs/DIGITAL_TWIN_SPECIFICATION.md
    §6 "S(t+1) = F(S(t), A(t), X(t))") calls this twice — once unmodified
    for the baseline, once with a scenario's adjusted price/marketing_spend
    — so "what changes" is entirely the model's own learned response to
    those two features, never a hand-picked multiplier.
    """
    series = list(units_series)
    points: list[ForecastPoint] = []
    for step in range(1, horizon_days + 1):
        forecast_date = last_date + timedelta(days=step)
        feature_row = build_feature_row(series, forecast_date, price, marketing_spend)

        predicted = max(0.0, float(model.predict(feature_row)[0]))
        series.append(predicted)

        points.append(
            ForecastPoint(
                forecast_date=forecast_date.date(),
                predicted_value=round(predicted, 2),
                lower_bound=round(max(0.0, predicted - UNCERTAINTY_Z * rmse), 2),
                upper_bound=round(predicted + UNCERTAINTY_Z * rmse, 2),
            )
        )

    return points


def forecast_sales(db: Session, business_id: str, horizon_days: int = 14) -> ForecastResult:
    from ml.features.forecasting_features import build_forecasting_features

    sufficient, reason = check_forecast_sufficiency(db, business_id)
    if not sufficient:
        raise InsufficientDataError(reason or "Not enough sales history for a forecast.")

    model_row = select_best_model(db, FORECAST_MODEL_CANDIDATES, metric="mae", minimize=True)
    if model_row is None:
        raise InsufficientDataError(
            "No forecasting model is registered yet. Run `python -m ml.training.train_forecasting` "
            "and sync the registry before requesting a forecast."
        )
    model = load_model(model_row)
    rmse = float(model_row.metrics_json.get("rmse", 0.0))

    daily = build_daily_series(db, business_id)
    history = daily.copy()
    history["date"] = pd.to_datetime(history["date"])
    featured_history = build_forecasting_features(history)
    if featured_history.empty:
        raise InsufficientDataError("Not enough contiguous sales history to build forecasting features.")

    units_series = list(history["units_sold"])
    last_price = float(history["price"].iloc[-1])
    last_marketing_spend = recent_marketing_spend(history)
    last_date = history["date"].iloc[-1]

    points = run_recursive_forecast(
        model, units_series, last_date, last_price, last_marketing_spend, horizon_days, rmse
    )

    return ForecastResult(
        model_name=model_row.model_name,
        model_version=model_row.version,
        metrics=model_row.metrics_json,
        points=points,
    )
