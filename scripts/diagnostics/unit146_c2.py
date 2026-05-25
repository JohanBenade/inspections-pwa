"""
Run _desnag_progress formula directly for unit 146, cycle 2.
unit_id is known from prior diagnostic: d41d75d0
"""
import sqlite3

conn = sqlite3.connect('/var/data/inspections.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

uid = 'd41d75d0'
ten = 'MONOGRAPH'
cn = 2

d = cur.execute(
    "SELECT COUNT(*) as n FROM defect "
    "WHERE unit_id = ? AND tenant_id = ? "
    "AND raised_cycle_number < ? "
    "AND (status = 'open' OR (status = 'cleared' AND cleared_cycle_number = ?))",
    (uid, ten, cn, cn)
).fetchone()['n']

l = cur.execute(
    "SELECT COUNT(*) as n FROM latent_area_note "
    "WHERE unit_id = ? AND tenant_id = ? "
    "AND (rectified_at IS NULL OR rectified_at_cycle_number = ?)",
    (uid, ten, cn)
).fetchone()['n']

i = cur.execute(
    "SELECT COUNT(*) as n FROM inspection_item ii "
    "JOIN inspection insp ON ii.inspection_id = insp.id "
    "WHERE insp.unit_id = ? AND insp.tenant_id = ? AND insp.cycle_number = ? "
    "AND ii.status != 'skipped' "
    "AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL) "
    "AND COALESCE(ii.has_prior_defects, 0) = 0",
    (uid, ten, cn)
).fetchone()['n']

print(f'defects:  {d}')
print(f'latents:  {l}')
print(f'items:    {i}')
print(f'TOTAL:    {d+l+i}')
print(f'PWA:      198')
print(f'MATCH:    {d+l+i == 198}')

conn.close()
