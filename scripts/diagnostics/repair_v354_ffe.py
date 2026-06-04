#!/usr/bin/env python3
"""
v354 DATA REPAIR -- SR-019 bedroom FF&E variant-3.
Flip the 1,716 born-skipped, NULL-reason bedroom FF&E inspection_item rows
(latest cycle per unit) from 'skipped' -> 'pending' so inspectors see them.

Mirrors repair_v353_hidepath.py structure:
  - backs up every mutated row to v354_repair_backup BEFORE writing
  - DRY=True by default (prints, does not commit)
  - assert-guarded count gate

Scope (proven 3x this thread, all reason=NULL):
  batch SR-019 (5bc63a1e), 44 bedroom FF&E templates, latest cycle per unit,
  status='skipped'. Expected exactly 1716 items / 62 units.

If any of these are 'submitted' inspections, reopen them (mirror v353 1b):
  status->'in_progress', submitted_at->NULL.

RUN ON: RENDER
"""
import sqlite3, datetime

DRY = False   # <<< flip to False ONLY after Johan reviews the DRY output

DB = "/var/data/inspections.db"
BATCH = "5bc63a1e"
EXPECTED_ITEMS = 1716
EXPECTED_UNITS = 62

FFE = ('078888d2','7d1f2e4f','927c1174','d0262104','7d7e29c6','5d45a701',
'34ea5535','d1d59d05','26c05c6a','f0b24a5f','15f1af2e','d7c9d133','ad6e4d5b',
'936a5aec','070c65ca','31f0f475','96baddae','9359dd96','1f2fe184','70e37fa6',
'220f697a','2189cff1','69c1cf1c','2bd8271a','f3c554ab','35352a04','fe1f4b2d',
'd959dbdc','ecb87392','7b76217f','df96557c','5249a8fd','dc8d6550','46c2267f',
'dfcb88ce','20208261','84795b32','874c7df6','063bf215','151d2b2e','68ad5ceb',
'34d53e14','e4104535','5d30fb30')
PH = "(%s)" % ",".join("'%s'" % t for t in FFE)

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

# --- Select the exact target rows (latest cycle per unit) ---
SEL = """
WITH latest AS (
  SELECT i.unit_id, MAX(ic.cycle_number) maxc
  FROM batch_unit bu JOIN inspection i ON i.unit_id=bu.unit_id
  JOIN inspection_cycle ic ON ic.id=i.cycle_id
  WHERE bu.batch_id=? AND bu.removed_at IS NULL GROUP BY i.unit_id)
SELECT ii.id AS item_id, ii.status AS item_status, ii.comment AS item_comment,
       ii.marked_at AS item_marked_at,
       i.id AS insp_id, i.status AS insp_status, i.submitted_at AS insp_submitted_at,
       i.unit_id AS unit_id
FROM batch_unit bu JOIN inspection i ON i.unit_id=bu.unit_id
JOIN inspection_cycle ic ON ic.id=i.cycle_id
JOIN latest l ON l.unit_id=i.unit_id AND l.maxc=ic.cycle_number
JOIN inspection_item ii ON ii.inspection_id=i.id
LEFT JOIN cycle_excluded_item cei
       ON cei.cycle_id=i.cycle_id AND cei.item_template_id=ii.item_template_id
WHERE bu.batch_id=? AND bu.removed_at IS NULL
  AND ii.item_template_id IN %s
  AND ii.status='skipped'
  AND cei.reason IS NULL
""" % PH

rows = [dict(r) for r in c.execute(SEL, (BATCH, BATCH))]
units = sorted({r['unit_id'] for r in rows})
print("Target items:", len(rows), "| units:", len(units))

# Gate: refuse to run if the count drifted from the proven figure
assert len(rows) == EXPECTED_ITEMS, "ITEM COUNT DRIFT: got %d expected %d" % (len(rows), EXPECTED_ITEMS)
assert len(units) == EXPECTED_UNITS, "UNIT COUNT DRIFT: got %d expected %d" % (len(units), EXPECTED_UNITS)

# Submitted inspections in scope (need reopen)
subm = sorted({r['insp_id'] for r in rows if r['insp_status'] == 'submitted'})
print("Submitted inspections to reopen:", len(subm), subm if subm else "")

if DRY:
    print("\n*** DRY RUN -- no changes written ***")
    # sample 5
    for r in rows[:5]:
        print("  item", r['item_id'], "insp", r['insp_id'], "unit", r['unit_id'],
              "insp_status", r['insp_status'])
    print("\nWould flip %d items skipped->pending." % len(rows))
    print("Would back up %d item rows + %d inspection rows to v354_repair_backup."
          % (len(rows), len(subm)))
    c.close()
    raise SystemExit(0)

# --- LIVE RUN ---
now = datetime.datetime.utcnow().isoformat()

# Backup table (same schema as v353_repair_backup)
c.execute("""CREATE TABLE IF NOT EXISTS v354_repair_backup (
  kind TEXT, row_id TEXT, old_status TEXT, old_comment TEXT,
  old_marked_at TEXT, old_submitted_at TEXT)""")

nb = 0
for r in rows:
    c.execute("""INSERT INTO v354_repair_backup
      (kind,row_id,old_status,old_comment,old_marked_at,old_submitted_at)
      VALUES ('item',?,?,?,?,NULL)""",
      (r['item_id'], r['item_status'], r['item_comment'], r['item_marked_at']))
    nb += 1
for iid in subm:
    ins = c.execute("SELECT status, submitted_at FROM inspection WHERE id=?", (iid,)).fetchone()
    c.execute("""INSERT INTO v354_repair_backup
      (kind,row_id,old_status,old_comment,old_marked_at,old_submitted_at)
      VALUES ('inspection',?,?,NULL,NULL,?)""",
      (iid, ins['status'], ins['submitted_at']))
    nb += 1
print("Backed up", nb, "rows to v354_repair_backup.")

# Flip items
ids = [r['item_id'] for r in rows]
for chunk_start in range(0, len(ids), 500):
    chunk = ids[chunk_start:chunk_start+500]
    qmarks = ",".join("?" * len(chunk))
    c.execute("UPDATE inspection_item SET status='pending', comment=NULL "
              "WHERE id IN (%s)" % qmarks, chunk)

# Reopen submitted inspections
for iid in subm:
    c.execute("UPDATE inspection SET status='in_progress', submitted_at=NULL WHERE id=?", (iid,))

c.commit()
print("LIVE RUN done. Flipped %d items; reopened %d inspections." % (len(ids), len(subm)))

# Post-verify: re-run the exact selector; should now return 0
rc = len([1 for _ in c.execute(SEL, (BATCH, BATCH))])
print("Remaining in-scope skipped (should be 0):", rc)
bc = c.execute("SELECT COUNT(*) FROM v354_repair_backup").fetchone()[0]
print("v354_repair_backup row count:", bc)
c.close()
