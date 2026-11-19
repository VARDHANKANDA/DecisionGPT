import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from sklearn.neural_network import MLPClassifier
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.evaluation.metrics import classification_metrics

df = pd.read_csv('data/external/india_telecom_churn/raw/indian_telecom_customers.csv')
num_cols = ['age', 'annual_income_lakhs', 'monthly_charges', 'tenure_months', 'data_usage_gb', 
            'voice_minutes', 'sms_count', 'payment_delays_last_6m', 'support_calls_last_month', 
            'network_satisfaction', 'price_satisfaction', 'overall_satisfaction', 
            'price_sensitivity_score', 'competitor_offers_received']
cat_cols = ['operator', 'plan_type', 'city_tier', 'payment_method']
X = pd.get_dummies(df[num_cols + cat_cols], drop_first=True)
y = (df['churn'] == 'Yes').astype(int)

X_tr_val, X_te, y_tr_val, y_te = train_test_split(X, y, test_size=0.15, stratify=y, random_state=42)
X_tr, X_val, y_tr, y_val = train_test_split(X_tr_val, y_tr_val, test_size=0.17647, stratify=y_tr_val, random_state=42)

models = {
    'Logistic Regression': make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=42)),
    'Random Forest': RandomForestClassifier(n_estimators=200, max_depth=10, min_samples_leaf=2, random_state=42, n_jobs=-1),
    'XGBoost': XGBClassifier(n_estimators=150, max_depth=5, learning_rate=0.08, subsample=0.8, eval_metric='logloss', random_state=42, n_jobs=-1),
    'LightGBM': LGBMClassifier(n_estimators=150, num_leaves=31, learning_rate=0.08, subsample=0.8, random_state=42, n_jobs=-1, verbose=-1),
    'MLP Neural Net': make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=200, random_state=42))
}

for name, model in models.items():
    model.fit(X_tr, y_tr)
    preds = model.predict(X_te)
    probs = model.predict_proba(X_te)[:, 1]
    m = classification_metrics(y_te.to_numpy(), preds, probs)
    print(f"{name:22s} | Acc: {m['accuracy']*100:.2f}% | Prec: {m['precision']*100:.2f}% | Rec: {m['recall']*100:.2f}% | F1: {m['f1']*100:.2f}% | AUC: {m['roc_auc']:.4f} | Brier: {m['brier']:.4f}")

