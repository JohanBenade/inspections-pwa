#!/usr/bin/env python3
# CEI SKIP POLLUTION REPAIR -- DRY RUN (writes NOTHING)
# Prints the exact partition, per-unit breakdown, and post-repair signature.
# Run on RENDER:  python3 /tmp/cei_repair_dry.py
import sqlite3
DB = '/var/data/inspections.db'
c = sqlite3.connect(DB); c.row_factory = sqlite3.Row

# The bad set: current (max-cycle, c>=3) inspection_item rows that are
# skipped+marked_at NULL but were 'ok' in the immediately-prior cycle.
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
assert len(rows) == 1196, f"EXPECTED 1196 bad rows, got {len(rows)}"

# classify each bad row
to_ok, to_pending, leave_skipped = [], [], []
for r in rows:
    if r['fc'] == 'ground_only':
        leave_skipped.append(r); continue
    if r['parent_item_id'] is None:
        # parent: pending iff any child currently open in same inspection
        open_kids = c.execute("""
            SELECT COUNT(*) FROM item_template ct
            JOIN inspection_item ch ON ch.inspection_id=? AND ch.item_template_id=ct.id
            WHERE ct.parent_item_id=?
              AND ch.status IN ('pending','not_to_standard','not_installed')
        """, [r['inspection_id'], r['item_template_id']]).fetchone()[0]
        (to_pending if open_kids > 0 else to_ok).append(r)
    else:
        to_ok.append(r)

print("=== PARTITION (DRY RUN, no writes) ===")
print(f"  -> ok      : {len(to_ok)}")
print(f"  -> pending : {len(to_pending)}")
print(f"  stay skipped (ground_only above-GF): {len(leave_skipped)}")
print(f"  TOTAL      : {len(to_ok)+len(to_pending)+len(leave_skipped)}")
assert len(to_ok)+len(to_pending)+len(leave_skipped) == 1196
assert len(to_ok) == 1173, f"expected 1173 ok, got {len(to_ok)}"
assert len(to_pending) == 5, f"expected 5 pending, got {len(to_pending)}"
assert len(leave_skipped) == 18, f"expected 18 skipped, got {len(leave_skipped)}"
print("  partition asserts PASS")

# per-unit summary
from collections import defaultdict
per = defaultdict(lambda: [0,0,0])
uname = {}
for grp, lst in ((0,to_ok),(1,to_pending),(2,leave_skipped)):
    for r in lst:
        per[r['unit_id']][grp]+=1
print("\n=== PER-UNIT (unit_id: ok/pending/skipped) ===")
for uid in sorted(per):
    if uid not in uname:
        u=c.execute("SELECT name FROM unit WHERE id=?", [uid]).fetchone()
        uname[uid]=u['name'] if u else uid
    a,b,s=per[uid]
    print(f"  {uname[uid]:>6}  ok={a:>3} pending={b} skip={s}")
print(f"  units affected: {len(per)}")

# what the signature query WOULD read after repair (the 18 remain)
print("\n=== POST-REPAIR SIGNATURE (predicted) ===")
print(f"  bad_items would read: {len(leave_skipped)} (all ground_only above-GF, legit)")
print("  NOTHING WAS WRITTEN.")
