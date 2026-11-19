import sqlite3
import json
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
churn_csv = ROOT / "data" / "external" / "india_telecom_churn" / "processed" / "india_telecom_churn_clean.csv"
pos_csv = ROOT / "data" / "external" / "india_pos_register" / "processed" / "india_pos_register_clean.csv"

churn_cols = [{"name": str(c), "dtype": str(pd.read_csv(churn_csv, nrows=2)[c].dtype)} for c in pd.read_csv(churn_csv, nrows=2).columns]
pos_cols = [{"name": str(c), "dtype": str(pd.read_csv(pos_csv, nrows=2)[c].dtype)} for c in pd.read_csv(pos_csv, nrows=2).columns]

for p in [ROOT / "backend" / "dev.db", ROOT / "dev.db"]:
    conn = sqlite3.connect(str(p))
    cur = conn.cursor()
    cur.execute(
        "UPDATE research_dataset_versions SET schema_json = ?, column_count = ? WHERE dataset_id IN (SELECT id FROM research_datasets WHERE dataset_id = 'external-india-telecom-churn-v1')",
        (json.dumps(churn_cols), len(churn_cols))
    )
    cur.execute(
        "UPDATE research_dataset_versions SET schema_json = ?, column_count = ? WHERE dataset_id IN (SELECT id FROM research_datasets WHERE dataset_id = 'external-india-pos-register-v1')",
        (json.dumps(pos_cols), len(pos_cols))
    )
    conn.commit()
    conn.close()
    print("Direct sqlite3 update done for", p.name)

