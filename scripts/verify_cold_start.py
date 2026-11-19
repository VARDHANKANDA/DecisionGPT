import os
import sys
from pathlib import Path

backend_dir = Path("d:/Capstone Project/backend")
sys.path.insert(0, str(backend_dir))
os.chdir(str(backend_dir))

import sqlite3
from app.db.session import engine, Base, SessionLocal
from app.main import on_startup

db_path = backend_dir / "dev.db"

def get_table_counts():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in cur.fetchall()]
    counts = {}
    total = 0
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM \"{t}\"")
        c = cur.fetchone()[0]
        counts[t] = c
        total += c
    conn.close()
    return counts, total

print("=" * 80)
print("COLD-START ZERO-DATA-LOSS VERIFICATION")
print("=" * 80)

counts_before, total_before = get_table_counts()
print(f"Pre-startup database record count across {len(counts_before)} tables: {total_before:,}")

print("\nExecuting FastAPI on_startup lifecycle hook...")
on_startup()
print("on_startup completed successfully.")

counts_after, total_after = get_table_counts()
print(f"Post-startup database record count across {len(counts_after)} tables: {total_after:,}")

discrepancies = []
for t, cnt in counts_before.items():
    cnt_after = counts_after.get(t, 0)
    if cnt != cnt_after:
        discrepancies.append((t, cnt, cnt_after))

if not discrepancies and total_before == total_after:
    print("\n✓ ZERO DATA LOSS VERIFIED: Exactly 100% of tables and rows preserved after cold start!")
    print(f"  Total records: {total_after:,}")
    print(f"  Models: {counts_after.get('models')}")
    print(f"  Businesses: {counts_after.get('businesses')}")
    print(f"  Experiment Runs: {counts_after.get('experiment_runs')}")
    print(f"  Training Runs: {counts_after.get('training_runs')}")
else:
    print(f"\n❌ Discrepancies detected: {discrepancies}")
    sys.exit(1)
print("=" * 80)

