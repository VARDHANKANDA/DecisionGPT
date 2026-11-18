"""Recover and merge historical research and platform data from archived DB into backend/dev.db.

Rules:
1. Preserve existing 3 demo accounts (admin, demo, researcher) and their password hashes.
2. Preserve existing demo business (Saanjh Handloom Co. ID: e41940d9-7083-45b1-8799-da21b39e13e7).
3. Insert all archived research datasets, versions, training runs, experiment runs,
   agent evaluations, agent runs, causal graphs, digital twin states/simulations,
   strategies, goals, decisions, saved reports, alerts, and other businesses.
4. Maintain transactional integrity.
"""
import sqlite3
from pathlib import Path

CURRENT_DB = Path("d:/Capstone Project/backend/dev.db")
ARCHIVED_DB = Path("d:/Capstone Project/_LOCAL_ARCHIVE_NOT_FOR_GITHUB/local_databases/backend_dev.db")

assert CURRENT_DB.exists(), "Current DB does not exist!"
assert ARCHIVED_DB.exists(), "Archived DB does not exist!"

conn_curr = sqlite3.connect(CURRENT_DB)
conn_arch = sqlite3.connect(ARCHIVED_DB)

conn_curr.row_factory = sqlite3.Row
conn_arch.row_factory = sqlite3.Row

cur_curr = conn_curr.cursor()
cur_arch = conn_arch.cursor()

# Get existing user mappings (email -> id)
cur_curr.execute("SELECT id, email FROM users")
curr_users = {r["email"]: r["id"] for r in cur_curr.fetchall()}

cur_arch.execute("SELECT id, email FROM users")
arch_users = {r["id"]: r["email"] for r in cur_arch.fetchall()}

# Create mapping from old user UUID to new user UUID if email matches
user_remap = {}
for old_id, email in arch_users.items():
    if email in curr_users:
        user_remap[old_id] = curr_users[email]

print(f"User remappings (email match): {user_remap}")

# Insert missing users
cur_arch.execute("SELECT * FROM users")
arch_user_rows = cur_arch.fetchall()
inserted_users = 0
for u in arch_user_rows:
    if u["email"] not in curr_users:
        cols = list(u.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join([f'"{c}"' for c in cols])
        cur_curr.execute(f"INSERT INTO users ({col_names}) VALUES ({placeholders})", [u[c] for c in cols])
        curr_users[u["email"]] = u["id"]
        inserted_users += 1
print(f"Inserted {inserted_users} additional users.")

# Helper to copy rows from archived to current
def copy_table(table_name, pk_col="id", transform_fn=None):
    cur_curr.execute(f"PRAGMA table_info('{table_name}')")
    curr_cols = [r[1] for r in cur_curr.fetchall()]
    if not curr_cols:
        print(f"Table {table_name} does not exist in current DB. Skipping.")
        return 0
    
    cur_curr.execute(f'SELECT "{pk_col}" FROM "{table_name}"')
    existing_pks = set(r[0] for r in cur_curr.fetchall())
    
    cur_arch.execute(f"PRAGMA table_info('{table_name}')")
    arch_cols = [r[1] for r in cur_arch.fetchall()]
    common_cols = [c for c in curr_cols if c in arch_cols]
    
    cur_arch.execute(f"SELECT * FROM \"{table_name}\"")
    arch_rows = cur_arch.fetchall()
    
    col_names = ", ".join([f'"{c}"' for c in common_cols])
    placeholders = ", ".join(["?"] * len(common_cols))
    insert_sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})'
    
    inserted = 0
    for row in arch_rows:
        pk_val = row[pk_col]
        if pk_val in existing_pks:
            continue
        vals = [row[c] for c in common_cols]
        if transform_fn:
            vals = transform_fn(common_cols, vals)
        cur_curr.execute(insert_sql, vals)
        existing_pks.add(pk_val)
        inserted += 1
        
    print(f"Table {table_name:30}: inserted {inserted} rows (total now: {len(existing_pks)})")
    return inserted

# Specific transform for businesses: remap owner_user_id
def transform_business(cols, vals):
    val_dict = dict(zip(cols, vals))
    owner = val_dict.get("owner_user_id")
    if owner and owner in user_remap:
        val_dict["owner_user_id"] = user_remap[owner]
    return [val_dict[c] for c in cols]

# Specific transform for models: check model_name + version uniqueness
def copy_models():
    cur_curr.execute("SELECT model_name, version FROM models")
    existing = set((r[0], r[1]) for r in cur_curr.fetchall())
    
    cur_arch.execute("PRAGMA table_info('models')")
    arch_cols = [r[1] for r in cur_arch.fetchall()]
    cur_curr.execute("PRAGMA table_info('models')")
    curr_cols = [r[1] for r in cur_curr.fetchall()]
    common_cols = [c for c in curr_cols if c in arch_cols]
    
    cur_arch.execute("SELECT * FROM models")
    arch_rows = cur_arch.fetchall()
    
    col_names = ", ".join([f'"{c}"' for c in common_cols])
    placeholders = ", ".join(["?"] * len(common_cols))
    insert_sql = f'INSERT INTO models ({col_names}) VALUES ({placeholders})'
    
    inserted = 0
    for r in arch_rows:
        key = (r["model_name"], r["version"])
        if key in existing:
            continue
        cur_curr.execute(insert_sql, [r[c] for c in common_cols])
        existing.add(key)
        inserted += 1
    print(f"Table models                        : inserted {inserted} rows (total now: {len(existing)})")
    return inserted

# Ordered copy to respect FKs
copy_table("businesses", pk_col="id", transform_fn=transform_business)
copy_table("research_datasets", pk_col="id")
copy_table("research_dataset_versions", pk_col="id")
copy_models()
copy_table("training_runs", pk_col="id")
copy_table("experiment_runs", pk_col="id")
copy_table("goals", pk_col="id")
copy_table("strategies", pk_col="id")
copy_table("decisions", pk_col="id")
copy_table("agent_runs", pk_col="id")
copy_table("agent_evaluations", pk_col="id")
copy_table("causal_graphs", pk_col="id")
copy_table("causal_edges", pk_col="id")
copy_table("digital_twin_states", pk_col="id")
copy_table("digital_twin_simulations", pk_col="id")
copy_table("products", pk_col="id")
copy_table("customers", pk_col="id")
copy_table("sales", pk_col="id")
copy_table("inventory", pk_col="id")
copy_table("marketing_campaigns", pk_col="id")
copy_table("business_memory", pk_col="id")
copy_table("analysis_runs", pk_col="id")
copy_table("saved_reports", pk_col="id")
copy_table("alerts", pk_col="id")
copy_table("data_prep_runs", pk_col="id")
copy_table("data_ingestion_jobs", pk_col="id")

conn_curr.commit()
print("\nAll historical records recovered and committed to dev.db successfully!")

conn_curr.close()
conn_arch.close()

