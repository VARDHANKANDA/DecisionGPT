import os
import sqlite3
import json
from pathlib import Path

def audit_models():
    db_path = Path("d:/Capstone Project/backend/dev.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.execute("SELECT id, model_name, version, model_type, status, metrics_json, model_path, created_at FROM models ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    
    print("=" * 80)
    print("DECISIONGPT REGISTERED ML MODELS AUDIT (ALL 9 REGISTERED MODELS)")
    print("=" * 80)
    print(f"Total registered models found in database: {len(rows)}")
    
    active_count = 0
    archived_count = 0
    
    for r in rows:
        m_id, name, ver, m_type, status, mj_raw, path, created = r
        mj = json.loads(mj_raw) if mj_raw else {}
        
        # Check artifact on disk
        full_path = Path("d:/Capstone Project") / path if path else None
        exists = full_path.exists() if full_path else False
        
        if status == "active":
            active_count += 1
        else:
            archived_count += 1
            
        print(f"\nModel ID: {m_id}")
        print(f"  Name: {name} (Version: {ver}, Type: {m_type})")
        print(f"  Status: {status.upper()}")
        print(f"  Created: {created}")
        print(f"  Artifact Path: {path} (Exists on disk: {exists})")
        print(f"  Metrics Count: {len(mj)} keys -> {list(mj.keys())}")
        if "mae" in mj:
            print(f"    MAE: {mj['mae']}, RMSE: {mj.get('rmse')}, MAPE: {mj.get('mape')}")
        if "roc_auc" in mj:
            print(f"    ROC-AUC: {mj['roc_auc']}, F1: {mj.get('f1')}, Precision: {mj.get('precision')}, Recall: {mj.get('recall')}")
            
    print("\n" + "=" * 80)
    print(f"Summary: Active v1 Models = {active_count}, Candidate/Archived Models = {archived_count}, Total = {len(rows)}")
    print("=" * 80)
    
if __name__ == "__main__":
    audit_models()

