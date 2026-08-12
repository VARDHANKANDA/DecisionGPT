"""Explainability — docs/AI_MODULE_SPECIFICATION.md §7.

Two kinds of explanation, both grounded in a real prediction rather than a
narrated guess (AGENTS.md "no fabrication"):

- Local: for one decision, the SHAP contribution *delta* between the
  Digital Twin's baseline and scenario day-1 feature rows — mechanically
  decomposes exactly what the model's prediction difference is attributable
  to. Computed here, at request time, using shap.TreeExplainer directly on
  the loaded model artifact — this never touches platform training data
  (see ml/pipeline/loaders.py "Data isolation"), only the model artifact and
  this business's own feature rows.
- Global: "which factors matter most in general" — precomputed once
  *offline* during training (ml/evaluation/explainability.py, run from
  ml/training/train_forecasting.py against real platform test data) and
  stored in the model's metrics_json. This module only ever reads that
  stored value; it never re-touches platform data itself.

Only SHAP-compatible model types (docs/AI_MODULE_SPECIFICATION.md §7
"compatible ML models") get an explanation — currently tree ensembles via
shap.TreeExplainer. The naive/linear forecasting models are refused with an
explicit "not available", never a fake explanation.
"""
from dataclasses import dataclass, field

import pandas as pd
import shap

from app.core.errors import AppError
from app.models.ml_model import MLModel

TREE_MODEL_TYPES = {"forecasting_xgboost", "forecasting_random_forest", "churn_xgboost", "churn_random_forest"}

FEATURE_LABELS = {
    "lag_1": "Yesterday's sales",
    "lag_7": "Sales from a week ago",
    "rolling_mean_7": "Recent 7-day average sales",
    "rolling_mean_28": "Recent 4-week average sales",
    "day_of_week": "Day-of-week pattern",
    "is_weekend": "Weekend timing",
    "month": "Seasonality (month)",
    "price": "Price",
    "marketing_spend": "Marketing spend",
    "promotion_flag": "Active promotion",
}

TOP_N_LOCAL_FACTORS = 5


class ExplanationUnavailableError(AppError):
    code = "EXPLANATION_UNAVAILABLE"
    http_status = 422


@dataclass
class FeatureContribution:
    feature: str
    label: str
    contribution: float
    direction: str


@dataclass
class Explanation:
    model_name: str
    model_version: str
    shap_available: bool
    unavailable_reason: str | None = None
    local_factors: list[FeatureContribution] = field(default_factory=list)
    global_importance: list[FeatureContribution] = field(default_factory=list)


def _label(feature: str) -> str:
    return FEATURE_LABELS.get(feature, feature.replace("_", " ").capitalize())


def explain_prediction_delta(
    model, model_type: str, baseline_row: pd.DataFrame, scenario_row: pd.DataFrame
) -> list[FeatureContribution]:
    """Ranked list of which features drove the difference between two
    predictions on the *same* model — the "what influenced this
    recommendation" answer (docs/PRD.md §28)."""
    if model_type not in TREE_MODEL_TYPES:
        raise ExplanationUnavailableError(f"SHAP explanations aren't available for '{model_type}' models yet.")

    explainer = shap.TreeExplainer(model)
    baseline_shap = explainer.shap_values(baseline_row)[0]
    scenario_shap = explainer.shap_values(scenario_row)[0]

    contributions = []
    for i, col in enumerate(baseline_row.columns):
        delta = float(scenario_shap[i] - baseline_shap[i])
        contributions.append(
            FeatureContribution(
                feature=col,
                label=_label(col),
                contribution=round(delta, 4),
                direction="increased" if delta > 1e-9 else ("decreased" if delta < -1e-9 else "unchanged"),
            )
        )
    contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
    return contributions[:TOP_N_LOCAL_FACTORS]


def global_importance_from_registry(model_row: MLModel) -> list[FeatureContribution]:
    raw = model_row.metrics_json.get("shap_global_importance")
    if not raw:
        return []
    ranked = sorted(raw.items(), key=lambda item: item[1], reverse=True)
    return [
        FeatureContribution(feature=feature, label=_label(feature), contribution=round(value, 4), direction="")
        for feature, value in ranked
    ]


def build_explanation(
    model_row: MLModel, model, baseline_row: pd.DataFrame | None, scenario_row: pd.DataFrame | None
) -> Explanation:
    global_importance = global_importance_from_registry(model_row)

    if model_row.model_type not in TREE_MODEL_TYPES:
        return Explanation(
            model_name=model_row.model_name,
            model_version=model_row.version,
            shap_available=False,
            unavailable_reason=f"SHAP explanations aren't available for '{model_row.model_type}' models yet.",
            global_importance=global_importance,
        )

    local_factors = []
    if baseline_row is not None and scenario_row is not None:
        local_factors = explain_prediction_delta(model, model_row.model_type, baseline_row, scenario_row)

    return Explanation(
        model_name=model_row.model_name,
        model_version=model_row.version,
        shap_available=True,
        local_factors=local_factors,
        global_importance=global_importance,
    )
