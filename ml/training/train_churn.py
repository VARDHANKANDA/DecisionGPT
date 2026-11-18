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
import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
try:
    from xgboost import XGBClassifier
except ImportError:
    XGBClassifier = None

from ml.evaluation.metrics import classification_metrics
from ml.features.churn_features import FEATURE_COLUMNS, TARGET_COLUMN, build_churn_features
from ml.pipeline.loaders import PLATFORM_DATA_ROOT, load_platform_dataset
from ml.features.contracts import CHURN_V1
from ml.pipeline.registry import next_version, save_model_artifact
from ml.pipeline.run_metadata import build_run_metadata

RANDOM_SEED = 42
RESULTS_DIR = Path(__file__).resolve().parents[2] / "experiments" / "results"

SUPPORTED_MODEL_TYPES = ("logistic_regression", "random_forest", "xgboost")
REQUIRED_COLUMNS = FEATURE_COLUMNS + [TARGET_COLUMN]


def _build_model(model_type: str, random_seed: int, params: dict | None):
    params = params or {}
    if model_type == "logistic_regression":
        cfg = {"max_iter": 1000, "scaled": True, **params}
        return (
            make_pipeline(StandardScaler(), LogisticRegression(max_iter=cfg["max_iter"], random_state=random_seed)),
            cfg,
        )
    if model_type == "random_forest":
        cfg = {"n_estimators": 200, "max_depth": 8, **params}
        return RandomForestClassifier(random_state=random_seed, **{k: cfg[k] for k in ("n_estimators", "max_depth")}), cfg
    if model_type == "xgboost":
        cfg = {"n_estimators": 200, "max_depth": 4, "learning_rate": 0.05, **params}
        return XGBClassifier(random_state=random_seed, eval_metric="logloss", **cfg), cfg
    raise ValueError(f"Unsupported churn model_type {model_type!r} (expected {SUPPORTED_MODEL_TYPES}).")


def _validation_metrics(model_type: str, random_seed: int, params: dict | None, X_train, y_train, folds: int = 5) -> dict:
    """Out-of-sample validation score computed INSIDE the training portion (stratified K-fold), so the 80/20 train/test sizes the existing
    models were built with are unchanged. Registry selection uses ``val_roc_auc`` instead of the test AUC. Also records the decision
    threshold chosen on these out-of-fold predictions (F1-optimal), which ``_test_diagnostics`` then applies once to the test block."""
    from sklearn.model_selection import StratifiedKFold, cross_val_predict

    model, _ = _build_model(model_type, random_seed, params)
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=random_seed)
    proba = cross_val_predict(model, X_train, y_train, cv=skf, method="predict_proba")[:, 1]
    y = np.asarray(y_train)
    grid = np.unique(np.round(np.quantile(proba, np.linspace(0.02, 0.98, 97)), 6))
    best_t, best_f1 = 0.5, -1.0
    for t in grid:
        pred = proba >= t
        tp, fp, fn = int(np.sum(pred & (y == 1))), int(np.sum(pred & (y == 0))), int(np.sum(~pred & (y == 1)))
        f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
        if f1 > best_f1:
            best_t, best_f1 = float(t), f1
    return {"val_roc_auc": float(roc_auc_score(y, proba)), "val_pr_auc": float(average_precision_score(y, proba)),
            "val_threshold": best_t, "val_f1_at_threshold": float(best_f1), "val_prevalence": float(y.mean())}


def _test_diagnostics(model, X_test, y_test, threshold: float, train_prevalence: float) -> dict:
    """Test-block diagnostics at the validation-chosen threshold (never tuned on the test block): PR-AUC, confusion matrix, Brier score,
    expected calibration error and the prevalence shift between training and test (calibration is only meaningful when it is small)."""
    y = np.asarray(y_test)
    p = model.predict_proba(X_test)[:, 1]
    pred = p >= threshold
    tp, fp = int(np.sum(pred & (y == 1))), int(np.sum(pred & (y == 0)))
    fn, tn = int(np.sum(~pred & (y == 1))), int(np.sum(~pred & (y == 0)))
    edges = np.linspace(0, 1, 11)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, 9)
    ece = float(sum((idx == b).mean() * abs(y[idx == b].mean() - p[idx == b].mean()) for b in range(10) if (idx == b).any()))
    return {
        "pr_auc": float(average_precision_score(y, p)), "brier": float(brier_score_loss(y, p)), "ece": ece,
        "threshold_from_validation": float(threshold), "confusion_tp": tp, "confusion_fp": fp, "confusion_fn": fn, "confusion_tn": tn,
        "precision_at_threshold": tp / (tp + fp) if tp + fp else 0.0, "recall_at_threshold": tp / (tp + fn) if tp + fn else 0.0,
        "test_prevalence": float(y.mean()), "train_prevalence": float(train_prevalence),
        "prevalence_shift": float(abs(y.mean() - train_prevalence)),
    }


def train_one(df, model_type: str, random_seed: int = RANDOM_SEED, params: dict | None = None) -> dict:
    """Train + evaluate a single churn model on an arbitrary raw dataframe
    (Research Console Training Center). Returns the fitted model + metrics;
    persistence is the caller's job."""
    base_cols = [
        "tenure_days", "recency_days", "frequency", "avg_order_value", "monetary_value", TARGET_COLUMN
    ]
    missing = [c for c in base_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Churn training needs columns {missing} that are not in the dataset.")

    featured = build_churn_features(df)
    X = featured[FEATURE_COLUMNS]
    y = featured[TARGET_COLUMN].astype(int)
    if y.nunique() < 2:
        raise ValueError("Target column 'churned' has only one class — cannot train a classifier.")
    if len(featured) < 50:
        raise ValueError(f"Only {len(featured)} rows — need at least 50 for a churn model.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=random_seed
    )
    model, resolved_params = _build_model(model_type, random_seed, params)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]
    metrics = classification_metrics(y_test.to_numpy(), preds, proba)
    metrics.update(_validation_metrics(model_type, random_seed, params, X_train, y_train))
    metrics.update(_test_diagnostics(model, X_test, y_test, metrics["val_threshold"], metrics["val_prevalence"]))

    return {
        "model": model,
        "metrics": metrics,
        "parameters": resolved_params,
        "feature_version": "churn_v1",
        "feature_columns": list(FEATURE_COLUMNS),
        "target": TARGET_COLUMN,
        "train_rows": len(X_train),
        "test_rows": len(X_test),
    }


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
        metrics.update(_validation_metrics(model_type, random_seed, None, X_train, y_train))
        metrics.update(_test_diagnostics(model, X_test, y_test, metrics["val_threshold"], metrics["val_prevalence"]))

        manifest = save_model_artifact(
            model=model,
            model_name=f"churn_{model_type}",
            model_type=f"churn_{model_type}",
            version=next_version(f"churn_{model_type}"),
            dataset_version=dataset_version,
            feature_version="churn_v1",
            parameters=params,
            metrics=metrics,
            random_seed=random_seed,
            run_metadata=build_run_metadata(
                task="churn", dataset_version=dataset_version, dataset_path=PLATFORM_DATA_ROOT / "churn" / "customers.csv", seed=random_seed,
                parameters=params, feature_columns=FEATURE_COLUMNS,
                splits={"scheme": "stratified random 80/20 (no time dimension); validation = 5-fold CV inside the train portion",
                        "train_rows": int(len(X_train)), "test_rows": int(len(X_test))},
                selection="registry selects on val_roc_auc when every candidate has it, else test roc_auc",
                extra={"label_provenance": "synthetic: drawn from a known logistic mechanism (scripts/generate_platform_data.py)",
                       "applicability": {
                           "source": "recorded", "provenance": "synthetic_platform", "target": "churned", "target_unit": "binary label",
                           "aggregation": "per_customer_snapshot", "population": f"{int(len(X_train) + len(X_test))} synthetic customers ({dataset_version})",
                           "business_id": None, "task": "score customers by similarity to customers labelled as churned", "horizon_max_days": None,
                           "evaluation_scope": "stratified held-out customers of the same synthetic population", "label_provenance_observed": False,
                           "feature_contract": CHURN_V1.describe()},
                       "feature_contract": CHURN_V1.describe()},
            ),
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
