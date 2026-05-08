#!/usr/bin/env python3
"""
Migration: Add latent_area_note and latent_photo tables.
Step 1 of latent-defect feature build.

Run on Render console:
    python3 /tmp/migration_latent_defects.py

Reversible:
    DROP TABLE latent_photo;
    DROP TABLE latent_area_note;
"""
import sqlite3
import sys

DB_PATH = '/var/data/inspections.db'

CREATE_LATENT_AREA_NOTE = """
CREATE TABLE IF NOT EXISTS latent_area_note (
    id                    TEXT PRIMARY KEY,
    tenant_id             TEXT NOT NULL,
    inspection_id         TEXT NOT NULL,
    unit_id               TEXT NOT NULL,
    cycle_id              TEXT NOT NULL,
    cycle_number          INTEGER NOT NULL,
    area_template_id      TEXT,
    area_name_override    TEXT,
    note_html             TEXT NOT NULL,
    created_by            TEXT NOT NULL,
    created_by_role       TEXT NOT NULL,
    created_at            TIMESTAMP NOT NULL,
    last_edited_by        TEXT,
    last_edited_by_role   TEXT,
    last_edited_at        TIMESTAMP,
    FOREIGN KEY (inspection_id) REFERENCES inspection(id),
    FOREIGN KEY (unit_id) REFERENCES unit(id),
    FOREIGN KEY (area_template_id) REFERENCES area_template(id),
    CHECK (area_template_id IS NOT NULL OR area_name_override IS NOT NULL),
    CHECK (created_by_role IN ('inspector', 'team_lead', 'manager'))
);
"""

CREATE_LATENT_PHOTO = """
CREATE TABLE IF NOT EXISTS latent_photo (
    id                    TEXT PRIMARY KEY,
    tenant_id             TEXT NOT NULL,
    latent_area_note_id   TEXT NOT NULL,
    file_path             TEXT NOT NULL,
    mime_type             TEXT NOT NULL,
    file_size             INTEGER NOT NULL,
    original_filename     TEXT,
    display_order         INTEGER NOT NULL DEFAULT 0,
    uploaded_by           TEXT NOT NULL,
    uploaded_at           TIMESTAMP NOT NULL,
    FOREIGN KEY (latent_area_note_id) REFERENCES latent_area_note(id) ON DELETE CASCADE
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_latent_area_note_inspection ON latent_area_note (inspection_id, area_template_id);",
    "CREATE INDEX IF NOT EXISTS idx_latent_area_note_unit      ON latent_area_note (unit_id, cycle_id);",
    "CREATE INDEX IF NOT EXISTS idx_latent_area_note_tenant    ON latent_area_note (tenant_id);",
    "CREATE INDEX IF NOT EXISTS idx_latent_photo_note          ON latent_photo (latent_area_note_id, display_order);",
    "CREATE INDEX IF NOT EXISTS idx_latent_photo_tenant        ON latent_photo (tenant_id);",
]


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Pre-flight: abort if tables already exist
    existing = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name IN ('latent_area_note', 'latent_photo')"
    )]
    if existing:
        print('ABORT: tables already exist: {}'.format(existing))
        print('To rollback first: DROP TABLE latent_photo; DROP TABLE latent_area_note;')
        conn.close()
        sys.exit(1)

    # Create tables
    cur.executescript(CREATE_LATENT_AREA_NOTE)
    cur.executescript(CREATE_LATENT_PHOTO)

    # Create indexes
    for ix in INDEXES:
        cur.execute(ix)

    conn.commit()

    # Verify
    print('=== latent_area_note schema ===')
    for r in cur.execute('PRAGMA table_info(latent_area_note)'):
        print(r)

    print('')
    print('=== latent_photo schema ===')
    for r in cur.execute('PRAGMA table_info(latent_photo)'):
        print(r)

    print('')
    print('=== indexes ===')
    for r in cur.execute(
        "SELECT name, tbl_name FROM sqlite_master WHERE type='index' "
        "AND tbl_name IN ('latent_area_note', 'latent_photo') "
        "AND name NOT LIKE 'sqlite_%' ORDER BY tbl_name, name"
    ):
        print(r)

    print('')
    print('Migration complete.')
    conn.close()


if __name__ == '__main__':
    main()
