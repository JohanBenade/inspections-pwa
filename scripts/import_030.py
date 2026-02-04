import sqlite3, uuid
from datetime import datetime

conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()

UNIT_NUMBER = '030'
INSPECTOR_ID = 'insp-004'
INSPECTOR_NAME = 'Thembinkosi Biko'
INSPECTION_DATE = '2026-01-27'
TENANT = 'MONOGRAPH'
CYCLE_ID = '792812c7'

cur.execute('SELECT id FROM unit WHERE unit_number=? AND tenant_id=?', (UNIT_NUMBER, TENANT))
row = cur.fetchone()
if not row:
    print(f'ERROR: Unit {UNIT_NUMBER} not found')
    conn.close()
    exit()
unit_id = row[0]
print(f'Unit {UNIT_NUMBER}: {unit_id}')

cur.execute('SELECT id FROM inspection WHERE unit_id=? AND cycle_id=?', (unit_id, CYCLE_ID))
if cur.fetchone():
    print('ERROR: Inspection already exists for this unit/cycle')
    conn.close()
    exit()

cur.execute('SELECT item_template_id FROM cycle_excluded_item WHERE cycle_id=?', (CYCLE_ID,))
excluded_ids = set(r[0] for r in cur.fetchall())
print(f'Exclusions: {len(excluded_ids)}')

cur.execute('SELECT id FROM item_template WHERE tenant_id=?', (TENANT,))
all_template_ids = [r[0] for r in cur.fetchall()]
print(f'Template items: {len(all_template_ids)}')

# (template_id, defect_type, comment)
# Note: Bedroom D door stop (6f905df9) has 2 defects
defects = [
    # KITCHEN (4)
    ('522b4aeb', 'not_to_standard', 'Chipped tile by bedroom A and B'),
    ('117c2748', 'not_to_standard', 'Shelf not installed/fitted in properly'),
    ('ff38c47c', 'not_to_standard', 'Third cabinet/drawer does not close all the way'),
    ('5fe88982', 'not_to_standard', 'Leg support not fixed to floor'),
    # BATHROOM (3)
    ('39fe1eda', 'not_to_standard', 'WC indicator does not turn to show right colours'),
    ('019d6605', 'not_to_standard', 'Arm cover plate is loose'),
    ('1beaecc9', 'not_to_standard', 'Rose cover plate is loose'),
    # BEDROOM A (2)
    ('ed15ccaf', 'not_to_standard', 'Clothing hanger inside B.I.C is not installed'),
    ('039bdc70', 'not_installed', 'B.I.C door stopper not installed'),
    # BEDROOM B (2)
    ('1eb374be', 'not_to_standard', 'Clothing hanger inside B.I.C is not installed'),
    ('aef89fec', 'not_installed', 'B.I.C door stopper not installed'),
    # BEDROOM C (2)
    ('80177e8e', 'not_to_standard', 'Door upside not finished well, needs repaint/one more coat'),
    ('968ba64b', 'not_to_standard', 'Clothing hanger inside B.I.C is not installed'),
    # BEDROOM D (3 defect records, 2 unique template items)
    ('6f905df9', 'not_to_standard', 'Door hits door stopper at the steel part instead of the rubber part'),
    ('6f905df9', 'not_to_standard', 'B.I.C door stopper not installed'),
    ('4e65f3e9', 'not_to_standard', 'Clothing hanger inside B.I.C is not installed'),
    # LOUNGE (1)
    ('c4348cc6', 'not_installed', 'Wi-Fi Repeater not installed'),
]

dropped = [(t, c) for t, dt, c in defects if t in excluded_ids]
for t, c in dropped:
    print(f'DROPPING defect on excluded item {t}: {c}')
defects = [(t, dt, c) for t, dt, c in defects if t not in excluded_ids]
print(f'Defects after exclusion filter: {len(defects)}')

inspection_id = uuid.uuid4().hex[:8]
now = datetime.utcnow().isoformat()
cur.execute('''
    INSERT INTO inspection (id, tenant_id, unit_id, cycle_id, inspection_date,
                           inspector_id, inspector_name, status, submitted_at, updated_at, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?, ?)
''', (inspection_id, TENANT, unit_id, CYCLE_ID, INSPECTION_DATE,
      INSPECTOR_ID, INSPECTOR_NAME, now, now, now))
print(f'Inspection created: {inspection_id}')

# Build per-template-item info (handle multiple defects on same item)
template_defect_map = {}
for tmpl_id, defect_type, comment in defects:
    if tmpl_id not in template_defect_map:
        template_defect_map[tmpl_id] = {'status': defect_type, 'comments': [comment]}
    else:
        template_defect_map[tmpl_id]['comments'].append(comment)
        # NTS takes priority over N/I
        if defect_type == 'not_to_standard':
            template_defect_map[tmpl_id]['status'] = 'not_to_standard'

items_created = {'skipped': 0, 'ok': 0, 'nts': 0, 'ni': 0}

for tmpl_id in all_template_ids:
    item_id = uuid.uuid4().hex[:8]
    if tmpl_id in excluded_ids:
        status = 'skipped'
        comment = None
        items_created['skipped'] += 1
    elif tmpl_id in template_defect_map:
        info = template_defect_map[tmpl_id]
        status = info['status']
        comment = ' | '.join(info['comments'])
        if status == 'not_installed':
            items_created['ni'] += 1
        else:
            items_created['nts'] += 1
    else:
        status = 'ok'
        comment = None
        items_created['ok'] += 1
    cur.execute('''
        INSERT INTO inspection_item (id, tenant_id, inspection_id, item_template_id,
                                     status, comment, updated_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (item_id, TENANT, inspection_id, tmpl_id, status, comment, now, now))

print(f'Items: {items_created}')
print(f'Total items: {sum(items_created.values())}')

defect_count = 0
for tmpl_id, defect_type, comment in defects:
    defect_id = uuid.uuid4().hex[:8]
    cur.execute('''
        INSERT INTO defect (id, tenant_id, unit_id, item_template_id, raised_cycle_id,
                           defect_type, status, original_comment, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)
    ''', (defect_id, TENANT, unit_id, tmpl_id, CYCLE_ID,
          defect_type, comment, now, now))
    defect_count += 1
print(f'Defect records created: {defect_count}')

cur.execute('UPDATE unit SET status=? WHERE id=?', ('in_progress', unit_id))
conn.commit()

print()
print('=== VERIFICATION ===')
cur.execute('SELECT status FROM inspection WHERE id=?', (inspection_id,))
print(f'Inspection status: {cur.fetchone()[0]}')
cur.execute('SELECT status, COUNT(*) FROM inspection_item WHERE inspection_id=? GROUP BY status', (inspection_id,))
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')
cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=?', (inspection_id,))
print(f'  TOTAL: {cur.fetchone()[0]}')
cur.execute('SELECT COUNT(*) FROM defect WHERE unit_id=? AND status="open"', (unit_id,))
print(f'Open defects: {cur.fetchone()[0]}')
cur.execute('SELECT status FROM unit WHERE id=?', (unit_id,))
print(f'Unit status: {cur.fetchone()[0]}')
print()
print('=== DEFECTS BY AREA ===')
cur.execute('''
    SELECT at.area_name, COUNT(*)
    FROM defect d
    JOIN item_template it ON d.item_template_id = it.id
    JOIN category_template ct ON it.category_id = ct.id
    JOIN area_template at ON ct.area_id = at.id
    WHERE d.unit_id=? AND d.status='open'
    GROUP BY at.area_name
    ORDER BY at.area_name
''', (unit_id,))
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')
conn.close()
print()
print('DONE - Unit 030 imported successfully')
