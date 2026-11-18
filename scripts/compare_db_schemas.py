import sqlite3

archived_db = "d:/Capstone Project/_LOCAL_ARCHIVE_NOT_FOR_GITHUB/local_databases/backend_dev.db"
current_db = "d:/Capstone Project/backend/dev.db"

conn_a = sqlite3.connect(archived_db)
conn_c = sqlite3.connect(current_db)

cur_a = conn_a.cursor()
cur_c = conn_c.cursor()

def get_cols(cur, table):
    try:
        cur.execute(f"PRAGMA table_info('{table}')")
        return [row[1] for row in cur.fetchall()]
    except Exception:
        return []

cur_c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
all_tables = [r[0] for r in cur_c.fetchall() if not r[0].startswith("sqlite_")]

print(f"{'TABLE':30} | {'ARCHIVED ROWS':15} | {'CURRENT ROWS':15} | SCHEMA DIFF")
print("-" * 80)

for t in all_tables:
    cols_a = get_cols(cur_a, t)
    cols_c = get_cols(cur_c, t)
    
    cnt_a = 0
    cnt_c = 0
    if cols_a:
        cur_a.execute(f"SELECT count(*) FROM '{t}'")
        cnt_a = cur_a.fetchone()[0]
    if cols_c:
        cur_c.execute(f"SELECT count(*) FROM '{t}'")
        cnt_c = cur_c.fetchone()[0]
        
    diff = ""
    if set(cols_a) != set(cols_c):
        added = set(cols_c) - set(cols_a)
        removed = set(cols_a) - set(cols_c)
        diff = f"+{list(added)} -{list(removed)}" if (added or removed) else "col types differ"
        
    if cnt_a > 0 or cnt_c > 0 or any(k in t for k in ["research", "model", "eval", "bench", "experiment"]):
        print(f"{t:30} | {cnt_a:<15} | {cnt_c:<15} | {diff}")

conn_a.close()
conn_c.close()

