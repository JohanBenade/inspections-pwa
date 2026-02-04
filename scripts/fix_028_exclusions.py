#!/usr/bin/env python3
"""Fix Unit 028: Revert 2 excluded items from NTS back to skipped, remove 3 defects."""
import sqlite3

conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()

cur.execute("""
    SELECT i.id FROM inspection i
    JOIN unit u ON i.unit_id = u.id
    WHERE u.unit_number = '028' AND u.tenant_id = 'MONOGRAPH'
""")
row = cur.fetchone()
if not row:
    print('No inspection found for Unit 028!')
    exit()
insp_id = row[0]
print(f'Inspection: {insp_id}')

excluded_items = ['c897b472', '244e8c43']

for tmpl_id in excluded_items:
    cur.execute("""
        UPDATE inspection_item SET status = 'skipped', comment = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE inspection_id = ? AND item_template_id = ?
    """, [insp_id, tmpl_id])
    print(f'  Reverted {tmpl_id} to skipped: {cur.rowcount}')

cur.execute("SELECT id FROM unit WHERE unit_number = '028' AND tenant_id = 'MONOGRAPH'")
unit_id = cur.fetchone()[0]

for tmpl_id in excluded_items:
    cur.execute("DELETE FROM defect WHERE unit_id = ? AND item_template_id = ?", [unit_id, tmpl_id])
    print(f'  Deleted defects for {tmpl_id}: {cur.rowcount}')

conn.commit()

cur.execute("SELECT status, COUNT(*) FROM inspection_item WHERE inspection_id = ? GROUP BY status ORDER BY status", [insp_id])
print('\nFinal item breakdown:')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

cur.execute("SELECT COUNT(*) FROM defect WHERE unit_id = ?", [unit_id])
print(f'Total defects: {cur.fetchone()[0]}')

conn.close()
print('Done!')
