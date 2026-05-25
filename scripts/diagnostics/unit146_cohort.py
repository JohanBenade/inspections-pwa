"""
Mirrors _desnag_progress() from app/routes/inspection.py L2793 exactly.
Target: unit 146 should return total=198 (matching PWA de-snag screen).
Run on Render console.
"""
import sqlite3

conn = sqlite3.connect('/var/data/inspections.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Step 1: Find unit 146
u = cur.execute(
    "SELECT id, unit_number FROM unit "
    "WHERE unit_number = '146' AND tenant_id = 'MONOGRAPH'"
).fetchone()

if not u:
    print('UNIT 146 NOT FOUND')
    raise SystemExit

uid = u['id']
print('UNIT 146 id:', uid)

# Step 2: Show all inspections for this unit
print('\nINSPECTIONS:')
rows = cur.execute(
    "SELECT id, cycle_number, status FROM inspection "
    "WHERE unit_id = ? AND tenant_id = 'MONOGRAPH' "
    "ORDER BY cycle_number",
    (uid,)
).fetchall()
for r in rows:
    print(' ', dict(r))

if not rows:
    print('NO INSPECTIONS FOR UNIT 146')
    raise SystemExit

# Step 3: Use highest cycle_number (current de-snag cycle)
cn = max(r['cycle_number'] for r in rows)
print('\nUsing cycle_number =', cn)

# Component 1: Defects
# (prior-cycle defects, either still open OR cleared this cycle)
d = cur.execute(
    "SELECT COUNT(*) as total, "
    "SUM(CASE WHEN addressed_cycle_number = ? THEN 1 ELSE 0 END) as addressed, "
    "SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as still_open, "
    "SUM(CASE WHEN status = 'cleared' AND cleared_cycle_number = ? THEN 1 ELSE 0 END) as cleared_now "
    "FROM defect "
    "WHERE unit_id = ? AND tenant_id = 'MONOGRAPH' "
    "AND raised_cycle_number < ? "
    "AND (status = 'open' OR (status = 'cleared' AND cleared_cycle_number = ?))",
    (cn, cn, uid, cn, cn)
).fetchone()
print('\nDEFECTS:', dict(d))

# Component 2: Latents
# (still open OR rectified this cycle)
l = cur.execute(
    "SELECT COUNT(*) as total, "
    "SUM(CASE WHEN addressed_cycle_number = ? THEN 1 ELSE 0 END) as addressed, "
    "SUM(CASE WHEN rectified_at IS NULL THEN 1 ELSE 0 END) as still_open, "
    "SUM(CASE WHEN rectified_at_cycle_number = ? THEN 1 ELSE 0 END) as cleared_now "
    "FROM latent_area_note "
    "WHERE unit_id = ? AND tenant_id = 'MONOGRAPH' "
    "AND (rectified_at IS NULL OR rectified_at_cycle_number = ?)",
    (cn, cn, uid, cn)
).fetchone()
print('LATENTS:', dict(l))

# Component 3: Newly-visible items at this cycle
# (not skipped, pending OR already marked this session, no prior defect)
i = cur.execute(
    "SELECT COUNT(*) as total, "
    "SUM(CASE WHEN ii.status != 'pending' AND ii.marked_at IS NOT NULL THEN 1 ELSE 0 END) as addressed "
    "FROM inspection_item ii "
    "JOIN inspection insp ON ii.inspection_id = insp.id "
    "WHERE insp.unit_id = ? AND insp.tenant_id = 'MONOGRAPH' "
    "AND insp.cycle_number = ? "
    "AND ii.status != 'skipped' "
    "AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL) "
    "AND COALESCE(ii.has_prior_defects, 0) = 0",
    (uid, cn)
).fetchone()
print('NEWLY-VISIBLE ITEMS:', dict(i))

# Roll-up
total = (d['total'] or 0) + (l['total'] or 0) + (i['total'] or 0)
addressed = (d['addressed'] or 0) + (l['addressed'] or 0) + (i['addressed'] or 0)
print(f'\nTOTAL COHORT: {total}   ADDRESSED: {addressed}')
print(f'PWA SHOWS:    198        0')
print(f'MATCH:        {total == 198}')

conn.close()
