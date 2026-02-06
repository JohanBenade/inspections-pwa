"""
Migration: Audit Trail Schema
Version: v63
Adds timestamp columns for complete audit trail tracking.
Safe to run multiple times - checks for existing columns before adding.
"""

import sqlite3
import os
import sys

DB_PATH = os.environ.get('DATABASE_PATH', '/var/data/inspections.db')

if not os.path.exists(DB_PATH):
    DB_PATH = 'instance/inspections.db'
    if not os.path.exists(DB_PATH):
        print(f'ERROR: Database not found at {DB_PATH}')
        sys.exit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()


def column_exists(table, column):
    cur.execute(f'PRAGMA table_info({table})')
    columns = [row[1] for row in cur.fetchall()]
    return column in columns


def table_exists(table):
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    return cur.fetchone() is not None


def add_column(table, column, col_type, default=None):
    if column_exists(table, column):
        print(f'  SKIP: {table}.{column} already exists')
        return False
    default_clause = f' DEFAULT {default}' if default is not None else ''
    cur.execute(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}')
    print(f'  ADDED: {table}.{column} ({col_type})')
    return True


print('=== AUDIT TRAIL MIGRATION ===')
print(f'Database: {DB_PATH}')
print()

print('1. inspection_cycle')
add_column('inspection_cycle', 'request_received_date', 'DATE')
add_column('inspection_cycle', 'started_at', 'TIMESTAMP')

print('2. inspection')
add_column('inspection', 'started_at', 'TIMESTAMP')
add_column('inspection', 'review_started_at', 'TIMESTAMP')
add_column('inspection', 'review_submitted_at', 'TIMESTAMP')
add_column('inspection', 'approved_at', 'TIMESTAMP')

print('3. inspection_item')
add_column('inspection_item', 'marked_at', 'TIMESTAMP')

print('4. unit')
add_column('unit', 'certified_at', 'TIMESTAMP')

print('5. audit_log')
if table_exists('audit_log'):
    print('  SKIP: audit_log table already exists')
else:
    cur.execute('''
        CREATE TABLE audit_log (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            action TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            user_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_audit_entity
        ON audit_log(entity_type, entity_id)
    ''')
    cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_audit_tenant
        ON audit_log(tenant_id, created_at)
    ''')
    cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_audit_user
        ON audit_log(user_id, created_at)
    ''')
    print('  CREATED: audit_log table + indexes')

conn.commit()
conn.close()

print()
print('=== MIGRATION COMPLETE ===')
