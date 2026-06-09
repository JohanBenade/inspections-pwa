import sqlite3
from datetime import datetime as dt, timedelta as td
c = sqlite3.connect('/var/data/inspections.db'); c.row_factory = sqlite3.Row
TID = 'MONOGRAPH'

# ---- Reproduce the 69 -> C2 subset (verbatim gates) ----
now_sast = dt.utcnow() + td(hours=2)
ANCHOR = dt(2026, 4, 13)
today_mid = dt(now_sast.year, now_sast.month, now_sast.day)
days = (today_mid - ANCHOR).days
idx = 0 if days <= 0 else (days - 1) // 14
snap_mon = ANCHOR + td(days=14 * idx)
snap = ((snap_mon + td(days=1, hours=11, minutes=59)) - td(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
completed = c.execute("""
  SELECT i.unit_id, MAX(i.cycle_number) m FROM inspection i
  JOIN unit_real u ON i.unit_id=u.id
  WHERE i.tenant_id=? AND i.review_submitted_at<=?
    AND i.status IN ('reviewed','approved','pending_followup')
  GROUP BY i.unit_id""", [TID, snap]).fetchall()
inspected = set(r['unit_id'] for r in completed)
openr = c.execute("""
  SELECT d.unit_id, COUNT(*) cnt FROM defect d JOIN unit_real u ON d.unit_id=u.id
  WHERE d.tenant_id=? AND d.created_at<=?
    AND (d.status='open' OR (d.status='cleared' AND d.cleared_at>?))
    AND d.raised_cycle_id NOT LIKE 'test-%'
    AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id=d.unit_id
        AND i2.cycle_id=d.raised_cycle_id
        AND i2.status IN ('reviewed','approved','certified','pending_followup')
        AND i2.review_submitted_at<=?)
  GROUP BY d.unit_id""", [TID, snap, snap, snap]).fetchall()
unit_open = {r['unit_id']: r['cnt'] for r in openr}
cyc = {r['unit_id']: r['m'] for r in completed}
c2_ready = [uid for uid in inspected if unit_open.get(uid, 0) == 0 and cyc.get(uid) == 2]

# ---- Find MISMATCH items, read full shapes ----
print("=== MISMATCH ITEMS — FULL SHAPE (read-only) ===\n")
n_mismatch = 0
all_intact = True
for uid in c2_ready:
    u = c.execute("SELECT unit_number FROM unit WHERE id=?", [uid]).fetchone()
    un = u['unit_number']
    insp = c.execute("""SELECT id FROM inspection WHERE unit_id=? AND tenant_id=? AND cycle_number=2
        ORDER BY created_at DESC LIMIT 1""", [uid, TID]).fetchone()
    if not insp:
        continue
    nts = c.execute("""SELECT ii.id, ii.item_template_id, ii.status, ii.comment, ii.marked_at,
            ii.has_prior_defects, it.item_description
        FROM inspection_item ii JOIN item_template it ON it.id=ii.item_template_id
        WHERE ii.inspection_id=? AND ii.status='not_to_standard'""", [insp['id']]).fetchall()
    for n in nts:
        defs = c.execute("""SELECT id, status, defect_type, cleared_cycle_number, cleared_cycle_id,
                cleared_at, clearance_note, raised_cycle_number, addressed_cycle_number
            FROM defect WHERE unit_id=? AND item_template_id=? AND tenant_id=?""",
            [uid, n['item_template_id'], TID]).fetchall()
        if not defs:
            continue  # orphan, skip
        if any(d['status'] == 'open' for d in defs):
            continue  # legit, skip
        # MISMATCH
        n_mismatch += 1
        print(f"Unit {un} | item '{n['item_description'][:45]}'")
        print(f"  inspection_item: id={n['id']} status={n['status']} marked_at={n['marked_at']}"
              f" comment={(n['comment'] or '-')[:40]} hpd={n['has_prior_defects']}")
        for d in defs:
            intact = (d['cleared_at'] is not None and d['cleared_cycle_id'] is not None)
            if not intact:
                all_intact = False
            print(f"  defect: id={d['id']} status={d['status']} type={d['defect_type']}"
                  f" r{d['raised_cycle_number']}/c{d['cleared_cycle_number']}"
                  f" cci={d['cleared_cycle_id']} cleared_at={d['cleared_at']}"
                  f" note={d['clearance_note']} acn={d['addressed_cycle_number']} INTACT={intact}")
        # inspection_defect link (an ok transition deletes these)
        idf = c.execute("""SELECT id, description, defect_type, created_at
            FROM inspection_defect WHERE inspection_item_id=?""", [n['id']]).fetchall()
        if idf:
            for x in idf:
                print(f"  inspection_defect: id={x['id']} desc={(x['description'] or '-')[:40]} type={x['defect_type']}")
        else:
            print(f"  inspection_defect: NONE")
        print()

print("=== SUMMARY ===")
print(f"MISMATCH items found: {n_mismatch}")
print(f"All backing defects intact-cleared (cleared_at + cci present): {all_intact}")
