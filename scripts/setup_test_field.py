import sqlite3, uuid
from datetime import datetime, timezone

conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()
now = datetime.now(timezone.utc).isoformat()
T = 'MONOGRAPH'

# 1. Create inspectors
for iid, name in [('insp-ruan', 'Ruan Marsh'), ('insp-benard', 'Benard Maree')]:
    cur.execute('SELECT id FROM inspector WHERE id=? AND tenant_id=?', (iid, T))
    if not cur.fetchone():
        cur.execute("INSERT INTO inspector (id, tenant_id, name, email, role, active, created_at) VALUES (?, ?, ?, '', 'inspector', 1, ?)", (iid, T, name, now))
        print(f'Created: {iid} ({name})')

# 2. Create 5 test units
unit_ids = {}
for unum in ['TEST-001','TEST-002','TEST-003','TEST-004','TEST-005']:
    cur.execute('SELECT id FROM unit WHERE unit_number=? AND tenant_id=?', (unum, T))
    row = cur.fetchone()
    if row:
        unit_ids[unum] = row[0]
    else:
        uid = uuid.uuid4().hex[:8]
        cur.execute("INSERT INTO unit (id, tenant_id, unit_number, block, floor, phase_id, unit_type, status) VALUES (?, ?, ?, 'Test Block', 0, 'phase-003', 'Standard', 'not_started')", (uid, T, unum))
        unit_ids[unum] = uid
        print(f'Unit: {unum} ({uid})')

# 3. Create test cycle
tc = 'test-field-001'
cur.execute('SELECT id FROM inspection_cycle WHERE id=?', (tc,))
if not cur.fetchone():
    cur.execute("INSERT INTO inspection_cycle (id, tenant_id, phase_id, cycle_number, block, floor, unit_start, unit_end, status, created_by, created_at) VALUES (?, ?, 'phase-003', 1, 'Test Block', 0, 'TEST-001', 'TEST-005', 'active', 'admin', ?)", (tc, T, now))
    print(f'Cycle: {tc}')

# 4. Get Kitchen + Bathroom templates
cur.execute("SELECT it.id FROM item_template it JOIN category_template ct ON it.category_id = ct.id JOIN area_template at2 ON ct.area_id = at2.id WHERE it.tenant_id = ? AND at2.area_name IN ('KITCHEN', 'BATHROOM')", (T,))
templates = [r[0] for r in cur.fetchall()]
print(f'Templates: {len(templates)}')

# 5. Create inspections
for unum, iid, name in [('TEST-001','admin','Johan Benade'),('TEST-002','insp-002','Kevin Coetzee'),('TEST-003','insp-ruan','Ruan Marsh'),('TEST-004','team-lead','Alex Nataniel'),('TEST-005','insp-benard','Benard Maree')]:
    uid = unit_ids[unum]
    cur.execute('SELECT id FROM inspection WHERE unit_id=? AND cycle_id=?', (uid, tc))
    if cur.fetchone():
        print(f'{unum}: exists')
        continue
    insp = uuid.uuid4().hex[:8]
    cur.execute("INSERT INTO inspection (id, tenant_id, unit_id, cycle_id, inspection_date, inspector_id, inspector_name, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'not_started', ?)", (insp, T, uid, tc, now[:10], iid, name, now))
    for tmpl in templates:
        cur.execute("INSERT INTO inspection_item (id, tenant_id, inspection_id, item_template_id, status, marked_at) VALUES (?, ?, ?, ?, 'pending', NULL)", (uuid.uuid4().hex[:8], T, insp, tmpl))
    print(f'{unum}: {name} ({len(templates)} items)')

conn.commit()
# Verify
cur.execute("SELECT i.inspector_name, u.unit_number, (SELECT COUNT(*) FROM inspection_item ii WHERE ii.inspection_id = i.id) FROM inspection i JOIN unit u ON i.unit_id = u.id WHERE i.cycle_id=? ORDER BY u.unit_number", (tc,))
print('\n=== RESULT ===')
for r in cur.fetchall():
    print(f'  {r[1]}: {r[0]} ({r[2]} items)')
conn.close()
