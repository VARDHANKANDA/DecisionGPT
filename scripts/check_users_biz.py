import sqlite3

current_db = "d:/Capstone Project/backend/dev.db"
archived_db = "d:/Capstone Project/_LOCAL_ARCHIVE_NOT_FOR_GITHUB/local_databases/backend_dev.db"

conn_c = sqlite3.connect(current_db)
conn_a = sqlite3.connect(archived_db)

cur_c = conn_c.cursor()
cur_a = conn_a.cursor()

cur_c.execute("SELECT id, email, role FROM users")
users_c = {r[1]: (r[0], r[2]) for r in cur_c.fetchall()}

cur_a.execute("SELECT id, email, role FROM users")
users_a = {r[1]: (r[0], r[2]) for r in cur_a.fetchall()}

print("Users in Current:", users_c)
print("Users in Archived:", users_a)

cur_c.execute("SELECT id, name FROM businesses")
biz_c = {r[0]: r[1] for r in cur_c.fetchall()}

cur_a.execute("SELECT id, name FROM businesses")
biz_a = {r[0]: r[1] for r in cur_a.fetchall()}

print("Businesses in Current:", biz_c)
print(f"Businesses in Archived ({len(biz_a)}):", list(biz_a.items())[:5])

conn_c.close()
conn_a.close()

