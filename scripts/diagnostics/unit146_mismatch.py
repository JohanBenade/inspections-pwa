"""
Hypothesis: items in the 'ITEMS TO INSPECT' section show 'Defects Remain' only
because has_prior_defects column = 0 (so show_prior block doesn't render),
but a defect with status='open' DOES exist for the same template_id (so branch 2
fires via has_open_prior=True at view time).

Find unit 146's current C2 inspection, look for inspection_item rows where:
  - has_prior_defects = 0 (or NULL)
  - AND an open prior defect exists for the same item_template_id
That's the mismatch.
"""
import sqlite3

conn = sqlite3.connect('/var/data/inspections.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

UID = 'd41d75d0'
TEN = 'MONOGRAPH'

# Find the current C2 inspection for unit 146
insp = cur.execute(
    "SELECT id, cycle_id, cycle_number, status FROM inspection "
    "WHERE unit_id = ? AND tenant_id = ? AND cycle_number = 2 "
    "ORDER BY rowid DESC LIMIT 1", (UID, TEN)
).fetchone()
if not insp:
    print('No C2 inspection found for unit 146.')
    raise SystemExit
print(f'C2 inspection: id={insp["id"]}, cycle_id={insp["cycle_id"]}, status={insp["status"]}')

iid = insp['id']
cid = insp['cycle_id']

# Defect counts for unit 146 (by raised_cycle_id state)
print('\n--- defect rows for unit 146 ---')
for r in cur.execute(
    "SELECT status, "
    "       SUM(CASE WHEN raised_cycle_id IS NULL THEN 1 ELSE 0 END) AS null_cycle, "
    "       SUM(CASE WHEN raised_cycle_id = ? THEN 1 ELSE 0 END) AS this_cycle, "
    "       SUM(CASE WHEN raised_cycle_id IS NOT NULL AND raised_cycle_id != ? THEN 1 ELSE 0 END) AS prior_cycle "
    "FROM defect WHERE unit_id = ? AND tenant_id = ? GROUP BY status",
    (cid, cid, UID, TEN)
).fetchall():
    print(' ', dict(r))

# inspection_item rows for this C2 inspection, summary by has_prior_defects
print('\n--- inspection_item.has_prior_defects distribution (this C2 inspection) ---')
for r in cur.execute(
    "SELECT COALESCE(has_prior_defects, 0) AS hpd, status, COUNT(*) AS n "
    "FROM inspection_item WHERE inspection_id = ? "
    "GROUP BY hpd, status ORDER BY hpd, status", (iid,)
).fetchall():
    print(' ', dict(r))

# The mismatch: has_prior_defects=0 but an open prior defect exists
mismatches = cur.execute(
    "SELECT ii.id, ii.item_template_id, ii.status, "
    "       COALESCE(ii.has_prior_defects, 0) AS hpd, "
    "       (SELECT COUNT(*) FROM defect d "
    "         WHERE d.unit_id = ? AND d.tenant_id = ? "
    "           AND d.item_template_id = ii.item_template_id "
    "           AND d.raised_cycle_id != ? AND d.status = 'open') AS open_prior "
    "FROM inspection_item ii "
    "WHERE ii.inspection_id = ? "
    "  AND COALESCE(ii.has_prior_defects, 0) = 0 "
    "  AND EXISTS ("
    "    SELECT 1 FROM defect d "
    "    WHERE d.unit_id = ? AND d.tenant_id = ? "
    "      AND d.item_template_id = ii.item_template_id "
    "      AND d.raised_cycle_id != ? AND d.status = 'open'"
    "  )", (UID, TEN, cid, iid, UID, TEN, cid)
).fetchall()

print(f'\n=== MISMATCHED rows: {len(mismatches)} ===')
for r in mismatches[:10]:
    print(' ', dict(r))

# Also check the NULL raised_cycle_id case (defects that BOTH the UPDATE and L514 query would miss)
null_cyc = cur.execute(
    "SELECT COUNT(*) AS n FROM defect "
    "WHERE unit_id = ? AND tenant_id = ? AND raised_cycle_id IS NULL AND status = 'open'",
    (UID, TEN)
).fetchone()['n']
print(f'\nDefects with NULL raised_cycle_id (status=open): {null_cyc}')

conn.close()
