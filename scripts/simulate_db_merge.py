import sqlite3

current_db = "d:/Capstone Project/backend/dev.db"
archived_db = "d:/Capstone Project/_LOCAL_ARCHIVE_NOT_FOR_GITHUB/local_databases/backend_dev.db"

conn_c = sqlite3.connect(current_db)
conn_a = sqlite3.connect(archived_db)

cur_c = conn_c.cursor()
cur_a = conn_a.cursor()

def get_pk(cur, table):
    cur.execute(f"PRAGMA table_info('{table}')")
    pks = [r[1] for r in cur.fetchall() if r[5] > 0]
    return pks or ['id']

cur_c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur_c.fetchall() if not r[0].startswith("sqlite_") and r[0] != "alembic_version"]

print(f"{'TABLE':30} | {'CURRENT':8} | {'ARCHIVED':8} | {'TO INSERT':10}")
print("-" * 65)

total_to_insert = 0
for t in tables:
    cur_c.execute(f"SELECT count(*) FROM '{t}'")
    cnt_c = cur_c.fetchone()[0]
    
    cur_a.execute(f"SELECT count(*) FROM '{t}'")
    cnt_a = cur_a.fetchone()[0]
    
    # Check PK
    pks = get_pk(cur_c, t)
    
    # Get existing PKs in current
    pk_str = ", ".join(f"\"{p}\"" for p in pks)
    cur_c.execute(f"SELECT {pk_str} FROM '{t}'")
    existing_pks = set(cur_c.fetchall())
    
    cur_a.execute(f"SELECT {pk_str} FROM '{t}'")
    archived_pks = cur_a.fetchall()
    
    new_rows = [p for p in archived_pks if p not in existing_pks]
    if cnt_c > 0 or cnt_a > 0 or len(new_rows) > 0:
        print(f"{t:30} | {cnt_c:<8} | {cnt_a:<8} | {len(new_rows):<10}")
    total_to_insert += len(new_rows)

print("-" * 65)
print(f"Total new records to merge: {total_to_insert}")

conn_c.close()
conn_a.close()

