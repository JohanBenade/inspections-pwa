"""
Verify audit trail migration completed successfully.
"""

import sqlite3
import os
import sys

DB_PATH = os.environ.get('DATABASE_PATH', '/var/data/inspections.db')

if not os.path.exists(DB_PATH):
    DB_PATH = 'instance/inspections.db'
    if not os.path.exists(DB_PATH):
        print(f'ERROR: Database not found')
        sys.exit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print('=== AUDIT TRAIL MIGRATION VERIFICATION ===')
print()

errors = 0

checks = [
    ('inspection_cycle', 'request_received_date'),
    ('inspection_cycle', 'started_at'),
    ('inspection', 'started_at'),
    ('inspection', 'review_started_at'),
    ('inspection', 'review_submitted_at'),
    ('inspection', 'approved_at'),
    ('inspection_item', 'marked_at'),
    ('unit', 'certified_at'),
]

for table, column in checks:
    cur.execute(f'PRAGMA table_info({table})')
    columns = [row[1] for row in cur.fetchall()]
    if column in columns:
        print(f'  OK: {table}.{column}')
    else:
        print(f'  FAIL: {table}.{column} MISSING')
        errors += 1

print()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
if cur.fetchone():
    print('  OK: audit_log table exists')
    cur.execute('PRAGMA table_info(audit_log)')
    cols = [row[1] for row in cur.fetchall()]
    expected = ['id', 'tenant_id', 'entity_type', 'entity_id', 'action',
                'old_value', 'new_value', 'user_id', 'user_name', 'metadata', 'created_at']
    for col in expected:
        if col in cols:
            print(f'    OK: audit_log.{col}')
        else:
            print(f'    FAIL: audit_log.{col} MISSING')
            errors += 1

    cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='audit_log'")
    indexes = [row[0] for row in cur.fetchall()]
    for idx in ['idx_audit_entity', 'idx_audit_tenant', 'idx_audit_user']:
        if idx in indexes:
            print(f'    OK: index {idx}')
        else:
            print(f'    FAIL: index {idx} MISSING')
            errors += 1
else:
    print('  FAIL: audit_log table MISSING')
    errors += 1

print()
print('=== EXISTING DATA CHECK ===')
cur.execute('SELECT COUNT(*) FROM inspection')
print(f'  Inspections: {cur.fetchone()[0]}')
cur.execute('SELECT COUNT(*) FROM inspection_item')
print(f'  Inspection items: {cur.fetchone()[0]}')
cur.execute('SELECT COUNT(*) FROM inspection_cycle')
print(f'  Cycles: {cur.fetchone()[0]}')
cur.execute('SELECT COUNT(*) FROM unit WHERE tenant_id="MONOGRAPH"')
print(f'  Units: {cur.fetchone()[0]}')
cur.execute('SELECT COUNT(*) FROM audit_log')
print(f'  Audit log entries: {cur.fetchone()[0]}')

print()
if errors == 0:
    print('=== ALL CHECKS PASSED ===')
else:
    print(f'=== {errors} CHECK(S) FAILED ===')

conn.close()
