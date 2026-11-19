import sqlite3

conn = sqlite3.connect("d:/Capstone Project/_LOCAL_ARCHIVE_NOT_FOR_GITHUB/local_databases/backend_dev.db")
cur = conn.cursor()
cur.execute("PRAGMA foreign_key_check")
errs = cur.fetchall()
print("FK errors in archived DB:", len(errs))
cur.execute("SELECT count(*) FROM strategies")
print("Strategies in archived DB:", cur.fetchone()[0])
cur.execute("SELECT count(distinct strategy_id) FROM agent_evaluations")
print("Distinct strategy_id in agent_evaluations:", cur.fetchone()[0])

# Check missing strategy IDs in agent_evaluations
cur.execute("""
    SELECT ae.strategy_id, count(*) 
    FROM agent_evaluations ae 
    LEFT JOIN strategies s ON ae.strategy_id = s.id 
    WHERE s.id IS NULL 
    GROUP BY ae.strategy_id
""")
missing = cur.fetchall()
print(f"Missing strategies count: {len(missing)} (affects {sum(m[1] for m in missing)} evaluations)")
print("Sample missing strategy IDs:", missing[:3])

conn.close()

