import sqlite3
from pathlib import Path

db_paths = [
    Path("d:/Capstone Project/backend/dev.db"),
    Path("d:/Capstone Project/dev.db"),
    Path("d:/Capstone Project/_LOCAL_ARCHIVE_NOT_FOR_GITHUB/local_databases/backend_dev.db"),
    Path("d:/Capstone Project/_LOCAL_ARCHIVE_NOT_FOR_GITHUB/research_experiments/_eval_scratch_ablation.db"),
    Path("d:/Capstone Project/_LOCAL_ARCHIVE_NOT_FOR_GITHUB/research_experiments/_eval_scratch_candidates.db"),
]

for p in db_paths:
    print("=" * 80)
    print(f"DATABASE: {p}")
    print(f"Exists: {p.exists()}, Size: {p.stat().st_size if p.exists() else 0} bytes")
    if not p.exists() or p.stat().st_size == 0:
        continue
    try:
        conn = sqlite3.connect(p)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]
        print(f"Total tables: {len(tables)}")
        for t in tables:
            try:
                cursor.execute(f'SELECT count(*) FROM "{t}"')
                cnt = cursor.fetchone()[0]
                if cnt > 0 or any(k in t.lower() for k in ["research", "model", "eval", "bench", "experiment", "train", "ablation"]):
                    print(f"  - {t:35}: {cnt} rows")
            except Exception as e:
                print(f"  - {t:35}: Error {e}")
        conn.close()
    except Exception as e:
        print(f"Failed to inspect {p}: {e}")

