#!/usr/bin/env python3
# CEI SKIP POLLUTION REPAIR -- LIVE
# Flips the 1196 CEI-polluted current-cycle items to their true seeded state:
#   1173 -> ok, 5 parents-with-open-children -> pending, 18 ground_only stay skipped.
# Discipline: backup -> precheck -> partition asserts -> transactional write -> verify.
# Run on RENDER:  python3 /app/scripts/diagnostics/cei_repair_live.py
import sqlite3, shutil, datetime, sys
DB = '/var/data/inspections.db'

# --- BACKUP ---
stamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
bak = f'/var/data/inspections.db.bak_ceifix_{stamp}'
shutil.copy2(DB, bak)
print(f"BACKUP: {bak}")

c = sqlite3.connect(DB); c.row_factory = sqlite3.Row

BAD = """
WITH maxc AS (SELECT unit_id, MAX(cycle_number) mc FROM inspection GROUP BY unit_id),
bad AS (
 SELECT ii3.id item_id, ii3.inspection_id, ii3.item_template_id, i3.unit_id,
        it.parent_item_id, COALESCE(it.floor_condition,'') fc
 FROM inspection i3
 JOIN maxc ON maxc.unit_id=i3.unit_id AND maxc.mc=i3.cycle_number
 JOIN inspection_item ii3 ON ii3.inspection_id=i3.id
      AND ii3.status='skipped' AND ii3.marked_at IS NULL
 JOIN inspection i2 ON i2.unit_id=i3.unit_id AND i2.cycle_number=i3.cycle_number-1
 JOIN inspection_item ii2 ON ii2.inspection_id=i2.id
      AND ii2.item_template_id=ii3.item_template_id AND ii2.status='ok'
 JOIN item_template it ON it.id=ii3.item_template_id
 WHERE i3.cycle_number>=3
)
"""
rows = c.execute(BAD + " SELECT * FROM bad").fetchall()

# --- PRECHECK ---
print(f"PRECHECK: bad rows = {len(rows)}")
assert len(rows) == 1196, f"ABORT: expected 1196, got {len(rows)}"

# --- CLASSIFY (identical logic to dry run) ---
to_ok, to_pending, leave_skipped = [], [], []
for r in rows:
    if r['fc'] == 'ground_only':
        leave_skipped.append(r); continue
    if r['parent_item_id'] is None:
        open_kids = c.execute("""
            SELECT COUNT(*) FROM item_template ct
            JOIN inspection_item ch ON ch.inspection_id=? AND ch.item_template_id=ct.id
            WHERE ct.parent_item_id=?
              AND ch.status IN ('pending','not_to_standard','not_installed')
        """, [r['inspection_id'], r['item_template_id']]).fetchone()[0]
        (to_pending if open_kids > 0 else to_ok).append(r)
    else:
        to_ok.append(r)

print(f"PARTITION: ok={len(to_ok)} pending={len(to_pending)} skip={len(leave_skipped)}")
assert len(to_ok) == 1173, f"ABORT: ok={len(to_ok)}"
assert len(to_pending) == 5, f"ABORT: pending={len(to_pending)}"
assert len(leave_skipped) == 18, f"ABORT: skip={len(leave_skipped)}"
print("PARTITION ASSERTS PASS")

# --- WRITE (single transaction) ---
ok_ids = [r['item_id'] for r in to_ok]
pe_ids = [r['item_id'] for r in to_pending]
try:
    cur = c.cursor()
    cur.execute("BEGIN")
    cur.executemany("UPDATE inspection_item SET status='ok', comment=NULL WHERE id=?",
                    [(i,) for i in ok_ids])
    n_ok = cur.rowcount
    cur.executemany("UPDATE inspection_item SET status='pending', comment=NULL WHERE id=?",
                    [(i,) for i in pe_ids])
    n_pe = cur.rowcount
    c.commit()
    print(f"WROTE: ok-updates issued for {len(ok_ids)} ids, pending for {len(pe_ids)} ids")
except Exception as e:
    c.rollback()
    print(f"ROLLED BACK: {e}"); sys.exit(1)

# --- VERIFY: signature query must now read 18 (the ground_only) ---
sig = c.execute(BAD + " SELECT COUNT(*) n, COUNT(DISTINCT unit_id) u FROM bad").fetchone()
print(f"POST-REPAIR SIGNATURE: skipped-prior-ok rows = {sig['n']} across {sig['u']} units")
print("  (expected 18, all ground_only above-GF)")
assert sig['n'] == 18, f"WARN: signature={sig['n']}, expected 18 -- investigate"
# confirm all 18 remaining are ground_only
chk = c.execute(BAD + """
  SELECT SUM(fc='ground_only') g, COUNT(*) tot FROM bad
""").fetchone()
print(f"  of remaining: ground_only={chk['g']} / total={chk['tot']}")
assert chk['g'] == chk['tot'], "WARN: non-ground_only residue remains"
print("VERIFY PASS. Repair complete.")
print(f"Backup retained at: {bak}")
