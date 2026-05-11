"""
Migration: Add latent defect rectification tracking columns to latent_area_note.

Per HANDOVER_v289.md Section 6.2 (Step 6.5).
Enables Model A lifecycle: each note tracks its own rectification state.
NULL columns = outstanding. Populated columns = rectified.

Run on Render console:
    python3 /app/scripts/migrate_latent_rectification.py
"""
import sqlite3

def migrate():
    conn = sqlite3.connect('/var/data/inspections.db')
    cur = conn.cursor()

    print("=== MIGRATION: Latent Rectification Columns ===")
    print()

    existing = [r[1] for r in cur.execute('PRAGMA table_info(latent_area_note)').fetchall()]

    for col, col_type in [
        ('rectified_at_cycle_id', 'TEXT'),
        ('rectified_at_cycle_number', 'INTEGER'),
        ('rectified_at', 'TIMESTAMP'),
        ('rectified_by', 'TEXT'),
        ('rectified_by_role', 'TEXT'),
    ]:
        if col not in existing:
            cur.execute('ALTER TABLE latent_area_note ADD COLUMN {} {}'.format(col, col_type))
            print('Added: latent_area_note.{}'.format(col))
        else:
            print('Exists: latent_area_note.{}'.format(col))

    conn.commit()
    print()

    print("=== VERIFICATION ===")
    for col in [
        'rectified_at_cycle_id',
        'rectified_at_cycle_number',
        'rectified_at',
        'rectified_by',
        'rectified_by_role',
    ]:
        cur.execute("SELECT COUNT(*) FROM pragma_table_info('latent_area_note') WHERE name=?", (col,))
        found = cur.fetchone()[0]
        print('latent_area_note.{}: {}'.format(col, 'OK' if found else 'MISSING'))

    total = len(cur.execute('PRAGMA table_info(latent_area_note)').fetchall())
    print()
    print('Total columns in latent_area_note: {} (expected 20: 15 existing + 5 new)'.format(total))

    conn.close()
    print()
    print("MIGRATION COMPLETE")

if __name__ == '__main__':
    migrate()
