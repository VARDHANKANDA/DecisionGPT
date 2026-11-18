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
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import InsufficientDataError, ValidationFailedError
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


MAX_HORIZON_DAYS = 90
STALE_AFTER_DAYS = 14  # last recorded day older than this -> a warning (not a refusal: the data may simply not have been refreshed)
SHORT_HISTORY_DAYS = 90


@dataclass
class ForecastResult:
    model_name: str
    model_version: str
    metrics: dict
    points: list[ForecastPoint] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    interval_method: str = "model_test_rmse"
    interval_reliable: bool = False
    data_as_of: date | None = None
    trained_on: str | None = None
    metrics_scope: str = "model's own held-out test set (not this business)"
    # Business-specific forecast description (additive; see business_forecast_service)
    forecast_basis: str = "registered_model"
    target: str = "units_sold"
    target_unit: str = "units per calendar day (all products)"
    aggregation: str = "business_daily_total"
    data_profile: dict = field(default_factory=dict)
    validation: dict = field(default_factory=dict)
    registered_model_note: str | None = None
    # Provenance (additive): what exactly was forecast, from which data, when
    fingerprint: str | None = None
    dataset_sha256: str | None = None
    generated_at: str | None = None
    horizon_requested: int | None = None
    horizon_returned: int | None = None
    forecast_start: date | None = None
    forecast_end: date | None = None
    references: dict = field(default_factory=dict)


def load_model(model_row: MLModel):
    return joblib.load(PROJECT_ROOT / model_row.model_path)


def select_forecast_model(db: Session) -> MLModel | None:
    """The single place that decides which registered model forecasts (shared by the forecast and the Digital Twin paths). Candidates are
    compared on their recorded VALIDATION MAE when all have one, otherwise on the legacy test MAE."""
    return select_best_model(db, FORECAST_MODEL_CANDIDATES, metric="mae", minimize=True, validation_metric="val_mae")


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


@lru_cache(maxsize=8)
def _platform_training_ranges(path_str: str, mtime: float) -> dict[str, tuple[float, float]]:
    from ml.features.forecasting_features import FEATURE_COLUMNS, build_forecasting_features

    df = build_forecasting_features(pd.read_csv(path_str))
    return {c: (float(df[c].quantile(0.05)), float(df[c].quantile(0.95))) for c in FEATURE_COLUMNS if c in df.columns}


def training_feature_ranges(model_row: MLModel) -> tuple[dict[str, tuple[float, float]] | None, str]:
    """(5th-95th percentile of each feature in the training data, where it came from). New models record ranges in their run metadata;
    for models trained on the bundled platform file they are recomputed from that file."""
    life = model_row.lifecycle_json or {}
    rng = (life.get("run_metadata") or {}).get("feature_ranges")
    if isinstance(rng, dict) and rng:
        return {k: (float(v[0]), float(v[1])) for k, v in rng.items()}, "run_metadata"
    if str(model_row.dataset_version or "").startswith("platform-forecasting"):
        path = PROJECT_ROOT / "data" / "platform" / "forecasting" / "sales_timeseries.csv"
        if path.exists():
            return _platform_training_ranges(str(path), path.stat().st_mtime), "platform_file"
    return None, "unknown"


def _registered_candidate(db: Session, business_id: str, history: pd.DataFrame, horizon: int):
    """(note, candidate). A registered model enters the business forecast ONLY when its recorded applicability says it was trained for
    this business's daily total of units; a synthetic-trained or per-series model is excluded and the reasons are returned as the note."""
    from app.services import model_applicability_service as applic

    row = select_forecast_model(db)
    if row is None:
        return "No registered forecasting model exists; the forecast uses this business's own history only.", None
    ranges, _src = training_feature_ranges(row)
    recent = float(history["units_sold"].astype(float).tail(28).mean())
    ok, reasons = applic.assess_business_forecast(row, business_id, recent, (ranges or {}).get("rolling_mean_28"))
    if not ok:
        return (f"The registered model {row.model_name} {row.version} was not used for this forecast: " + "; ".join(reasons) + ".", None)
    model = load_model(row)
    units = list(history["units_sold"].astype(float))
    dates = list(pd.to_datetime(history["date"]))
    prices = list(history["price"].astype(float))

    def candidate(t0: int, h: int):
        past = history.iloc[:t0]
        pts = run_recursive_forecast(model, units[:t0], pd.Timestamp(dates[t0 - 1]), prices[t0 - 1], recent_marketing_spend(past), h, 0.0)
        return np.asarray([p.predicted_value for p in pts], dtype=float)

    return f"The registered model {row.model_name} {row.version} was applicable and was evaluated as a candidate.", candidate


def _example_note(db: Session, business_id: str) -> str | None:
    from app.services.training_readiness_service import example_data_note

    return example_data_note(db, business_id)


def forecast_provenance(business_id: str, history: pd.DataFrame, horizon_requested: int, model_name: str, basis: str, interval_method: str,
                        points: list, units: np.ndarray) -> dict:
    """What identifies this forecast: the data it used, when it was made, the dates it covers and a fingerprint of its values.
    The fingerprint excludes warnings (which change with today's date) so that the same data and method give the same fingerprint."""
    import hashlib
    import json
    from datetime import datetime, timezone

    h = hashlib.sha256()
    for d, u in zip(pd.to_datetime(history["date"]).dt.strftime("%Y-%m-%d"), history["units_sold"].astype(float)):
        h.update(f"{d}|{u:.6f}\n".encode())
    dataset = h.hexdigest()
    body = {"business_id": str(business_id), "dataset": dataset, "horizon": len(points), "model": model_name, "basis": basis,
            "interval_method": interval_method,
            "points": [[p.forecast_date.isoformat(), round(float(p.predicted_value), 4), round(float(p.lower_bound), 4), round(float(p.upper_bound), 4)]
                       for p in points]}
    fp = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    n = len(points)
    return {
        "fingerprint": fp, "dataset_sha256": dataset, "generated_at": datetime.now(timezone.utc).isoformat(),
        "horizon_requested": int(horizon_requested), "horizon_returned": n,
        "forecast_start": points[0].forecast_date if points else None, "forecast_end": points[-1].forecast_date if points else None,
        "references": {"naive_last_daily": float(units[-1]) if len(units) else None,
                       "trailing_mean_28_daily": float(np.mean(units[-28:])) if len(units) else None,
                       "note": "constant per-day references computed at the same data cutoff"},
    }


def forecast_sales(db: Session, business_id: str, horizon_days: int = 14) -> ForecastResult:
    """The business's own daily-units forecast (see ``business_forecast_service``). Never uses a model that was not trained for this
    business's target, units and aggregation; a refusal (InsufficientDataError) is returned when there is too little history."""
    from app.analytics import business_forecast_service as bfs

    if not isinstance(horizon_days, int) or not 1 <= horizon_days <= MAX_HORIZON_DAYS:
        raise ValidationFailedError(f"horizon_days must be between 1 and {MAX_HORIZON_DAYS} (got {horizon_days!r}).")

    daily = build_daily_series(db, business_id)
    if daily.empty:
        raise InsufficientDataError("No sales history on file yet.")
    history = daily.copy()
    history["date"] = pd.to_datetime(history["date"])

    note, candidate = _registered_candidate(db, business_id, history, horizon_days)
    try:
        res = bfs.forecast(history, horizon_days, clock.today(), note, candidate)
    except ValueError as exc:
        raise InsufficientDataError(str(exc)) from exc

    names = {"registered_model": "registered_model"}
    method = names.get(res.method, res.method)
    units = history["units_sold"].astype(float).to_numpy()
    points = [ForecastPoint(p["forecast_date"], p["predicted_value"], p["lower_bound"], p["upper_bound"]) for p in res.points]
    provenance = forecast_provenance(business_id, history, horizon_days, f"business_baseline:{method}" if method != "registered_model" else "registered_model",
                                    res.basis, res.interval_method, points, units)
    return ForecastResult(
        model_name=f"business_baseline:{method}" if method != "registered_model" else "registered_model",
        model_version="per-business",
        metrics=res.metrics,
        points=points,
        warnings=res.warnings + ([note] if (note := _example_note(db, business_id)) else []),
        interval_method=res.interval_method,
        interval_reliable=res.interval_reliable,
        data_as_of=res.data_as_of,
        trained_on="this business's own sales history",
        metrics_scope=("this business's own chronological backtest (not a synthetic benchmark)" if res.basis != "limited_estimate"
                       else "none: there was too little history to backtest, so no accuracy figure exists for this estimate"),
        forecast_basis=res.basis,
        data_profile=res.profile,
        validation=res.validation,
        registered_model_note=res.registered_model_note,
        **provenance,
    )
