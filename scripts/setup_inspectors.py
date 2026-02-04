#!/usr/bin/env python3
"""Set up real inspector records and fix Unit 027 inspector name."""
import sqlite3

conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()

# 1. Rename insp-001 from "Student One" to "Stemi Tumona"
cur.execute("UPDATE inspector SET name = 'Stemi Tumona' WHERE id = 'insp-001'")
print(f'Renamed insp-001 to Stemi Tumona: {cur.rowcount}')

# 2. Create new inspector records
new_inspectors = [
    ('insp-003', 'MONOGRAPH', 'Thebe Majodina', 'inspector'),
    ('insp-004', 'MONOGRAPH', 'Thembinkosi Biko', 'inspector'),
]
for insp_id, tenant, name, role in new_inspectors:
    cur.execute("SELECT id FROM inspector WHERE id = ?", [insp_id])
    if cur.fetchone():
        print(f'{insp_id} already exists, skipping')
    else:
        cur.execute("INSERT INTO inspector (id, tenant_id, name, role) VALUES (?, ?, ?, ?)",
            [insp_id, tenant, name, role])
        print(f'Created {insp_id}: {name}')

# 3. Fix Unit 027 inspection: update inspector_name
cur.execute("""
    UPDATE inspection SET inspector_name = 'Stemi Tumona', inspector_id = 'insp-001'
    WHERE id = '62b5db02'
""")
print(f'Fixed Unit 027 inspector_name: {cur.rowcount}')

# 4. Fix Unit 028 inspection: already set to Alex/team-lead, just verify
cur.execute("""
    SELECT inspector_id, inspector_name FROM inspection
    WHERE id = '1417446c'
""")
row = cur.fetchone()
print(f'Unit 028 inspector: {row[0]} / {row[1]}')

conn.commit()

# Verify all inspectors
print('\n=== INSPECTORS ===')
cur.execute("SELECT id, name, role FROM inspector WHERE tenant_id = 'MONOGRAPH' ORDER BY id")
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]} ({row[2]})')

conn.close()
print('\nDone!')
