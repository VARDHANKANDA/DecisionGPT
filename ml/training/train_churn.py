"""Train and evaluate churn models on the platform dataset.

Compares Logistic Regression, Random Forest, and XGBoost per
docs/AI_MODULE_SPECIFICATION.md §4 and docs/EXPERIMENT_PLAN.md Experiment B.

Usage:
    python -m ml.training.train_churn
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from ml.evaluation.metrics import classification_metrics
from ml.features.churn_features import FEATURE_COLUMNS, TARGET_COLUMN, build_churn_features
from ml.pipeline.loaders import load_platform_dataset
from ml.pipeline.registry import save_model_artifact

RANDOM_SEED = 42
RESULTS_DIR = Path(__file__).resolve().parents[2] / "experiments" / "results"


def run(random_seed: int = RANDOM_SEED) -> dict:
    dataset = load_platform_dataset("churn", "customers.csv")
    dataset_version = dataset.metadata["dataset_id"]

    featured = build_churn_features(dataset.dataframe)
    X = featured[FEATURE_COLUMNS]
    y = featured[TARGET_COLUMN]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=random_seed
    )

    models = {
        "logistic_regression": (
            make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=random_seed)),
            {"max_iter": 1000, "scaled": True},
        ),
        "random_forest": (
            RandomForestClassifier(n_estimators=200, max_depth=8, random_state=random_seed),
            {"n_estimators": 200, "max_depth": 8},
        ),
        "xgboost": (
            XGBClassifier(
                n_estimators=200,
                max_depth=4,
                learning_rate=0.05,
                random_state=random_seed,
                eval_metric="logloss",
            ),
            {"n_estimators": 200, "max_depth": 4, "learning_rate": 0.05},
        ),
    }

    results = {}
    for model_type, (model, params) in models.items():
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        proba = model.predict_proba(X_test)[:, 1]
        metrics = classification_metrics(y_test.to_numpy(), preds, proba)

        manifest = save_model_artifact(
            model=model,
            model_name=f"churn_{model_type}",
            model_type=f"churn_{model_type}",
            version="v1",
            dataset_version=dataset_version,
            feature_version="churn_v1",
            parameters=params,
            metrics=metrics,
            random_seed=random_seed,
        )
        results[model_type] = {"metrics": metrics, "manifest": manifest.artifact_path}
        print(
            f"[churn/{model_type}] Precision={metrics['precision']:.3f} "
            f"Recall={metrics['recall']:.3f} F1={metrics['f1']:.3f} ROC-AUC={metrics['roc_auc']:.3f}"
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_record = {
        "experiment_type": "churn",
        "dataset_version": dataset_version,
        "random_seed": random_seed,
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "results": {k: v["metrics"] for k, v in results.items()},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    out_path = RESULTS_DIR / f"churn_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
    out_path.write_text(json.dumps(result_record, indent=2))
    print(f"Saved experiment result to {out_path}")
    return result_record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args()
    run(random_seed=args.seed)
