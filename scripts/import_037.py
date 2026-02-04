import sqlite3, uuid
from datetime import datetime

conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()

UNIT_NUMBER = '037'
INSPECTOR_ID = 'team-lead'
INSPECTOR_NAME = 'Alex Nataniel'
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
    # KITCHEN (8 - 3 will be dropped)
    ('c897b472', 'not_to_standard', 'Paint is damaged as indicated'),
    ('c897b472', 'not_to_standard', 'Has paint marks as indicated'),
    ('244e8c43', 'not_installed', 'Thumb turn not installed'),
    ('522b4aeb', 'not_to_standard', 'Broken tiles as indicated'),
    ('522b4aeb', 'not_to_standard', 'Chipped tiles as indicated'),
    ('624544cd', 'not_to_standard', 'No screw covers'),
    ('b2209272', 'not_to_standard', 'Board is chipped as indicated'),
    ('5fe88982', 'not_to_standard', 'Leg support is loose'),
    # BEDROOM A (5 - 2 pairs on same items)
    ('04796e27', 'not_to_standard', 'Has paint droplets'),
    ('04796e27', 'not_to_standard', 'Chipped edge at the bottom as indicated'),
    ('afcc1bc2', 'not_to_standard', 'Has paint overlaps'),
    ('01a96116', 'not_to_standard', 'Peeling paint as indicated'),
    ('e6f434e1', 'not_to_standard', 'Bad plaster work around window'),
    # BEDROOM B (2)
    ('340d94a3', 'not_to_standard', 'Damaged paint as indicated'),
    ('2ed16ab7', 'not_to_standard', 'Chipped tile as indicated'),
    # BEDROOM C (4)
    ('80177e8e', 'not_to_standard', 'Chipped at the bottom as indicated'),
    ('9fdcd89e', 'not_to_standard', 'Damaged paint as indicated'),
    ('5628303a', 'not_to_standard', 'Orchid bay paint is peeling off as indicated'),
    ('e3f789d6', 'not_to_standard', 'Inconsistent colouring near light'),
    # BEDROOM D (3 - door has 2 defects)
    ('212d83e1', 'not_to_standard', 'Inconsistent paint application'),
    ('212d83e1', 'not_to_standard', 'Chipped edge as indicated'),
    ('66cc0d36', 'not_to_standard', 'Damaged paint as indicated'),
    # BATHROOM (4)
    ('b6b5d166', 'not_to_standard', 'Chipped edge as indicated'),
    ('e326b993', 'not_to_standard', 'Damaged paint as indicated'),
    ('df84942f', 'not_to_standard', 'Tile trim on duct wall corner does not have sufficient grout'),
    ('ef937d8f', 'not_to_standard', 'Chipped tile as indicated'),
    # LOUNGE (1)
    ('c4348cc6', 'not_installed', 'Wi-Fi repeater not installed'),
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
print('DONE - Unit 037 imported successfully')
