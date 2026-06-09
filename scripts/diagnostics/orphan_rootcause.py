import sqlite3
from datetime import datetime as dt, timedelta as td
c = sqlite3.connect('/var/data/inspections.db'); c.row_factory = sqlite3.Row
TID = 'MONOGRAPH'

# ---- Reproduce the 69 (verbatim from list_certified_69.py) ----
now_sast = dt.utcnow() + td(hours=2)
ANCHOR = dt(2026, 4, 13)
today_mid = dt(now_sast.year, now_sast.month, now_sast.day)
days = (today_mid - ANCHOR).days
idx = 0 if days <= 0 else (days - 1) // 14
snap_mon = ANCHOR + td(days=14 * idx)
snap_utc = (snap_mon + td(days=1, hours=11, minutes=59)) - td(hours=2)
snap = snap_utc.strftime('%Y-%m-%d %H:%M:%S')

completed = c.execute("""
  SELECT i.unit_id, MAX(i.cycle_number) m FROM inspection i
  JOIN unit_real u ON i.unit_id=u.id
  WHERE i.tenant_id=? AND i.review_submitted_at<=?
    AND i.status IN ('reviewed','approved','pending_followup')
  GROUP BY i.unit_id""", [TID, snap]).fetchall()
inspected = set(r['unit_id'] for r in completed)
openr = c.execute("""
  SELECT d.unit_id, COUNT(*) cnt FROM defect d
  JOIN unit_real u ON d.unit_id=u.id
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
ready = [uid for uid in inspected if unit_open.get(uid, 0) == 0]
c2_ready = [uid for uid in ready if cyc.get(uid) == 2]

# ---- For each C2 unit: find ORPHAN NTS items, dump root-cause fields ----
print(f"{'UNIT':5} {'ITEM':40} {'COMMENT?':9} {'MARKED_AT':21} {'HPD':3} {'CREATED==MARKED?':16}")
print("-" * 100)
orphan_total = with_comment = with_marked = bare = 0
unit_counts = {}
for uid in c2_ready:
    u = c.execute("SELECT unit_number FROM unit WHERE id=?", [uid]).fetchone()
    un = u['unit_number']
    insp = c.execute("""SELECT id FROM inspection WHERE unit_id=? AND tenant_id=? AND cycle_number=2
        ORDER BY created_at DESC LIMIT 1""", [uid, TID]).fetchone()
    if not insp:
        continue
    nts = c.execute("""SELECT ii.id, ii.item_template_id, ii.comment, ii.marked_at,
            ii.created_at, ii.has_prior_defects, it.item_description
        FROM inspection_item ii JOIN item_template it ON it.id=ii.item_template_id
        WHERE ii.inspection_id=? AND ii.status='not_to_standard'""", [insp['id']]).fetchall()
    for n in nts:
        defs = c.execute("""SELECT id FROM defect
            WHERE unit_id=? AND item_template_id=? AND tenant_id=?""",
            [uid, n['item_template_id'], TID]).fetchall()
        if defs:
            continue  # not an orphan
        orphan_total += 1
        unit_counts[un] = unit_counts.get(un, 0) + 1
        cmt = (n['comment'] or '').strip()
        has_cmt = 'YES' if cmt else 'no'
        ma = n['marked_at'] or '-'
        ca = n['created_at'] or '-'
        same = 'yes' if (n['marked_at'] and n['created_at'] and n['marked_at'] == n['created_at']) else ('NULL-ma' if not n['marked_at'] else 'no')
        if cmt:
            with_comment += 1
        if n['marked_at']:
            with_marked += 1
        if not cmt and not n['marked_at']:
            bare += 1
        print(f"{un:5} {n['item_description'][:40]:40} {has_cmt:9} {str(ma):21} {str(n['has_prior_defects']):3} {same:16}")
        if cmt:
            print(f"      comment: {cmt[:90]}")

print("\n=== ORPHAN ROOT-CAUSE SUMMARY ===")
print(f"Total orphans:                 {orphan_total}")
print(f"  carry a comment:             {with_comment}")
print(f"  have non-NULL marked_at:     {with_marked}")
print(f"  bare (no comment, no mark):  {bare}")
print(f"Per-unit orphan counts: {dict(sorted(unit_counts.items()))}")
