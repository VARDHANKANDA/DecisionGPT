import sqlite3
import json

db_path = "d:/Capstone Project/_LOCAL_ARCHIVE_NOT_FOR_GITHUB/local_databases/backend_dev.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=== EXPERIMENT RUNS ===")
cursor.execute("SELECT * FROM experiment_runs")
for r in cursor.fetchall():
    d = dict(r)
    print(f"ID: {d.get('id')} | Type: {d.get('experiment_type')} | Status: {d.get('status')} | Created: {d.get('created_at')}")

print("\n=== TRAINING RUNS ===")
cursor.execute("SELECT * FROM training_runs")
for r in cursor.fetchall():
    d = dict(r)
    print(f"ID: {d.get('id')} | Model: {d.get('model_name')} | Version: {d.get('version')} | Status: {d.get('status')} | Created: {d.get('created_at')}")

print("\n=== RESEARCH DATASETS ===")
cursor.execute("SELECT * FROM research_datasets")
for r in cursor.fetchall():
    d = dict(r)
    print(f"ID: {d.get('id')} | Name: {d.get('name')} | Domain: {d.get('domain')} | Storage: {d.get('storage_path')}")

print("\n=== RESEARCH DATASET VERSIONS ===")
cursor.execute("SELECT * FROM research_dataset_versions")
for r in cursor.fetchall():
    d = dict(r)
    print(f"ID: {d.get('id')} | DatasetID: {d.get('dataset_id')} | Version: {d.get('version')} | Rows: {d.get('num_rows')} | SHA: {d.get('sha256')}")

print("\n=== AGENT EVALUATIONS SAMPLE ===")
cursor.execute("SELECT count(*), task, agent_name, metric_name FROM agent_evaluations GROUP BY task, agent_name, metric_name")
for r in cursor.fetchall():
    print(" ", dict(r))

conn.close()

