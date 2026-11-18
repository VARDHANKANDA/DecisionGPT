import sqlite3
import json

archived_db = "d:/Capstone Project/_LOCAL_ARCHIVE_NOT_FOR_GITHUB/local_databases/backend_dev.db"
conn = sqlite3.connect(archived_db)
cur = conn.cursor()

cur.execute("SELECT id, model_name, version, model_type, status, metrics_json, model_path FROM models")
for r in cur.fetchall():
    mj = json.loads(r[5]) if r[5] else {}
    print(f"ID: {r[0]} | Name: {r[1]} | Ver: {r[2]} | Type: {r[3]} | Status: {r[4]} | Metrics: {list(mj.keys())} | Path: {r[6]}")

conn.close()
