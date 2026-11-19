import sqlite3
from pathlib import Path

db_backend = Path("d:/Capstone Project/backend/dev.db")
db_root = Path("d:/Capstone Project/dev.db")

tables_to_check = [
    "agent_evaluations",
    "agent_runs",
    "experiment_runs",
    "training_runs",
    "research_datasets",
    "research_dataset_versions",
    "causal_graphs",
    "causal_edges",
    "digital_twin_states",
    "digital_twin_simulations",
    "strategies",
    "goals",
    "decisions",
    "saved_reports",
    "alerts",
    "data_prep_runs",
    "data_ingestion_jobs",
    "businesses",
    "customers",
    "sales",
    "inventory",
    "marketing_campaigns",
    "business_memory",
    "models",
]

def check_db(path: Path):
    print("=" * 70)
    print(f"CHECKING: {path} (Size: {path.stat().st_size:,} bytes)")
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    
    # 1. Integrity check
    cur.execute("PRAGMA integrity_check")
    integrity = cur.fetchall()
    print("  Integrity check:", integrity)
    assert integrity == [("ok",)], f"Integrity check failed: {integrity}"
    
    # 2. Foreign key check
    cur.execute("PRAGMA foreign_key_check")
    fk_errors = cur.fetchall()
    print("  Foreign key errors count:", len(fk_errors))
    if fk_errors:
        print("  Sample FK errors:", fk_errors[:5])
        
    # 3. Tables check
    print(f"  {'TABLE':30} | {'ROW COUNT':10}")
    print("  " + "-" * 45)
    counts = {}
    for t in tables_to_check:
        try:
            cur.execute(f'SELECT count(*) FROM "{t}"')
            cnt = cur.fetchone()[0]
            counts[t] = cnt
            print(f"  {t:30} | {cnt:<10}")
        except Exception as e:
            print(f"  {t:30} | Error: {e}")
            counts[t] = -1
            
    conn.close()
    return counts

counts_backend = check_db(db_backend)
counts_root = check_db(db_root)

# Check parity
print("=" * 70)
diffs = []
for t in tables_to_check:
    if counts_backend.get(t) != counts_root.get(t):
        diffs.append((t, counts_backend.get(t), counts_root.get(t)))
if diffs:
    print("Differences between backend/dev.db and root dev.db:", diffs)
else:
    print("PERFECT PARITY: Both databases have identical row counts across all 24 tables!")

