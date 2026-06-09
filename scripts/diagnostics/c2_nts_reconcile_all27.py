import sqlite3
from datetime import datetime as dt, timedelta as td
c = sqlite3.connect('/var/data/inspections.db'); c.row_factory = sqlite3.Row
TID = 'MONOGRAPH'

# ---- 1. Reproduce the 69 handover-ready units (verbatim from list_certified_69.py) ----
now_sast = dt.utcnow() + td(hours=2)
ANCHOR = dt(2026, 4, 13)
today_mid = dt(now_sast.year, now_sast.month, now_sast.day)
days = (today_mid - ANCHOR).days
idx = 0 if days <= 0 else (days - 1) // 14
snap_mon = ANCHOR + td(days=14 * idx)
snap_utc = (snap_mon + td(days=1, hours=11, minutes=59)) - td(hours=2)
snap = snap_utc.strftime('%Y-%m-%d %H:%M:%S')
print('snapshot_str =', snap)

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

# ---- 2. Filter the 69 to C2 units ----
c2_ready = [uid for uid in ready if cyc.get(uid) == 2]
print('handover_ready total =', len(ready), '| C2 subset =', len(c2_ready))

# ---- 3. Reconcile NTS items per C2 unit (logic verbatim from nts_reconcile.py) ----
tot_legit = tot_orphan = tot_mismatch = 0
units_with_nts = 0
group_summary = {}  # unit_number -> dict
for uid in c2_ready:
    u = c.execute("SELECT unit_number FROM unit WHERE id=?", [uid]).fetchone()
    un = u['unit_number']
    insp = c.execute("""SELECT id FROM inspection WHERE unit_id=? AND tenant_id=? AND cycle_number=2
        ORDER BY created_at DESC LIMIT 1""", [uid, TID]).fetchone()
    if not insp:
        print(f"  !! Unit {un}: no C2 inspection found"); continue
    # exclusion-list link status (NULL-link 7 vs list-applied 20)
    link = c.execute("SELECT exclusion_list_id FROM inspection WHERE id=?", [insp['id']]).fetchone()
    grp = 'LIST' if link and link['exclusion_list_id'] else 'NULL'
    nts = c.execute("""SELECT ii.id, ii.item_template_id, it.item_description
        FROM inspection_item ii JOIN item_template it ON it.id=ii.item_template_id
        WHERE ii.inspection_id=? AND ii.status='not_to_standard'""", [insp['id']]).fetchall()
    if nts:
        units_with_nts += 1
    u_legit = u_mismatch = u_orphan = 0
    detail = []
    for n in nts:
        defs = c.execute("""SELECT id, status, raised_cycle_number, cleared_cycle_number
            FROM defect WHERE unit_id=? AND item_template_id=? AND tenant_id=?""",
            [uid, n['item_template_id'], TID]).fetchall()
        if not defs:
            tot_orphan += 1; u_orphan += 1
            detail.append(f"  ORPHAN   {n['item_description'][:40]:40} | NTS but NO defect row")
        else:
            statuses = [f"{d['status']}(r{d['raised_cycle_number']}/c{d['cleared_cycle_number']})" for d in defs]
            if any(d['status'] == 'open' for d in defs):
                tot_legit += 1; u_legit += 1
                detail.append(f"  LEGIT    {n['item_description'][:40]:40} | {', '.join(statuses)}")
            else:
                tot_mismatch += 1; u_mismatch += 1
                detail.append(f"  MISMATCH {n['item_description'][:40]:40} | {', '.join(statuses)}")
    group_summary[un] = dict(grp=grp, nts=len(nts), legit=u_legit, mismatch=u_mismatch, orphan=u_orphan)
    if nts:
        print(f"\n=== Unit {un} [{grp}-link]: {len(nts)} NTS (insp {insp['id']}) ===")
        for d in detail:
            print(d)

print("\n=== PER-UNIT TABLE (units with >=1 NTS) ===")
print(f"{'UNIT':5} {'LINK':5} {'NTS':>4} {'LEGIT':>6} {'MISMATCH':>9} {'ORPHAN':>7}")
for un in sorted(group_summary):
    g = group_summary[un]
    if g['nts'] > 0:
        print(f"{un:5} {g['grp']:5} {g['nts']:>4} {g['legit']:>6} {g['mismatch']:>9} {g['orphan']:>7}")

print("\n=== GRAND SUMMARY ===")
print(f"C2 units in 69:                 {len(c2_ready)}")
print(f"  of which NULL-link:           {sum(1 for g in group_summary.values() if g['grp']=='NULL')}")
print(f"  of which LIST-applied:        {sum(1 for g in group_summary.values() if g['grp']=='LIST')}")
print(f"C2 units carrying >=1 NTS item: {units_with_nts}")
print(f"LEGIT    (NTS backed by open defect): {tot_legit}")
print(f"MISMATCH (NTS, defect cleared):       {tot_mismatch}")
print(f"ORPHAN   (NTS, no defect row):        {tot_orphan}")
print(f"TOTAL NTS items:                      {tot_legit + tot_mismatch + tot_orphan}")
