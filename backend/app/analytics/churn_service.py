"""Churn prediction inference for a single business.

See docs/DATA_SPECIFICATION.md §4: "Churn requires repeat customer
observations" — disabled with an explicit insufficient-evidence error
rather than guessing when a business doesn't have enough customer history.
"""
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy.orm import Session

from app.core.errors import InsufficientDataError
from app.models.customer import Customer
from app.models.ml_model import MLModel
from app.services.model_registry_service import select_best_model

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHURN_MODEL_CANDIDATES = ["churn_logistic_regression", "churn_random_forest", "churn_xgboost"]
MIN_CUSTOMERS_WITH_HISTORY = 30


@dataclass
class ChurnPrediction:
    customer_id: str
    external_customer_id: str | None
    churn_probability: float


def _load_model(model_row: MLModel):
    return joblib.load(PROJECT_ROOT / model_row.model_path)


def _customers_with_complete_history(db: Session, business_id: str) -> list[Customer]:
    customers = db.query(Customer).filter(Customer.business_id == business_id).all()
    return [
        c
        for c in customers
        if c.first_purchase_date is not None
        and c.last_purchase_date is not None
        and c.purchase_frequency is not None
        and c.monetary_value is not None
        and float(c.purchase_frequency) > 0
    ]


def check_churn_sufficiency(db: Session, business_id: str) -> tuple[bool, str | None]:
    eligible = _customers_with_complete_history(db, business_id)
    if len(eligible) < MIN_CUSTOMERS_WITH_HISTORY:
        return False, (
            f"Only {len(eligible)} customers have complete purchase history "
            f"(first/last purchase date, frequency, monetary value) — at least "
            f"{MIN_CUSTOMERS_WITH_HISTORY} are needed for churn predictions."
        )
    return True, None


def predict_churn(db: Session, business_id: str) -> tuple[list[ChurnPrediction], MLModel]:
    from ml.features.churn_features import FEATURE_COLUMNS, build_churn_features

    sufficient, reason = check_churn_sufficiency(db, business_id)
    if not sufficient:
        raise InsufficientDataError(reason or "Not enough customer history for churn prediction.")

    model_row = select_best_model(db, CHURN_MODEL_CANDIDATES, metric="roc_auc", minimize=False)
    if model_row is None:
        raise InsufficientDataError(
            "No churn model is registered yet. Run `python -m ml.training.train_churn` "
            "and sync the registry before requesting churn predictions."
        )
    model = _load_model(model_row)

    eligible = _customers_with_complete_history(db, business_id)
    today = date.today()
    rows = []
    for c in eligible:
        tenure_days = max(1, (today - c.first_purchase_date).days)
        recency_days = max(0, (today - c.last_purchase_date).days)
        frequency = float(c.purchase_frequency)
        monetary_value = float(c.monetary_value)
        avg_order_value = monetary_value / frequency if frequency else 0.0
        rows.append(
            {
                "customer_id": c.id,
                "external_customer_id": c.external_customer_id,
                "tenure_days": tenure_days,
                "recency_days": recency_days,
                "frequency": frequency,
                "avg_order_value": avg_order_value,
                "monetary_value": monetary_value,
            }
        )

    df = pd.DataFrame(rows)
    featured = build_churn_features(df)
    probabilities = model.predict_proba(featured[FEATURE_COLUMNS])[:, 1]

    predictions = [
        ChurnPrediction(
            customer_id=row["customer_id"],
            external_customer_id=row["external_customer_id"],
            churn_probability=round(float(prob), 4),
        )
        for row, prob in zip(rows, probabilities)
    ]
    return predictions, model_row
