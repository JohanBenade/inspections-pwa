import sqlite3, uuid
from datetime import datetime, timezone
conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()
now = datetime.now(timezone.utc).isoformat()
TENANT = 'MONOGRAPH'
def gen_id(): return uuid.uuid4().hex[:8]

print('--- STEP 1: Known cycle mappings ---')
cycle_map = {'792812c7':'d91c233d','855cd617':'8e7f08f8','36e85327':'8e7f08f8','915b43b4':'8e7f08f8','179b2b9d':'d91c233d','951ea2db':'fca35779'}
for cycle_id, list_id in cycle_map.items():
    cur.execute("UPDATE inspection SET exclusion_list_id=?, updated_at=? WHERE cycle_id=? AND exclusion_list_id IS NULL AND tenant_id=?", (list_id, now, cycle_id, TENANT))
    print(f'  {cycle_id} -> {list_id}: {cur.rowcount} updated')

print('--- STEP 2: batch_unit known batches ---')
for batch_id, list_id in {'812dab77':'d91c233d','c173fdf3':'8e7f08f8','78b3b756':'8e7f08f8','7132b6f9':'d91c233d','78a45234':'fca35779'}.items():
    cur.execute("UPDATE batch_unit SET exclusion_list_id=? WHERE batch_id=? AND exclusion_list_id IS NULL", (list_id, batch_id))
    print(f'  {batch_id} -> {list_id}: {cur.rowcount} updated')
for un in ['029','030','046','054','055','056']:
    cur.execute("UPDATE batch_unit SET exclusion_list_id='8e7f08f8' WHERE batch_id='f7d88d82' AND unit_id=(SELECT id FROM unit WHERE unit_number=? AND tenant_id=?) AND exclusion_list_id IS NULL", (un, TENANT))
    print(f'  SR-005 unit {un}: {cur.rowcount} updated')

print('--- STEP 3: B6 1st Floor units 148-158 ---')
unit_skipped = {}
for un in ['148','149','150','151','152','154','155','156','157','158']:
    cur.execute("SELECT ii.item_template_id FROM inspection_item ii JOIN inspection i ON ii.inspection_id=i.id JOIN unit u ON i.unit_id=u.id WHERE u.unit_number=? AND u.tenant_id=? AND i.cycle_id='213a746f' AND ii.status='skipped' ORDER BY ii.item_template_id", (un, TENANT))
    unit_skipped[un] = tuple(r[0] for r in cur.fetchall())
    print(f'  Unit {un}: {len(unit_skipped[un])} skipped')
unique_sets = {}
for un, items in unit_skipped.items():
    key = frozenset(items)
    unique_sets.setdefault(key, []).append(un)
print(f'  Unique sets: {len(unique_sets)}')
set_to_list_id = {}
for fset, units in unique_sets.items():
    items = sorted(fset)
    list_id = gen_id()
    cur.execute("INSERT INTO exclusion_list (id,tenant_id,name,description,item_count,is_active,created_by,created_at,updated_at) VALUES (?,?,?,?,?,1,?,?,?)", (list_id, TENANT, f'B6 1st Floor C1 — {len(items)} items — v1', f'Retroactive units: {",".join(sorted(units))}', len(items), 'admin', now, now))
    for tmpl_id in items:
        cur.execute("INSERT INTO exclusion_list_item (id,tenant_id,exclusion_list_id,item_template_id,reason,created_at) VALUES (?,?,?,?,?,?)", (gen_id(), TENANT, list_id, tmpl_id, 'retroactive', now))
    set_to_list_id[frozenset(fset)] = list_id
    print(f'  Created {list_id}: {len(items)} items -> units {sorted(units)}')
for un, items in unit_skipped.items():
    list_id = set_to_list_id[frozenset(items)]
    cur.execute("UPDATE inspection SET exclusion_list_id=?, updated_at=? WHERE cycle_id='213a746f' AND unit_id=(SELECT id FROM unit WHERE unit_number=? AND tenant_id=?) AND exclusion_list_id IS NULL", (list_id, now, un, TENANT))
    cur.execute("UPDATE batch_unit SET exclusion_list_id=? WHERE batch_id='f7d88d82' AND unit_id=(SELECT id FROM unit WHERE unit_number=? AND tenant_id=?) AND exclusion_list_id IS NULL", (list_id, un, TENANT))

print('--- VERIFY ---')
cur.execute("SELECT COUNT(*) FROM inspection i JOIN batch_unit bu ON bu.unit_id=i.unit_id WHERE bu.batch_id IN ('812dab77','c173fdf3','78b3b756','7132b6f9','f7d88d82','78a45234') AND i.exclusion_list_id IS NULL")
print(f'  Remaining NULLs: {cur.fetchone()[0]} (expected 0)')
conn.commit()
print('COMMITTED')
conn.close()
