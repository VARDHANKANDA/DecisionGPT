"""Churn prediction inference for a single business.

See docs/DATA_SPECIFICATION.md §4: "Churn requires repeat customer
observations" — disabled with an explicit insufficient-evidence error
rather than guessing when a business doesn't have enough customer history.
"""
from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy.orm import Session

from app.core import clock
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


def describe_scores(model_row: MLModel) -> dict:
    """What the churn number means for this model: the label it was trained on and the limits of reading it as a probability."""
    meta = (model_row.lifecycle_json or {}).get("run_metadata") or {}
    ds = str(model_row.dataset_version or "")
    if "label_provenance" in meta:
        provenance = str(meta["label_provenance"])
    elif ds.startswith("platform-churn"):
        provenance = "synthetic: the label was drawn from a known generator (scripts/generate_platform_data.py), not observed customers"
    else:
        provenance = "unknown: the training run did not record where its churn label came from"
    warnings = []
    if provenance.startswith("synthetic"):
        warnings.append("This model was trained on synthetic customers. Its recorded metrics describe that data, not your customers.")
    if provenance.startswith("unknown"):
        warnings.append("The origin of this model's churn label was not recorded, so the score cannot be interpreted as observed churn.")
    warnings.append("The score ranks customers by similarity to the training customers' pattern. It has not been calibrated against "
                    "outcomes recorded for your business, so do not read it as the exact chance that a customer will leave.")
    return {"label_provenance": provenance, "warnings": warnings,
            "score_meaning": "A model score between 0 and 1 for how much a customer's recency, frequency and spend resemble customers "
                             "labelled as churned in the training data. Not a verified churn probability."}


STALE_CUSTOMER_DAYS = 45   # provisional engineering policy; see docs/REAL_WORLD_VALIDATION_PLAN.md section 4


def data_age_warning(db: Session, business_id: str) -> str | None:
    """Recency is measured against today, so customer records that stopped being updated make every customer look lapsed. Say so."""
    last = [c.last_purchase_date for c in _customers_with_complete_history(db, business_id)]
    if not last:
        return None
    age = (clock.today() - max(last)).days
    if age <= STALE_CUSTOMER_DAYS:
        return None
    return (f"The most recent purchase on record for any customer is {age} days old. Recency is measured against today, so most customers "
            "will score as lapsed because the records have not been updated, not necessarily because they stopped buying.")


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
    from ml.features.contracts import CHURN_V1, FeatureContractError

    sufficient, reason = check_churn_sufficiency(db, business_id)
    if not sufficient:
        raise InsufficientDataError(reason or "Not enough customer history for churn prediction.")

    model_row = select_best_model(db, CHURN_MODEL_CANDIDATES, metric="roc_auc", minimize=False, validation_metric="val_roc_auc")
    if model_row is None:
        raise InsufficientDataError(
            "No churn model is registered yet. Run `python -m ml.training.train_churn` "
            "and sync the registry before requesting churn predictions."
        )
    model = _load_model(model_row)

    eligible = _customers_with_complete_history(db, business_id)
    today = clock.today()
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
    try:  # fail safely: never score customers on a frame that does not match what the model was trained on
        frame = CHURN_V1.validate(featured[FEATURE_COLUMNS])
    except (FeatureContractError, KeyError) as exc:
        raise InsufficientDataError(f"Customer data cannot be scored: {exc}") from exc
    probabilities = model.predict_proba(frame)[:, 1]

    predictions = [
        ChurnPrediction(
            customer_id=row["customer_id"],
            external_customer_id=row["external_customer_id"],
            churn_probability=round(float(prob), 4),
        )
        for row, prob in zip(rows, probabilities)
    ]
    return predictions, model_row
