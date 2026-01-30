#!/usr/bin/env python3
import sqlite3

DB_PATH = '/var/data/inspections.db'
SQL_PATH = 'scripts/load_template.sql'

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

with open(SQL_PATH, 'r') as f:
    sql = f.read()

cur.executescript(sql)
conn.commit()

cur.execute("SELECT area_name FROM area_template WHERE tenant_id = 'MONOGRAPH' ORDER BY area_order")
areas = [r[0] for r in cur.fetchall()]

cur.execute("SELECT COUNT(*) FROM item_template WHERE tenant_id = 'MONOGRAPH'")
count = cur.fetchone()[0]

conn.close()

print(f"Done! Items: {count}")
print(f"Areas: {areas}")
