import sqlite3
import json

conn = sqlite3.connect('dev.db')
cur = conn.cursor()
cur.execute("SELECT id, model_name, version, lifecycle_json FROM models WHERE status='active'")
for r in cur.fetchall():
    life = json.loads(r[3]) if r[3] else {}
    if 'reevaluation' in life:
        print(r[1], r[2], '->', life['reevaluation'].get('metrics'), 'baseline:', life['reevaluation'].get('baseline'))
conn.close()

