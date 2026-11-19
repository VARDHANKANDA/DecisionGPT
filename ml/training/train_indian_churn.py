"""Train and evaluate Indian Customer Churn & Retention Models.

Dataset: Indian Telecom Customer Churn & Retention (15,000 customers with deep behavioural data)
Models:
  1. Logistic Regression Classifier (StandardScaler, L2 regularized)
  2. Random Forest Classifier (200 trees, max_depth=10, min_samples_leaf=2)
  3. XGBoost Classifier (150 trees, max_depth=5, lr=0.08)
  4. LightGBM Classifier (150 trees, num_leaves=31, lr=0.08)
  5. Multi-Layer Perceptron (MLP) Classifier (Deep Neural Network)

Protocol:
  - 70% Train, 15% Validation, 15% Held-out Test
  - Stratified split with fixed seed 42 (zero data leakage)
  - Full evaluation: Test Accuracy, Val Accuracy, Precision, Recall, F1, ROC-AUC, PR-AUC,
    Confusion Matrix, Brier Score, Log Loss, and execution runtimes.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier

from ml.evaluation.metrics import classification_metrics

MODELS_DIR = ROOT / "models"
DATA_FILE = ROOT / "data" / "external" / "india_telecom_churn" / "raw" / "indian_telecom_customers.csv"
RANDOM_SEED = 42


def train_and_evaluate_all() -> dict[str, dict]:
    print("=" * 80)
    print("TRAINING INDIAN TELECOM CHURN & RETENTION MODELS")
    print("=" * 80)
    
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Dataset not found at {DATA_FILE}")

    df = pd.read_csv(DATA_FILE)
    print(f"Loaded {len(df):,} customer records.")

    num_cols = [
        "age", "annual_income_lakhs", "monthly_charges", "tenure_months", "data_usage_gb", 
        "voice_minutes", "sms_count", "payment_delays_last_6m", "support_calls_last_month", 
        "network_satisfaction", "price_satisfaction", "overall_satisfaction", 
        "price_sensitivity_score", "competitor_offers_received"
    ]
    cat_cols = ["operator", "plan_type", "city_tier", "payment_method"]
    X = pd.get_dummies(df[num_cols + cat_cols], drop_first=True)
    y = (df["churn"] == "Yes").astype(int)

    # 70% Train, 15% Validation, 15% Test
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X, y, test_size=0.15, stratify=y, random_state=RANDOM_SEED
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val, y_train_val, test_size=0.17647, stratify=y_train_val, random_state=RANDOM_SEED
    )

    print(f"Splits -> Train: {len(X_train):,} ({len(X_train)/len(df):.1%}), "
          f"Validation: {len(X_val):,} ({len(X_val)/len(df):.1%}), "
          f"Test: {len(X_test):,} ({len(X_test)/len(df):.1%})")
    print(f"Target prevalence: {y.mean():.3f} (Class 0: {(y==0).sum():,}, Class 1: {(y==1).sum():,})")

    model_configs = {
        "logistic_regression": {
            "name": "Logistic Regression Classifier",
            "builder": lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=RANDOM_SEED)),
            "params": {"max_iter": 1000, "solver": "lbfgs", "scaling": "StandardScaler"},
        },
        "random_forest": {
            "name": "Random Forest Classifier",
            "builder": lambda: RandomForestClassifier(n_estimators=200, max_depth=10, min_samples_leaf=2, random_state=RANDOM_SEED, n_jobs=-1),
            "params": {"n_estimators": 200, "max_depth": 10, "min_samples_leaf": 2},
        },
        "xgboost": {
            "name": "XGBoost Classifier",
            "builder": lambda: XGBClassifier(n_estimators=150, max_depth=5, learning_rate=0.08, subsample=0.8, eval_metric="logloss", random_state=RANDOM_SEED, n_jobs=-1),
            "params": {"n_estimators": 150, "max_depth": 5, "learning_rate": 0.08, "subsample": 0.8},
        },
        "lightgbm": {
            "name": "LightGBM Classifier",
            "builder": lambda: LGBMClassifier(n_estimators=150, num_leaves=31, learning_rate=0.08, subsample=0.8, random_state=RANDOM_SEED, n_jobs=-1, verbose=-1),
            "params": {"n_estimators": 150, "num_leaves": 31, "learning_rate": 0.08},
        },
        "mlp_neural_network": {
            "name": "Multi-Layer Perceptron (Deep Neural Network)",
            "builder": lambda: make_pipeline(
                StandardScaler(),
                MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=300, random_state=RANDOM_SEED)
            ),
            "params": {"hidden_layers": [64, 32], "activation": "relu", "solver": "adam"},
        },
    }

    results = {}

    for model_key, cfg in model_configs.items():
        print(f"\n--- Training {cfg['name']} ---")
        clf = cfg["builder"]()
        
        # Fit timing
        t0 = time.perf_counter()
        clf.fit(X_train, y_train)
        train_duration = time.perf_counter() - t0

        # Validation evaluation
        val_preds = clf.predict(X_val)
        val_proba = clf.predict_proba(X_val)[:, 1] if hasattr(clf, "predict_proba") else None
        val_metrics = classification_metrics(y_val.to_numpy(), val_preds, val_proba)

        # Test evaluation (held-out)
        t_inf0 = time.perf_counter()
        test_preds = clf.predict(X_test)
        inference_duration = time.perf_counter() - t_inf0
        test_proba = clf.predict_proba(X_test)[:, 1] if hasattr(clf, "predict_proba") else None
        test_metrics = classification_metrics(y_test.to_numpy(), test_preds, test_proba)

        # Structure complete metric dictionary
        combined_metrics = {
            "accuracy": round(float(test_metrics["accuracy"]), 4),
            "val_accuracy": round(float(val_metrics["accuracy"]), 4),
            "balanced_accuracy": round(float(test_metrics["balanced_accuracy"]), 4),
            "precision": round(float(test_metrics["precision"]), 4),
            "recall": round(float(test_metrics["recall"]), 4),
            "f1": round(float(test_metrics["f1"]), 4),
            "roc_auc": round(float(test_metrics.get("roc_auc", 0.5)), 4),
            "pr_auc": round(float(test_metrics.get("pr_auc", 0.0)), 4),
            "brier": round(float(test_metrics.get("brier", 0.0)), 4),
            "log_loss": round(float(test_metrics["log_loss"]), 4) if test_metrics.get("log_loss") is not None else None,
            "confusion_tp": int(test_metrics.get("confusion_tp", 0)),
            "confusion_fp": int(test_metrics.get("confusion_fp", 0)),
            "confusion_fn": int(test_metrics.get("confusion_fn", 0)),
            "confusion_tn": int(test_metrics.get("confusion_tn", 0)),
            "training_time_sec": round(train_duration, 4),
            "inference_time_sec": round(inference_duration, 4),
            "n_train": len(X_train),
            "n_val": len(X_val),
            "n_test": len(X_test),
        }

        print(f"  Test Accuracy:     {combined_metrics['accuracy']:.2%}")
        print(f"  Val Accuracy:      {combined_metrics['val_accuracy']:.2%}")
        print(f"  Precision:         {combined_metrics['precision']:.2%}")
        print(f"  Recall:            {combined_metrics['recall']:.2%}")
        print(f"  F1 Score:          {combined_metrics['f1']:.2%}")
        print(f"  ROC-AUC:           {combined_metrics['roc_auc']:.4f}")
        print(f"  Training Duration: {train_duration:.2f}s")

        # Save artifact
        model_name = f"indian_telecom_churn_{model_key}"
        version_dir = MODELS_DIR / model_name / "v1"
        version_dir.mkdir(parents=True, exist_ok=True)
        artifact_file = version_dir / "model.joblib"
        joblib.dump(clf, artifact_file)

        manifest = {
            "model_name": model_name,
            "display_name": cfg["name"],
            "version": "v1",
            "model_type": f"churn_{model_key}",
            "task": "classification",
            "dataset_version": "external-india-telecom-churn-v1",
            "dataset_name": "Indian Telecom Customer Churn & Retention",
            "geography": "India (28 states)",
            "n_samples": len(df),
            "parameters": cfg["params"],
            "feature_columns": list(X.columns),
            "metrics": combined_metrics,
            "artifact_path": str(artifact_file.relative_to(ROOT)),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        manifest_file = version_dir / "manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(manifest, f, indent=2)

        results[model_name] = manifest

    print("\n" + "=" * 80)
    print("ALL 5 INDIAN TELECOM CHURN MODELS TRAINED AND SAVED SUCCESSFULLY")
    print("=" * 80)
    return results


if __name__ == "__main__":
    train_and_evaluate_all()
