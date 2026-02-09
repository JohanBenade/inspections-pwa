"""Unit 099 Test Utility - Create or Remove"""
import sqlite3, uuid, sys
from datetime import datetime, timezone

DB = '/var/data/inspections.db'
TENANT = 'MONOGRAPH'
UNIT_ID = 'unit-test-099'
INSP_ID = 'insp-test-099'
CYCLE_ID = 'test-c1-099'

def create():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    cur.execute('SELECT id FROM inspection_cycle WHERE id=?', (CYCLE_ID,))
    if not cur.fetchone():
        cur.execute('INSERT INTO inspection_cycle (id,tenant_id,cycle_number,block,status,created_at,updated_at) VALUES (?,?,1,"Test","active",?,?)', (CYCLE_ID,TENANT,now,now))
        print('Created test cycle')
    else:
        print('Test cycle exists')

    cur.execute('SELECT id FROM unit WHERE id=?', (UNIT_ID,))
    if not cur.fetchone():
        cur.execute('INSERT INTO unit (id,tenant_id,unit_number,block,floor,status,created_at,updated_at) VALUES (?,?,"099","Test","1","not_started",?,?)', (UNIT_ID,TENANT,now,now))
        print('Created unit 099')
    else:
        print('Unit 099 exists')

    cur.execute('SELECT id FROM inspection WHERE id=?', (INSP_ID,))
    if not cur.fetchone():
        cur.execute('INSERT INTO inspection (id,tenant_id,unit_id,cycle_id,status,created_at,updated_at) VALUES (?,?,?,?,"not_started",?,?)', (INSP_ID,TENANT,UNIT_ID,CYCLE_ID,now,now))
        print('Created inspection')
    else:
        print('Inspection exists')

    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=?', (INSP_ID,))
    if cur.fetchone()[0] > 0:
        print('Items already exist')
    else:
        cur.execute('SELECT id FROM item_template WHERE tenant_id=?', (TENANT,))
        for t in cur.fetchall():
            cur.execute('INSERT INTO inspection_item (id,tenant_id,inspection_id,item_template_id,status,marked_at) VALUES (?,?,?,?,"pending",NULL)', (uuid.uuid4().hex[:8],TENANT,INSP_ID,t[0]))
        print('Created 523 inspection items (no exclusions)')

    print('\n=== VERIFY ===')
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status="pending"', (INSP_ID,))
    print(f'Pending: {cur.fetchone()[0]}')
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status="skipped"', (INSP_ID,))
    print(f'Skipped: {cur.fetchone()[0]}')
    cur.execute('SELECT COUNT(*) FROM defect WHERE unit_id=?', (UNIT_ID,))
    print(f'Defects: {cur.fetchone()[0]}')
    conn.commit()
    print('UNIT 099 READY')
    conn.close()

def remove():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('DELETE FROM defect WHERE unit_id=?', (UNIT_ID,))
    print(f'Defects: {cur.rowcount}')
    cur.execute('DELETE FROM inspection_item WHERE inspection_id=?', (INSP_ID,))
    print(f'Items: {cur.rowcount}')
    cur.execute('DELETE FROM cycle_unit_assignment WHERE unit_id=?', (UNIT_ID,))
    print(f'Assignments: {cur.rowcount}')
    cur.execute('DELETE FROM inspection WHERE id=?', (INSP_ID,))
    print(f'Inspection: {cur.rowcount}')
    cur.execute('DELETE FROM unit WHERE id=?', (UNIT_ID,))
    print(f'Unit: {cur.rowcount}')
    cur.execute('DELETE FROM inspection_cycle WHERE id=?', (CYCLE_ID,))
    print(f'Cycle: {cur.rowcount}')
    conn.commit()
    print('UNIT 099 REMOVED')
    conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in ('create','remove'):
        print('Usage: python3 scripts/test_unit_099.py create|remove')
        sys.exit(1)
    if sys.argv[1] == 'create':
        create()
    else:
        remove()
