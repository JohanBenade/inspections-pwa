#!/usr/bin/env python3
"""
q_dup_check.py - Duplicate detection diagnostic for unit 011 BATHROOM/PLUMBING.

Three sections:
  1. Same item_template_id appearing multiple times in unit 011 C2
     -> If any rows, real DB-level duplicates (Bug 2 confirmed real)
     -> If zero rows, "duplicates" were rendering artifact (v327 closed it)
  2. Full BATHROOM/PLUMBING inspection_item rows for unit 011 C2
     -> Shows what the inspector actually sees in that category
  3. BATHROOM/PLUMBING item_template catalog (template uniqueness)
     -> Shows whether the templates themselves have duplicates upstream
"""

import sqlite3

DB = '/var/data/inspections.db'
INSPECTION_ID = '1f666236'  # unit 011 C2 per v316 handover

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

print("=" * 60)
print("1. inspection_item rows with duplicate template_id (unit 011 C2)")
print("=" * 60)
rows = conn.execute("""
    SELECT item_template_id, COUNT(*) AS n
    FROM inspection_item
    WHERE inspection_id = ?
    GROUP BY item_template_id
    HAVING n > 1
""", [INSPECTION_ID]).fetchall()
if not rows:
    print("(zero rows - no DB-level duplicates)")
else:
    for r in rows:
        print(dict(r))

print()
print("=" * 60)
print("2. BATHROOM/PLUMBING inspection_item rows for unit 011 C2")
print("=" * 60)
rows = conn.execute("""
    SELECT ii.id,
           ii.item_template_id,
           it.item_description,
           ii.status,
           ii.has_prior_defects,
           ii.marked_at,
           it.parent_item_id,
           it.item_order
    FROM inspection_item ii
    JOIN item_template it ON ii.item_template_id = it.id
    JOIN category_template ct ON it.category_id = ct.id
    JOIN area_template a ON ct.area_id = a.id
    WHERE ii.inspection_id = ?
      AND a.area_name LIKE '%BATHROOM%'
      AND ct.category_name LIKE '%PLUMBING%'
    ORDER BY it.item_order
""", [INSPECTION_ID]).fetchall()
if not rows:
    print("(zero rows)")
else:
    for r in rows:
        print(dict(r))

print()
print("=" * 60)
print("3. BATHROOM/PLUMBING item_template catalog")
print("=" * 60)
rows = conn.execute("""
    SELECT it.id,
           it.item_description,
           it.parent_item_id,
           it.item_order,
           ct.category_name,
           a.area_name
    FROM item_template it
    JOIN category_template ct ON it.category_id = ct.id
    JOIN area_template a ON ct.area_id = a.id
    WHERE a.area_name LIKE '%BATHROOM%'
      AND ct.category_name LIKE '%PLUMBING%'
    ORDER BY a.area_name, ct.category_name, it.item_order
""").fetchall()
if not rows:
    print("(zero rows)")
else:
    for r in rows:
        print(dict(r))

conn.close()
print()
print("DONE")
