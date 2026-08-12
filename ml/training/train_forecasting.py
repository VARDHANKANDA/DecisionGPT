"""Train and evaluate forecasting models on the platform dataset.

Compares naive, linear, and XGBoost per docs/AI_MODULE_SPECIFICATION.md §3
and docs/EXPERIMENT_PLAN.md Experiment A. All three are registered (not
just the winner) so the Research Console can render the real comparison
table — no metric on that page is ever hand-typed.

Usage:
    python -m ml.training.train_forecasting
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor

from ml.evaluation.explainability import tree_shap_global_importance
from ml.evaluation.metrics import regression_metrics
from ml.features.forecasting_features import FEATURE_COLUMNS, TARGET_COLUMN, build_forecasting_features
from ml.pipeline.loaders import load_platform_dataset
from ml.pipeline.preprocessing import chronological_split, clean_dataframe
from ml.pipeline.registry import save_model_artifact
from ml.training.baselines import NaiveLagForecaster

RANDOM_SEED = 42
RESULTS_DIR = Path(__file__).resolve().parents[2] / "experiments" / "results"


def run(random_seed: int = RANDOM_SEED) -> dict:
    dataset = load_platform_dataset("forecasting", "sales_timeseries.csv")
    dataset_version = dataset.metadata["dataset_id"]

    cleaned = clean_dataframe(dataset.dataframe, date_columns=["date"])
    featured = build_forecasting_features(cleaned)
    train, val, test = chronological_split(featured, "date")

    X_train, y_train = train[FEATURE_COLUMNS], train[TARGET_COLUMN]
    X_test, y_test = test[FEATURE_COLUMNS], test[TARGET_COLUMN]

    models = {
        "naive": (NaiveLagForecaster(), {}),
        "linear": (LinearRegression(), {}),
        "xgboost": (
            XGBRegressor(
                n_estimators=200,
                max_depth=4,
                learning_rate=0.05,
                random_state=random_seed,
                objective="reg:squarederror",
            ),
            {"n_estimators": 200, "max_depth": 4, "learning_rate": 0.05},
        ),
    }

    results = {}
    for model_type, (model, params) in models.items():
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        metrics = regression_metrics(y_test.to_numpy(), preds)

        if model_type == "xgboost":
            sample = X_test.sample(min(200, len(X_test)), random_state=random_seed)
            metrics["shap_global_importance"] = tree_shap_global_importance(model, sample)

        manifest = save_model_artifact(
            model=model,
            model_name=f"sales_forecast_{model_type}",
            model_type=f"forecasting_{model_type}",
            version="v1",
            dataset_version=dataset_version,
            feature_version="forecasting_v1",
            parameters=params,
            metrics=metrics,
            random_seed=random_seed,
        )
        results[model_type] = {"metrics": metrics, "manifest": manifest.artifact_path}
        print(f"[forecasting/{model_type}] MAE={metrics['mae']:.3f} RMSE={metrics['rmse']:.3f} MAPE={metrics['mape']:.2f}%")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_record = {
        "experiment_type": "forecasting",
        "dataset_version": dataset_version,
        "random_seed": random_seed,
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "results": {k: v["metrics"] for k, v in results.items()},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    out_path = RESULTS_DIR / f"forecasting_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
    out_path.write_text(json.dumps(result_record, indent=2))
    print(f"Saved experiment result to {out_path}")
    return result_record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args()
    run(random_seed=args.seed)
