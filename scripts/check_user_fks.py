import sqlite3

archived_db = "d:/Capstone Project/_LOCAL_ARCHIVE_NOT_FOR_GITHUB/local_databases/backend_dev.db"
conn_a = sqlite3.connect(archived_db)
cur_a = conn_a.cursor()

cur_a.execute("PRAGMA foreign_key_list('businesses')")
print("businesses FKs:", cur_a.fetchall())

# Check where user_id is used
cur_a.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur_a.fetchall() if not r[0].startswith("sqlite_")]

for t in tables:
    cur_a.execute(f"PRAGMA table_info('{t}')")
    cols = [r[1] for r in cur_a.fetchall()]
    if "user_id" in cols or "owner_id" in cols:
        print(f"Table '{t}' has user column: {[c for c in cols if 'user' in c or 'owner' in c]}")

conn_a.close()

