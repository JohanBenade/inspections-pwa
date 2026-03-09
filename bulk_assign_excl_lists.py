"""
Bulk assign exclusion lists to SR-001 through SR-006 units.
Also creates B6 1st Floor exclusion lists for units 148-158 from actual skipped items.

Cycle to list mapping (from handover verified data):
  792812c7  B5 Ground C1    -> d91c233d (90 items)
  855cd617  B5 Ground C2    -> 8e7f08f8 (91 items)
  36e85327  B6 Ground C1    -> 8e7f08f8 (91 items)
  915b43b4  B7 Ground C1    -> 8e7f08f8 (91 items)
  179b2b9d  B5 1st Floor C1 -> d91c233d (90 items)
  951ea2db  B5 2nd Floor C1 -> fca35779 (109 items)
  213a746f  B6 1st Floor C1 -> CREATE from actual skipped items
"""
import sqlite3, uuid
from datetime import datetime, timezone

conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()
now = datetime.now(timezone.utc).isoformat()
TENANT = 'MONOGRAPH'

def gen_id():
    return uuid.uuid4().hex[:8]

# -------------------------------------------------------
# STEP 1: Update inspection.exclusion_list_id by cycle
# -------------------------------------------------------
print('--- STEP 1: Assign known cycle mappings to inspections ---')

cycle_map = {
    '792812c7': 'd91c233d',
    '855cd617': '8e7f08f8',
    '36e85327': '8e7f08f8',
    '915b43b4': '8e7f08f8',
    '179b2b9d': 'd91c233d',
    '951ea2db': 'fca35779',
}

for cycle_id, list_id in cycle_map.items():
    cur.execute("""
        UPDATE inspection SET exclusion_list_id=?, updated_at=?
        WHERE cycle_id=? AND exclusion_list_id IS NULL AND tenant_id=?
    """, (list_id, now, cycle_id, TENANT))
    print(f'  Cycle {cycle_id} -> {list_id}: {cur.rowcount} inspections updated')

# -------------------------------------------------------
# STEP 2: Update batch_unit.exclusion_list_id
# Simple batches (single cycle each)
# -------------------------------------------------------
print()
print('--- STEP 2: Assign known lists to batch_unit rows ---')

batch_list_map = {
    '812dab77': 'd91c233d',  # SR-001 B5 Ground C1
    'c173fdf3': '8e7f08f8',  # SR-002 B6 Ground C1
    '78b3b756': '8e7f08f8',  # SR-003 B7 Ground C1
    '7132b6f9': 'd91c233d',  # SR-004 B5 1st Floor C1
    '78a45234': 'fca35779',  # SR-006 B5 2nd Floor C1
}

for batch_id, list_id in batch_list_map.items():
    cur.execute("""
        UPDATE batch_unit SET exclusion_list_id=?
        WHERE batch_id=? AND exclusion_list_id IS NULL
    """, (list_id, batch_id))
    print(f'  Batch {batch_id} -> {list_id}: {cur.rowcount} batch_unit rows updated')

# SR-005 (f7d88d82): mixed batch — update non-B6-1stFloor units
# Units 029, 030 (B5 Ground C2) -> 8e7f08f8
# Units 046, 054, 055, 056 (B6/B7 Ground C1) -> 8e7f08f8
# Units 148-158 (B6 1st Floor) -> handled in step 3
sr005_units_known = ['029', '030', '046', '054', '055', '056']
for un in sr005_units_known:
    cur.execute("""
        UPDATE batch_unit SET exclusion_list_id='8e7f08f8'
        WHERE batch_id='f7d88d82'
        AND unit_id=(SELECT id FROM unit WHERE unit_number=? AND tenant_id=?)
        AND exclusion_list_id IS NULL
    """, (un, TENANT))
    print(f'  SR-005 unit {un} -> 8e7f08f8: {cur.rowcount} updated')

# -------------------------------------------------------
# STEP 3: B6 1st Floor units 148-158
# Pull actual skipped items, group by unique sets, create lists, assign
# -------------------------------------------------------
print()
print('--- STEP 3: B6 1st Floor units 148-158 ---')

b6_units = ['148','149','150','151','152','154','155','156','157','158']

# Pull skipped item sets per unit
unit_skipped = {}
for un in b6_units:
    cur.execute("""
        SELECT ii.item_template_id
        FROM inspection_item ii
        JOIN inspection i ON ii.inspection_id = i.id
        JOIN unit u ON i.unit_id = u.id
        WHERE u.unit_number=? AND u.tenant_id=? AND i.cycle_id='213a746f'
          AND ii.status='skipped'
        ORDER BY ii.item_template_id
    """, (un, TENANT))
    items = tuple(r[0] for r in cur.fetchall())
    unit_skipped[un] = items
    print(f'  Unit {un}: {len(items)} skipped items')

# Find unique sets
unique_sets = {}  # frozenset -> list of units
for un, items in unit_skipped.items():
    key = frozenset(items)
    if key not in unique_sets:
        unique_sets[key] = []
    unique_sets[key].append(un)

print(f'  Unique exclusion sets found: {len(unique_sets)}')

# Create one named list per unique set, assign to units
set_to_list_id = {}
for i, (fset, units) in enumerate(unique_sets.items(), 1):
    items = sorted(fset)
    count = len(items)
    list_id = gen_id()
    name = f'B6 1st Floor C1 — {count} items — v1'
    desc = f'Retroactive — actual skipped items. Units: {", ".join(sorted(units))}'
    cur.execute("""
        INSERT INTO exclusion_list
        (id,tenant_id,name,description,item_count,is_active,created_by,created_at,updated_at)
        VALUES (?,?,?,?,?,1,?,?,?)
    """, (list_id, TENANT, name, desc, count, 'admin', now, now))
    for tmpl_id in items:
        cur.execute("""
            INSERT INTO exclusion_list_item
            (id,tenant_id,exclusion_list_id,item_template_id,reason,created_at)
            VALUES (?,?,?,?,?,?)
        """, (gen_id(), TENANT, list_id, tmpl_id, 'retroactive', now))
    set_to_list_id[frozenset(fset)] = list_id
    print(f'  Created list {list_id}: {name} -> units {sorted(units)}')

# Assign to inspections and batch_unit rows
for un, items in unit_skipped.items():
    list_id = set_to_list_id[frozenset(items)]
    cur.execute("""
        UPDATE inspection SET exclusion_list_id=?, updated_at=?
        WHERE cycle_id='213a746f'
        AND unit_id=(SELECT id FROM unit WHERE unit_number=? AND tenant_id=?)
        AND exclusion_list_id IS NULL
    """, (list_id, now, un, TENANT))
    cur.execute("""
        UPDATE batch_unit SET exclusion_list_id=?
        WHERE batch_id='f7d88d82'
        AND unit_id=(SELECT id FROM unit WHERE unit_number=? AND tenant_id=?)
        AND exclusion_list_id IS NULL
    """, (list_id, un, TENANT))
    print(f'  Unit {un}: assigned {list_id}')

# -------------------------------------------------------
# VERIFY
# -------------------------------------------------------
print()
print('--- VERIFY: any remaining NULLs in SR-001 to SR-006? ---')
cur.execute("""
    SELECT ib.name, COUNT(*) as null_count
    FROM batch_unit bu
    JOIN inspection_batch ib ON ib.id = bu.batch_id
    JOIN inspection i ON i.unit_id = bu.unit_id
    WHERE bu.batch_id IN (
        '812dab77','c173fdf3','78b3b756','7132b6f9','f7d88d82','78a45234'
    )
    AND i.exclusion_list_id IS NULL
    GROUP BY ib.name
""")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f'  STILL NULL: {r}')
else:
    print('  All assigned - no NULLs remaining')

conn.commit()
print()
print('COMMITTED')
conn.close()
