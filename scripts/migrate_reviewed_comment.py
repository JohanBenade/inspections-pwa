"""
Migration: Add reviewed_comment column to defect table.
Supports manager review workflow - Kevin's cleaned descriptions.
original_comment remains untouched (audit trail).
reviewed_comment is NULL until Kevin edits during review.
All downstream reads use COALESCE(reviewed_comment, original_comment).
"""
import sqlite3
import os

DB_PATH = os.environ.get('DATABASE_PATH', '/var/data/inspections.db')


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Check if column already exists
    cur.execute("PRAGMA table_info(defect)")
    columns = [row[1] for row in cur.fetchall()]

    if 'reviewed_comment' in columns:
        print('Column reviewed_comment already exists. No migration needed.')
        conn.close()
        return

    # Add column
    cur.execute("ALTER TABLE defect ADD COLUMN reviewed_comment TEXT DEFAULT NULL")
    print('Added reviewed_comment column to defect table.')

    # Verify
    cur.execute("PRAGMA table_info(defect)")
    columns = [row[1] for row in cur.fetchall()]
    assert 'reviewed_comment' in columns, 'Migration failed - column not found'
    print(f'Verified: defect table now has {len(columns)} columns.')

    # Check no data corruption
    cur.execute('SELECT COUNT(*) FROM defect WHERE tenant_id = "MONOGRAPH"')
    total = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM defect WHERE reviewed_comment IS NOT NULL')
    reviewed = cur.fetchone()[0]
    print(f'Total defects: {total}')
    print(f'With reviewed_comment: {reviewed} (expected 0)')

    conn.commit()
    conn.close()
    print('Migration complete.')


if __name__ == '__main__':
    migrate()
