"""
Resolve the mismatch: PWA shows inspection ffa20626 for unit 146 C2,
but lookup by unit_number=146 returned a unit whose inspections only include C1.
Find ffa20626 directly, follow its unit_id, run cohort formula on the correct context.
"""
import sqlite3

conn = sqlite3.connect('/var/data/inspections.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Schema of inspection (columns we can rely on)
print('=== inspection columns ===')
for col in cur.execute("PRAGMA table_info(inspection)").fetchall():
    print(' ', col['name'])

# 2. Look up inspection ffa20626 directly (no other filters)
print('\n=== inspection ffa20626 ===')
insp = cur.execute(
    "SELECT * FROM inspection WHERE id LIKE 'ffa20626%'"
).fetchone()
if not insp:
    print('NOT FOUND')
    raise SystemExit
print(dict(insp))

# 3. Look up ALL unit records with unit_number=146 (no tenant filter)
print('\n=== ALL units where unit_number=146 ===')
for u in cur.execute("SELECT * FROM unit WHERE unit_number = '146'").fetchall():
    print(dict(u))

# 4. Show the unit that inspection ffa20626 actually points at
uid = insp['unit_id']
ten = insp['tenant_id']
cn = insp['cycle_number']
print(f'\n=== unit row for inspection ffa20626 (unit_id={uid}) ===')
u = cur.execute("SELECT * FROM unit WHERE id = ?", (uid,)).fetchone()
print(dict(u) if u else 'NO MATCHING UNIT ROW')

# 5. All inspections for that unit_id
print(f'\n=== all inspections for unit_id={uid} ===')
for r in cur.execute(
    "SELECT id, cycle_number, status, tenant_id FROM inspection "
    "WHERE unit_id = ? ORDER BY cycle_number",
    (uid,)
).fetchall():
    print(dict(r))

# 6. Run the _desnag_progress mirror with the CORRECT unit_id, tenant_id, cycle_number
print(f'\n=== _desnag_progress(unit_id={uid}, tenant={ten}, cycle={cn}) ===')

d = cur.execute(
    "SELECT COUNT(*) as total, "
    "SUM(CASE WHEN addressed_cycle_number = ? THEN 1 ELSE 0 END) as addressed, "
    "SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as still_open, "
    "SUM(CASE WHEN status = 'cleared' AND cleared_cycle_number = ? THEN 1 ELSE 0 END) as cleared_now "
    "FROM defect "
    "WHERE unit_id = ? AND tenant_id = ? "
    "AND raised_cycle_number < ? "
    "AND (status = 'open' OR (status = 'cleared' AND cleared_cycle_number = ?))",
    (cn, cn, uid, ten, cn, cn)
).fetchone()
print('DEFECTS:', dict(d))

l = cur.execute(
    "SELECT COUNT(*) as total, "
    "SUM(CASE WHEN addressed_cycle_number = ? THEN 1 ELSE 0 END) as addressed, "
    "SUM(CASE WHEN rectified_at IS NULL THEN 1 ELSE 0 END) as still_open, "
    "SUM(CASE WHEN rectified_at_cycle_number = ? THEN 1 ELSE 0 END) as cleared_now "
    "FROM latent_area_note "
    "WHERE unit_id = ? AND tenant_id = ? "
    "AND (rectified_at IS NULL OR rectified_at_cycle_number = ?)",
    (cn, cn, uid, ten, cn)
).fetchone()
print('LATENTS:', dict(l))

i = cur.execute(
    "SELECT COUNT(*) as total, "
    "SUM(CASE WHEN ii.status != 'pending' AND ii.marked_at IS NOT NULL THEN 1 ELSE 0 END) as addressed "
    "FROM inspection_item ii "
    "JOIN inspection insp ON ii.inspection_id = insp.id "
    "WHERE insp.unit_id = ? AND insp.tenant_id = ? AND insp.cycle_number = ? "
    "AND ii.status != 'skipped' "
    "AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL) "
    "AND COALESCE(ii.has_prior_defects, 0) = 0",
    (uid, ten, cn)
).fetchone()
print('NEWLY-VISIBLE ITEMS:', dict(i))

total = (d['total'] or 0) + (l['total'] or 0) + (i['total'] or 0)
addressed = (d['addressed'] or 0) + (l['addressed'] or 0) + (i['addressed'] or 0)
print(f'\nTOTAL COHORT: {total}   ADDRESSED: {addressed}')
print(f'PWA SHOWS:    198        0')
print(f'MATCH:        {total == 198}')

conn.close()
