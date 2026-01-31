#!/usr/bin/env python3
"""Run this in Render Shell to load the real template."""
import sqlite3
import os

DB_PATH = '/var/data/inspections.db'
SQL_FILE = '/opt/render/project/src/scripts/load_real_template.sql'

if not os.path.exists(SQL_FILE):
    print(f"ERROR: SQL file not found at {SQL_FILE}")
    exit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("Loading real template...")
with open(SQL_FILE, 'r') as f:
    sql = f.read()

cur.executescript(sql)
conn.commit()

# Verify
print("\nVerification:")
print(f"  Areas: {cur.execute('SELECT COUNT(*) FROM area_template').fetchone()[0]}")
print(f"  Categories: {cur.execute('SELECT COUNT(*) FROM category_template').fetchone()[0]}")
print(f"  Items: {cur.execute('SELECT COUNT(*) FROM item_template').fetchone()[0]}")
print("\nArea names:")
for r in cur.execute('SELECT area_name FROM area_template ORDER BY area_order'):
    print(f"  - {r[0]}")

conn.close()
print("\nDone!")
