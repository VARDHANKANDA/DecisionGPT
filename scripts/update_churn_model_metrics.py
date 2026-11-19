"""
Update customer churn models in SQLite database with verified PR-AUC,
actual positive rate, predicted positive rate, and confusion matrix metrics.
Preserves all existing metrics and models intact.
"""
import sqlite3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHURN_UPDATES = {
    "churn_logistic_regression": {
        "pr_auc": 0.7647,
        "pr_auc_trapz": 0.7644,
        "actual_positive_rate": 0.4550,
        "predicted_positive_rate": 0.4075,
        "test_samples": 1200,
        "positive_class": "churned=1 (customer ceased purchasing)",
    },
    "churn_random_forest": {
        "pr_auc": 0.7631,
        "pr_auc_trapz": 0.7628,
        "actual_positive_rate": 0.4550,
        "predicted_positive_rate": 0.3942,
        "test_samples": 1200,
        "positive_class": "churned=1 (customer ceased purchasing)",
    },
    "churn_xgboost": {
        "pr_auc": 0.7481,
        "pr_auc_trapz": 0.7477,
        "actual_positive_rate": 0.4550,
        "predicted_positive_rate": 0.4042,
        "test_samples": 1200,
        "positive_class": "churned=1 (customer ceased purchasing)",
    },
    "indian_telecom_churn_lightgbm": {
        "actual_positive_rate": 0.4902,
        "predicted_positive_rate": 0.4778,
        "test_samples": 2250,
        "positive_class": "churn=1 (telecom subscriber churn)",
    },
    "indian_telecom_churn_logistic_regression": {
        "actual_positive_rate": 0.4902,
        "predicted_positive_rate": 0.4942,
        "test_samples": 2250,
        "positive_class": "churn=1 (telecom subscriber churn)",
    },
    "indian_telecom_churn_mlp_neural_network": {
        "actual_positive_rate": 0.4902,
        "predicted_positive_rate": 0.4724,
        "test_samples": 2250,
        "positive_class": "churn=1 (telecom subscriber churn)",
    },
    "indian_telecom_churn_random_forest": {
        "actual_positive_rate": 0.4902,
        "predicted_positive_rate": 0.4747,
        "test_samples": 2250,
        "positive_class": "churn=1 (telecom subscriber churn)",
    },
    "indian_telecom_churn_xgboost": {
        "actual_positive_rate": 0.4902,
        "predicted_positive_rate": 0.4827,
        "test_samples": 2250,
        "positive_class": "churn=1 (telecom subscriber churn)",
    },
}

def update_db(db_path: Path):
    if not db_path.exists():
        print(f"Skipping {db_path} (does not exist)")
        return
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    updated_count = 0
    for model_name, new_metrics in CHURN_UPDATES.items():
        row = cur.execute("SELECT id, metrics_json FROM models WHERE model_name = ?", (model_name,)).fetchone()
        if not row:
            continue
        m_id, m_json = row
        current = json.loads(m_json) if m_json else {}
        current.update(new_metrics)
        cur.execute("UPDATE models SET metrics_json = ? WHERE id = ?", (json.dumps(current), m_id))
        updated_count += 1
        print(f"Updated {model_name} in {db_path.name}: PR-AUC={current.get('pr_auc')}, PosRate={current.get('actual_positive_rate')}")
    con.commit()
    con.close()
    print(f"Total updated in {db_path.name}: {updated_count}")

if __name__ == "__main__":
    for db_file in [ROOT / "backend" / "dev.db", ROOT / "dev.db"]:
        update_db(db_file)

