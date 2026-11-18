import sqlite3

for name, path in [
    ("archived", "d:/Capstone Project/_LOCAL_ARCHIVE_NOT_FOR_GITHUB/local_databases/backend_dev.db"),
    ("current", "d:/Capstone Project/backend/dev.db")
]:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info('agent_evaluations')")
    cols = [r[1] for r in cur.fetchall()]
    print(name, "cols:", cols)
    if name == "archived":
        cur.execute("SELECT * FROM agent_evaluations LIMIT 1")
        row = cur.fetchone()
        print("archived row 0:", dict(zip(cols, row)))
    conn.close()

