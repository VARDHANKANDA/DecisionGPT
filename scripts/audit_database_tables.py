import sqlite3

conn = sqlite3.connect('backend/dev.db')
c = conn.cursor()
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
print(f"Total tables in backend/dev.db: {len(tables)}")
for t in sorted(tables):
    cnt = c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    print(f"  {t:35s}: {cnt:6d} rows")

