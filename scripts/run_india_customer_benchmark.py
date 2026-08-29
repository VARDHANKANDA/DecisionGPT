"""Purchase-prediction benchmark on the SIMULATED Indian customer dataset
(Kaggle `kundanbedmutha/...`, CC BY 4.0).

This is a **standalone** benchmark - it is deliberately NOT wired into the
Training Center or Model Registry, so it can never touch a production model.
The dataset is synthetic; its metrics are reported under
`SYNTHETIC_INDIAN_CONTEXT` and never combined with real-world results.

    python scripts/run_india_customer_benchmark.py [--seed 42]

Writes data/external/india_customer_synthetic/benchmark_results.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from xgboost import XGBClassifier  # noqa: E402

from ml.preprocessing.india_customer_adapter import FEATURE_COLUMNS, TARGET  # noqa: E402

PROCESSED = ROOT / "data/external/india_customer_synthetic/processed/india_customer_purchase_prediction.csv"
OUT = ROOT / "data/external/india_customer_synthetic/benchmark_results.json"


def _models(seed: int):
    return {
        "logistic_regression": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=1000, random_state=seed)
        ),
        "random_forest": RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=-1),
        "xgboost": XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05, random_state=seed,
            objective="binary:logistic", eval_metric="logloss",
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if not PROCESSED.exists():
        print(f"SKIP: {PROCESSED} missing - run "
              "scripts/download_india_business_datasets.py --only kundan && "
              "scripts/build_external_datasets.py --only kundan")
        sys.exit(0)

    df = pd.read_csv(PROCESSED)
    X, y = df[FEATURE_COLUMNS], df[TARGET].astype(int)
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.25, random_state=args.seed, stratify=y
    )

    rows = []
    for name, model in _models(args.seed).items():
        model.fit(X_tr, y_tr)
        pred = model.predict(X_te)
        proba = model.predict_proba(X_te)[:, 1]
        rows.append({
            "model": name,
            "precision": round(float(precision_score(y_te, pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_te, pred, zero_division=0)), 4),
            "f1": round(float(f1_score(y_te, pred, zero_division=0)), 4),
            "roc_auc": round(float(roc_auc_score(y_te, proba)), 4),
        })
        print(f"  {name:20} P={rows[-1]['precision']} R={rows[-1]['recall']} "
              f"F1={rows[-1]['f1']} AUC={rows[-1]['roc_auc']}")

    result = {
        "dataset": "external-india-customer-synthetic-v1",
        "data_category": "SYNTHETIC_INDIAN_CONTEXT",
        "task": "purchase_prediction",
        "target": TARGET,
        "seed": args.seed,
        "n_rows": int(len(df)),
        "class_balance": {str(k): int(v) for k, v in y.value_counts().items()},
        "train_rows": int(len(X_tr)),
        "test_rows": int(len(X_te)),
        "features": FEATURE_COLUMNS,
        "excluded_as_leakage": ["revenue", "revenue_normalized", "cart_abandoned",
                                "rating", "review_text", "review_helpful_votes"],
        "results": rows,
        "note": "SIMULATED dataset. Standalone benchmark - not registered as an "
                "MLModel, not wired into the Training Center. Never combined with "
                "real-world Indian results.",
    }
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
