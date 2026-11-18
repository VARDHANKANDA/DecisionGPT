import sqlite3

db_path = "d:/Capstone Project/_LOCAL_ARCHIVE_NOT_FOR_GITHUB/local_databases/backend_dev.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== USERS IN ARCHIVED DB ===")
cursor.execute("SELECT id, email, role, is_active FROM users")
for u in cursor.fetchall():
    print(" ", u)

print("\n=== BUSINESSES IN ARCHIVED DB ===")
cursor.execute("SELECT id, name, industry FROM businesses")
for b in cursor.fetchall():
    print(" ", b)

print("\n=== RESEARCH DATASETS IN ARCHIVED DB ===")
cursor.execute("SELECT id, name, domain, created_at FROM research_datasets")
for d in cursor.fetchall():
    print(" ", d)

print("\n=== RESEARCH DATASET VERSIONS IN ARCHIVED DB ===")
cursor.execute("SELECT id, dataset_id, version, num_rows, status FROM research_dataset_versions")
for v in cursor.fetchall():
    print(" ", v)

print("\n=== MODELS IN ARCHIVED DB ===")
cursor.execute("SELECT id, model_name, version, model_type, status, metrics_json FROM models")
for m in cursor.fetchall():
    print(" ", m[0], m[1], m[2], m[3], m[4], (m[5][:60] + "...") if m[5] else None)

print("\n=== EXPERIMENT RUNS IN ARCHIVED DB ===")
cursor.execute("SELECT id, experiment_name, status, created_at FROM experiment_runs")
for er in cursor.fetchall():
    print(" ", er)

print("\n=== AGENT EVALUATIONS IN ARCHIVED DB ===")
cursor.execute("SELECT count(*), task, agent_name FROM agent_evaluations GROUP BY task, agent_name")
for ae in cursor.fetchall():
    print(" ", ae)

print("\n=== TRAINING RUNS IN ARCHIVED DB ===")
cursor.execute("SELECT id, model_name, version, status, metrics_json FROM training_runs")
for tr in cursor.fetchall():
    print(" ", tr[0], tr[1], tr[2], tr[3], (tr[4][:60] + "...") if tr[4] else None)

conn.close()

