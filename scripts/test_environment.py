"""
Test Environment Setup/Teardown
Creates two isolated test cycles in Block A (no production contamination):
  1. Unit 027 Cycle 2 - carries forward Cycle 1 markings, no exclusions
  2. Unit 099 Cycle 1 - clean slate, all 523 items pending, no exclusions

Usage (Render console):
  python3 scripts/test_environment.py create
  python3 scripts/test_environment.py remove
  python3 scripts/test_environment.py status

Login URLs:
  Stemi:  /login?u=insp-001
  Alex:   /login?u=team-lead

Direct inspection URLs (after login):
  Unit 027 C2: /inspection/start/a407a9c4?cycle_id=test-c2-027
  Unit 099 C1: /inspection/start/unit-test-099?cycle_id=test-c1-099
"""
import sqlite3
import sys
from datetime import datetime, timezone

DB = '/var/data/inspections.db'
TENANT = 'MONOGRAPH'
PHASE_ID = 'phase-003'

# Test IDs - deterministic for reliable cleanup
UNIT_099_ID = 'unit-test-099'
CYCLE_C2_027_ID = 'test-c2-027'
CYCLE_C1_099_ID = 'test-c1-099'
CUA_027_ID = 'cua-test-027'
CUA_099_ID = 'cua-test-099'

# Production references (read-only)
UNIT_027_ID = 'a407a9c4'
STEMI_ID = 'insp-001'
CREATED_BY = 'insp-002'  # Kevin Coetzee


def create():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    print('=== TEST ENVIRONMENT CREATE ===')
    print()

    # --- 1. Safety: check for existing test data ---
    cur.execute('SELECT id FROM inspection_cycle WHERE id IN (?, ?)',
                (CYCLE_C2_027_ID, CYCLE_C1_099_ID))
    existing = cur.fetchall()
    if existing:
        print('ERROR: Test data already exists. Run "remove" first.')
        print(f'  Found cycles: {[r[0] for r in existing]}')
        conn.close()
        return

    # --- 2. Create Unit 099 ---
    cur.execute('SELECT id FROM unit WHERE id = ?', (UNIT_099_ID,))
    if cur.fetchone():
        print(f'Unit 099 already exists: {UNIT_099_ID}')
    else:
        cur.execute('''
            INSERT INTO unit (id, tenant_id, phase_id, unit_number, unit_type, block, floor, status)
            VALUES (?, ?, ?, '099', '4-Bed', 'A', 2, 'not_started')
        ''', (UNIT_099_ID, TENANT, PHASE_ID))
        print(f'Created Unit 099: {UNIT_099_ID} (Block A, Floor 2, 4-Bed)')

    # --- 3. Create test cycle for Unit 099 (Cycle 1) ---
    cur.execute('''
        INSERT INTO inspection_cycle
        (id, tenant_id, phase_id, cycle_number, block, floor, status, created_by, created_at)
        VALUES (?, ?, ?, 1, 'A', 2, 'active', ?, ?)
    ''', (CYCLE_C1_099_ID, TENANT, PHASE_ID, CREATED_BY, now))
    print(f'Created Cycle 1 for Unit 099: {CYCLE_C1_099_ID}')

    # --- 4. Create test cycle for Unit 027 (Cycle 2) ---
    cur.execute('''
        INSERT INTO inspection_cycle
        (id, tenant_id, phase_id, cycle_number, block, floor, status, created_by, created_at)
        VALUES (?, ?, ?, 2, 'A', 0, 'active', ?, ?)
    ''', (CYCLE_C2_027_ID, TENANT, PHASE_ID, CREATED_BY, now))
    print(f'Created Cycle 2 for Unit 027: {CYCLE_C2_027_ID}')

    # --- 5. Assign Stemi to both ---
    cur.execute('''
        INSERT INTO cycle_unit_assignment (id, tenant_id, cycle_id, unit_id, inspector_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (CUA_099_ID, TENANT, CYCLE_C1_099_ID, UNIT_099_ID, STEMI_ID, now))
    print(f'Assigned Stemi -> Unit 099 in Cycle 1')

    cur.execute('''
        INSERT INTO cycle_unit_assignment (id, tenant_id, cycle_id, unit_id, inspector_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (CUA_027_ID, TENANT, CYCLE_C2_027_ID, UNIT_027_ID, STEMI_ID, now))
    print(f'Assigned Stemi -> Unit 027 in Cycle 2')

    # --- 6. NO exclusions (cycle_excluded_item left empty) ---
    print('No exclusions created (both cycles have full 523 items)')

    # --- 7. NO inspections (Stemi creates via URL) ---
    print('No inspections created (Stemi starts via direct URL)')

    conn.commit()
    print()
    _print_status(cur)
    conn.close()


def remove():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    print('=== TEST ENVIRONMENT REMOVE ===')
    print()

    # Find all inspections in test cycles
    cur.execute('''
        SELECT id FROM inspection
        WHERE cycle_id IN (?, ?)
    ''', (CYCLE_C2_027_ID, CYCLE_C1_099_ID))
    test_inspections = [r[0] for r in cur.fetchall()]
    print(f'Test inspections found: {len(test_inspections)}')

    # 1. Delete defects raised in test cycles
    cur.execute('DELETE FROM defect WHERE raised_cycle_id IN (?, ?)',
                (CYCLE_C2_027_ID, CYCLE_C1_099_ID))
    print(f'Defects deleted: {cur.rowcount}')

    # 2. Delete inspection items for test inspections
    if test_inspections:
        placeholders = ','.join('?' * len(test_inspections))
        cur.execute(f'DELETE FROM inspection_item WHERE inspection_id IN ({placeholders})',
                    test_inspections)
        print(f'Inspection items deleted: {cur.rowcount}')
    else:
        print('Inspection items deleted: 0')

    # 3. Delete inspections in test cycles
    cur.execute('DELETE FROM inspection WHERE cycle_id IN (?, ?)',
                (CYCLE_C2_027_ID, CYCLE_C1_099_ID))
    print(f'Inspections deleted: {cur.rowcount}')

    # 4. Delete cycle_unit_assignments
    cur.execute('DELETE FROM cycle_unit_assignment WHERE cycle_id IN (?, ?)',
                (CYCLE_C2_027_ID, CYCLE_C1_099_ID))
    print(f'Assignments deleted: {cur.rowcount}')

    # 5. Delete test cycles
    cur.execute('DELETE FROM inspection_cycle WHERE id IN (?, ?)',
                (CYCLE_C2_027_ID, CYCLE_C1_099_ID))
    print(f'Cycles deleted: {cur.rowcount}')

    # 6. Delete Unit 099
    cur.execute('DELETE FROM unit WHERE id = ?', (UNIT_099_ID,))
    print(f'Unit 099 deleted: {cur.rowcount}')

    # 7. Restore Unit 027 status to in_progress (match Cycle 1 state)
    cur.execute("UPDATE unit SET status = 'in_progress' WHERE id = ?", (UNIT_027_ID,))
    print(f'Unit 027 status restored to in_progress')

    # 8. Clean up any audit trail entries for test data
    cur.execute('''
        DELETE FROM audit_log
        WHERE entity_id IN (?, ?)
        OR (entity_type = 'inspection' AND entity_id IN (
            SELECT id FROM inspection WHERE cycle_id IN (?, ?)
        ))
    ''', (CYCLE_C2_027_ID, CYCLE_C1_099_ID, CYCLE_C2_027_ID, CYCLE_C1_099_ID))
    # Ignore error if audit_log doesn't exist
    print(f'Audit entries cleaned: {cur.rowcount}')

    conn.commit()
    print()
    print('=== VERIFICATION ===')
    cur.execute('SELECT COUNT(*) FROM inspection_cycle WHERE id IN (?, ?)',
                (CYCLE_C2_027_ID, CYCLE_C1_099_ID))
    print(f'Test cycles remaining: {cur.fetchone()[0]} (expected 0)')
    cur.execute('SELECT COUNT(*) FROM unit WHERE id = ?', (UNIT_099_ID,))
    print(f'Unit 099 remaining: {cur.fetchone()[0]} (expected 0)')
    cur.execute('SELECT status FROM unit WHERE id = ?', (UNIT_027_ID,))
    print(f'Unit 027 status: {cur.fetchone()[0]} (expected in_progress)')
    cur.execute('SELECT COUNT(*) FROM defect WHERE status = "open" AND tenant_id = ?', (TENANT,))
    print(f'Total open defects: {cur.fetchone()[0]} (expected 861)')

    conn.close()
    print()
    print('TEST ENVIRONMENT REMOVED')


def status():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    _print_status(cur)
    conn.close()


def _print_status(cur):
    print('=== TEST ENVIRONMENT STATUS ===')
    print()

    # Test cycles
    for cid, label in [(CYCLE_C1_099_ID, 'Unit 099 C1'), (CYCLE_C2_027_ID, 'Unit 027 C2')]:
        cur.execute('SELECT status FROM inspection_cycle WHERE id = ?', (cid,))
        r = cur.fetchone()
        print(f'{label} cycle ({cid}): {r[0] if r else "NOT FOUND"}')

    # Unit 099
    cur.execute('SELECT status FROM unit WHERE id = ?', (UNIT_099_ID,))
    r = cur.fetchone()
    print(f'Unit 099: {r[0] if r else "NOT FOUND"}')

    # Assignments
    cur.execute('SELECT cycle_id, unit_id, inspector_id FROM cycle_unit_assignment WHERE cycle_id IN (?, ?)',
                (CYCLE_C1_099_ID, CYCLE_C2_027_ID))
    assignments = cur.fetchall()
    print(f'Assignments: {len(assignments)}')
    for a in assignments:
        print(f'  {a[0]} -> unit {a[1]} -> {a[2]}')

    # Inspections (created by Stemi via URL)
    cur.execute('''
        SELECT i.id, i.cycle_id, i.status, u.unit_number
        FROM inspection i JOIN unit u ON i.unit_id = u.id
        WHERE i.cycle_id IN (?, ?)
    ''', (CYCLE_C1_099_ID, CYCLE_C2_027_ID))
    inspections = cur.fetchall()
    print(f'Inspections: {len(inspections)}')
    for i in inspections:
        print(f'  {i[3]}: {i[2]} (cycle {i[1]})')

    # Defects in test cycles
    cur.execute('SELECT COUNT(*) FROM defect WHERE raised_cycle_id IN (?, ?)',
                (CYCLE_C1_099_ID, CYCLE_C2_027_ID))
    print(f'Test defects: {cur.fetchone()[0]}')

    # Exclusions (should be 0)
    cur.execute('SELECT COUNT(*) FROM cycle_excluded_item WHERE cycle_id IN (?, ?)',
                (CYCLE_C1_099_ID, CYCLE_C2_027_ID))
    print(f'Exclusions: {cur.fetchone()[0]} (expected 0)')

    print()
    print('LOGIN URLs:')
    print('  Stemi: https://inspections.archpractice.co.za/login?u=insp-001')
    print('  Alex:  https://inspections.archpractice.co.za/login?u=team-lead')
    print()
    print('INSPECTION URLs (use after login):')
    print('  Unit 027 C2: https://inspections.archpractice.co.za/inspection/start/a407a9c4?cycle_id=test-c2-027')
    print('  Unit 099 C1: https://inspections.archpractice.co.za/inspection/start/unit-test-099?cycle_id=test-c1-099')


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in ('create', 'remove', 'status'):
        print('Usage: python3 scripts/test_environment.py create|remove|status')
        sys.exit(1)

    action = sys.argv[1]
    if action == 'create':
        create()
    elif action == 'remove':
        remove()
    else:
        status()
