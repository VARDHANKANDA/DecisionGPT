import sys
import pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal
from app.models.research import ResearchDataset, ResearchDatasetVersion
import sqlite3

churn_csv = ROOT / "data" / "external" / "india_telecom_churn" / "processed" / "india_telecom_churn_clean.csv"
pos_csv = ROOT / "data" / "external" / "india_pos_register" / "processed" / "india_pos_register_clean.csv"

df_churn = pd.read_csv(churn_csv, nrows=10)
churn_cols = [{"name": str(c), "dtype": str(df_churn[c].dtype)} for c in df_churn.columns]

df_pos = pd.read_csv(pos_csv, nrows=10)
pos_cols = [{"name": str(c), "dtype": str(df_pos[c].dtype)} for c in df_pos.columns]

import json

for db_path in [ROOT / "backend" / "dev.db", ROOT / "dev.db"]:
    if not db_path.exists():
        continue
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    
    # Find dataset IDs
    cur.execute("SELECT id, dataset_id FROM research_datasets WHERE dataset_id IN ('india_telecom_churn', 'india_pos_register')")
    rows = cur.fetchall()
    for row in rows:
        ds_uuid, slug = row[0], row[1]
        cols = churn_cols if slug == "india_telecom_churn" else pos_cols
        cols_json = json.dumps(cols)
        cur.execute(
            "UPDATE research_dataset_versions SET schema_json = ?, column_count = ? WHERE dataset_id = ?",
            (cols_json, len(cols), ds_uuid)
        )
        print(f"Updated {slug} in {db_path.name}: {len(cols)} columns")
    conn.commit()
    conn.close()

print("Database update completed.")

