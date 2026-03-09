import sqlite3, uuid
from datetime import datetime, timezone

conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()
now = datetime.now(timezone.utc).isoformat()
TENANT = 'MONOGRAPH'

# Clone fca35779, skip the 4 deleted operational children
deleted = {'f0e65cf3','9935d75a','c3d253b5','820b2e59'}

cur.execute('SELECT item_template_id, reason FROM exclusion_list_item WHERE exclusion_list_id=?', ('fca35779',))
base_items = [(r[0], r[1]) for r in cur.fetchall() if r[0] not in deleted]
print(f'Base items (after removing deleted): {len(base_items)}')

# 12 new operation items to exclude
new_ops = [
    '6a780920','c7d3ece2','fd3ca682',
    'd45cfe75','4e9d29c5','a421d142',
    '74797a68','24160cca','b7e9e8a3',
    '6755790e','2e97d1b1','8bb92df0',
]
total = len(base_items) + len(new_ops)
print(f'New ops to add: {len(new_ops)}')
print(f'Total: {total}')

# Create new list
list_id = uuid.uuid4().hex[:8]
name = f'Standard {total}-Item Exclusion Set - v1'
cur.execute('''INSERT INTO exclusion_list
    (id, tenant_id, name, description, item_count, is_active, created_by, created_at, updated_at)
    VALUES (?,?,?,?,?,1,?,?,?)''',
    (list_id, TENANT, name, 'Flat electrical items. Cloned from fca35779 + 12 operation items.', total, 'admin', now, now))
print(f'Created list: {list_id} — {name}')

# Insert base items
for tmpl_id, reason in base_items:
    eid = uuid.uuid4().hex[:8]
    cur.execute('''INSERT INTO exclusion_list_item
        (id, tenant_id, exclusion_list_id, item_template_id, reason, created_at)
        VALUES (?,?,?,?,?,?)''',
        (eid, TENANT, list_id, tmpl_id, reason, now))

# Insert new operation items
for tmpl_id in new_ops:
    eid = uuid.uuid4().hex[:8]
    cur.execute('''INSERT INTO exclusion_list_item
        (id, tenant_id, exclusion_list_id, item_template_id, reason, created_at)
        VALUES (?,?,?,?,?,?)''',
        (eid, TENANT, list_id, tmpl_id, 'operational - excluded', now))

# Apply to units 230, 163, 164, 165
unit_inspections = {
    '230': None, '163': '4e51fb9a', '164': '96ad4e45', '165': '1fda9d3d'
}
for unit_num, insp_id in unit_inspections.items():
    cur.execute('SELECT id FROM unit WHERE unit_number=? AND tenant_id=?', (unit_num, TENANT))
    row = cur.fetchone()
    if not row:
        print(f'Unit {unit_num}: NOT FOUND')
        continue
    unit_id = row[0]
    cur.execute('UPDATE batch_unit SET exclusion_list_id=? WHERE unit_id=?', (list_id, unit_id))
    print(f'batch_unit updated: unit {unit_num}')
    if insp_id:
        cur.execute('UPDATE inspection SET exclusion_list_id=? WHERE id=?', (list_id, insp_id))
        print(f'inspection updated: {insp_id}')
    else:
        cur.execute('UPDATE inspection SET exclusion_list_id=? WHERE unit_id=? AND tenant_id=?', (list_id, unit_id, TENANT))
        print(f'inspection updated via unit_id: unit {unit_num}')

conn.commit()
print('COMMITTED')
conn.close()
