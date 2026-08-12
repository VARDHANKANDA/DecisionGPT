import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from app.analytics import explainability_service
from app.analytics.explainability_service import ExplanationUnavailableError
from app.models.ml_model import MLModel
from ml.evaluation.explainability import tree_shap_global_importance


def _fit_model_with_one_real_driver():
    """y depends strongly on 'driver' and not at all on 'noise' — a model
    trained on this should let SHAP recover exactly that."""
    rng = np.random.default_rng(7)
    n = 300
    driver = rng.uniform(0, 100, n)
    noise = rng.uniform(0, 100, n)
    y = driver * 3 + rng.normal(0, 1, n)

    X = pd.DataFrame({"driver": driver, "noise": noise})
    model = XGBRegressor(n_estimators=50, max_depth=3, random_state=0)
    model.fit(X, y)
    return model, X


def test_tree_shap_global_importance_ranks_the_real_driver_highest():
    model, X = _fit_model_with_one_real_driver()
    importance = tree_shap_global_importance(model, X)

    assert importance["driver"] > importance["noise"] * 5


def test_explain_prediction_delta_isolates_the_changed_feature():
    """Only 'driver' is changed between the two rows; 'noise' keeps its
    exact value in both. Tree SHAP's Shapley values are computed jointly
    over all of a row's features, so 'noise' can still pick up a small
    interaction-effect delta even though its own value didn't move — that's
    real SHAP behavior, not a bug — but 'driver' (the feature that actually
    changed, and the only one the target genuinely depends on) must
    dominate the explanation, both in rank and in magnitude.
    """
    model, X = _fit_model_with_one_real_driver()

    baseline_row = X.iloc[[0]].copy()
    scenario_row = baseline_row.copy()
    scenario_row["driver"] = scenario_row["driver"] + 50  # only 'driver' changes

    contributions = explainability_service.explain_prediction_delta(
        model, "forecasting_xgboost", baseline_row, scenario_row
    )

    by_feature = {c.feature: c for c in contributions}
    assert by_feature["driver"].contribution > 0
    assert by_feature["driver"].direction == "increased"
    assert contributions[0].feature == "driver"  # ranked first by |contribution|
    assert abs(by_feature["driver"].contribution) > abs(by_feature["noise"].contribution) * 5


def test_explain_prediction_delta_refuses_non_tree_model_types():
    model, X = _fit_model_with_one_real_driver()
    row = X.iloc[[0]]

    try:
        explainability_service.explain_prediction_delta(model, "forecasting_naive", row, row)
        assert False, "expected ExplanationUnavailableError"
    except ExplanationUnavailableError as exc:
        assert "forecasting_naive" in exc.message


def test_global_importance_from_registry_reads_stored_values_only():
    model_row = MLModel(
        model_name="sales_forecast_xgboost",
        model_type="forecasting_xgboost",
        version="v1",
        dataset_version="d1",
        feature_version="f1",
        model_path="unused",
        metrics_json={"mae": 1.0, "shap_global_importance": {"price": 0.5, "marketing_spend": 2.0}},
    )
    ranked = explainability_service.global_importance_from_registry(model_row)

    assert [c.feature for c in ranked] == ["marketing_spend", "price"]  # sorted descending


def test_global_importance_from_registry_empty_when_not_precomputed():
    model_row = MLModel(
        model_name="sales_forecast_linear",
        model_type="forecasting_linear",
        version="v1",
        dataset_version="d1",
        feature_version="f1",
        model_path="unused",
        metrics_json={"mae": 1.0},
    )
    assert explainability_service.global_importance_from_registry(model_row) == []


def test_build_explanation_degrades_gracefully_for_non_tree_models():
    model_row = MLModel(
        model_name="sales_forecast_naive",
        model_type="forecasting_naive",
        version="v1",
        dataset_version="d1",
        feature_version="f1",
        model_path="unused",
        metrics_json={"mae": 1.0},
    )
    explanation = explainability_service.build_explanation(model_row, model=None, baseline_row=None, scenario_row=None)

    assert explanation.shap_available is False
    assert explanation.unavailable_reason is not None
    assert explanation.local_factors == []
