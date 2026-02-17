"""
Migration: Add manager review tracking to inspection table
and cycle-level approval tracking to inspection_cycle table.

Run on Render console:
    python3 /app/scripts/migrate_manager_review.py
"""
import sqlite3

def migrate():
    conn = sqlite3.connect('/var/data/inspections.db')
    cur = conn.cursor()

    print("=== MIGRATION: Manager Review + Cycle Approval ===")
    print()

    # --- 1. Add manager_reviewed_at and manager_reviewed_by to inspection ---
    existing = [r[1] for r in cur.execute('PRAGMA table_info(inspection)').fetchall()]

    if 'manager_reviewed_at' not in existing:
        cur.execute('ALTER TABLE inspection ADD COLUMN manager_reviewed_at TIMESTAMP')
        print('Added: inspection.manager_reviewed_at')
    else:
        print('Exists: inspection.manager_reviewed_at')

    if 'manager_reviewed_by' not in existing:
        cur.execute('ALTER TABLE inspection ADD COLUMN manager_reviewed_by TEXT')
        print('Added: inspection.manager_reviewed_by')
    else:
        print('Exists: inspection.manager_reviewed_by')

    # --- 2. Add cycle-level approval columns to inspection_cycle ---
    existing_ic = [r[1] for r in cur.execute('PRAGMA table_info(inspection_cycle)').fetchall()]

    for col, col_type in [
        ('approved_at', 'TIMESTAMP'),
        ('approved_by', 'TEXT'),
        ('pdfs_pushed_at', 'TIMESTAMP'),
        ('pdfs_push_status', 'TEXT'),
    ]:
        if col not in existing_ic:
            cur.execute('ALTER TABLE inspection_cycle ADD COLUMN {} {}'.format(col, col_type))
            print('Added: inspection_cycle.{}'.format(col))
        else:
            print('Exists: inspection_cycle.{}'.format(col))

    conn.commit()
    print()

    # --- 3. Verify ---
    print("=== VERIFICATION ===")
    for col in ['manager_reviewed_at', 'manager_reviewed_by']:
        cur.execute("SELECT COUNT(*) FROM pragma_table_info('inspection') WHERE name=?", (col,))
        found = cur.fetchone()[0]
        print('inspection.{}: {}'.format(col, 'OK' if found else 'MISSING'))

    for col in ['approved_at', 'approved_by', 'pdfs_pushed_at', 'pdfs_push_status']:
        cur.execute("SELECT COUNT(*) FROM pragma_table_info('inspection_cycle') WHERE name=?", (col,))
        found = cur.fetchone()[0]
        print('inspection_cycle.{}: {}'.format(col, 'OK' if found else 'MISSING'))

    conn.close()
    print()
    print("MIGRATION COMPLETE")

if __name__ == '__main__':
    migrate()
