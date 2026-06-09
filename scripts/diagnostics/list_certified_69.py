import sqlite3
from datetime import datetime as dt, timedelta as td
c = sqlite3.connect('/var/data/inspections.db'); c.row_factory = sqlite3.Row
TID = 'MONOGRAPH'

# Replicate SMB snapshot (live=False): anchor 2026-04-13, Tue 11:59 SAST -> UTC
now_sast = dt.utcnow() + td(hours=2)
ANCHOR = dt(2026, 4, 13)
today_mid = dt(now_sast.year, now_sast.month, now_sast.day)
days = (today_mid - ANCHOR).days
idx = 0 if days <= 0 else (days - 1) // 14
snap_mon = ANCHOR + td(days=14 * idx)
snap_utc = (snap_mon + td(days=1, hours=11, minutes=59)) - td(hours=2)
snap = snap_utc.strftime('%Y-%m-%d %H:%M:%S')
print('snapshot_str =', snap)

# Inspected gate (unit_max_completed keys)
completed = c.execute("""
  SELECT i.unit_id, MAX(i.cycle_number) m FROM inspection i
  JOIN unit_real u ON i.unit_id=u.id
  WHERE i.tenant_id=? AND i.review_submitted_at<=?
    AND i.status IN ('reviewed','approved','pending_followup')
  GROUP BY i.unit_id""", [TID, snap]).fetchall()
inspected = set(r['unit_id'] for r in completed)

# Open-defect count per unit (open_rows logic, verbatim)
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

ready = [uid for uid in inspected if unit_open.get(uid, 0) == 0]
rows = []
for uid in ready:
    u = c.execute("SELECT block, floor, unit_number FROM unit WHERE id=?", [uid]).fetchone()
    if u: rows.append((u['block'], u['floor'], u['unit_number']))
rows.sort(key=lambda x: (str(x[0]), str(x[1]), str(x[2])))
print('handover_ready count =', len(rows))
print('BLOCK | FLOOR | UNIT')
for b, f, n in rows:
    print(f'{b} | {f} | {n}')
