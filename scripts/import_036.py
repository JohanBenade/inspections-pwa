import sqlite3, uuid
from datetime import datetime

conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()

UNIT_NUMBER = '036'
INSPECTOR_ID = 'insp-003'
INSPECTOR_NAME = 'Thebe Majodina'
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

defects = [
    # KITCHEN (10 - 2 will be dropped)
    ('c897b472', 'not_to_standard', 'Finish has scratches'),
    ('244e8c43', 'not_installed', 'Door has no thumb turn'),
    ('485aba2b', 'not_to_standard', 'Tile trim at sink splash back does not reach the eye level pack'),
    ('cbaefabd', 'not_to_standard', 'Glass needs to be cleaned'),
    ('707304a2', 'not_to_standard', 'Glass needs to be cleaned'),
    ('522b4aeb', 'not_to_standard', 'Broken tiles at the doorstep'),
    ('7414ad92', 'not_to_standard', 'DB cover needs to be cleaned'),
    ('445ab368', 'not_to_standard', 'Runners have sand'),
    ('3738af64', 'not_to_standard', 'Locks are installed upside down'),
    ('218f3d5a', 'not_to_standard', 'Locks are installed upside down'),
    # BATHROOM (4)
    ('4abe1624', 'not_to_standard', 'Airbrick finish is dirty'),
    ('852c37b8', 'not_to_standard', 'Mosaic tiles have plaster and paint splashes'),
    ('8667f32c', 'not_to_standard', 'WC has sand inside'),
    ('b9805e6c', 'not_to_standard', 'WC shut off valve is not working'),
    # BEDROOM A (2)
    ('110e7bcc', 'not_to_standard', 'Ceiling mounted light cover needs to be cleaned'),
    ('03e99050', 'not_to_standard', 'Study desk missing 1 screw to wall'),
    # BEDROOM B (1)
    ('5d1dc2bd', 'not_to_standard', 'Study desk missing 1 screw to wall'),
    # BEDROOM C (4)
    ('c2e3219c', 'not_to_standard', 'Handle has grey paint smudge'),
    ('6bc58353', 'not_to_standard', 'Paint on outside has white gaps'),
    ('f42cffed', 'not_to_standard', 'Study desk missing 1 screw to wall'),
    # BEDROOM D (1)
    ('b38587a1', 'not_to_standard', 'Study desk missing 1 screw to wall'),
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

template_defect_map = {}
for tmpl_id, defect_type, comment in defects:
    if tmpl_id not in template_defect_map:
        template_defect_map[tmpl_id] = {'status': defect_type, 'comments': [comment]}
    else:
        template_defect_map[tmpl_id]['comments'].append(comment)
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
print('DONE - Unit 036 imported successfully')
