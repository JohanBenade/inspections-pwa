import sqlite3
from datetime import datetime as dt, timedelta as td
c = sqlite3.connect('/var/data/inspections.db'); c.row_factory = sqlite3.Row
TID = 'MONOGRAPH'
BACKUP = 'v401_mismatch_items'

# ---- Reproduce the 69 -> C2 subset (verbatim gates) ----
now_sast = dt.utcnow() + td(hours=2)
ANCHOR = dt(2026, 4, 13)
today_mid = dt(now_sast.year, now_sast.month, now_sast.day)
days = (today_mid - ANCHOR).days
idx = 0 if days <= 0 else (days - 1) // 14
snap_mon = ANCHOR + td(days=14 * idx)
snap = ((snap_mon + td(days=1, hours=11, minutes=59)) - td(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
completed = c.execute("""
  SELECT i.unit_id, MAX(i.cycle_number) m FROM inspection i JOIN unit_real u ON i.unit_id=u.id
  WHERE i.tenant_id=? AND i.review_submitted_at<=? AND i.status IN ('reviewed','approved','pending_followup')
  GROUP BY i.unit_id""", [TID, snap]).fetchall()
inspected = set(r['unit_id'] for r in completed)
openr = c.execute("""
  SELECT d.unit_id, COUNT(*) cnt FROM defect d JOIN unit_real u ON d.unit_id=u.id
  WHERE d.tenant_id=? AND d.created_at<=? AND (d.status='open' OR (d.status='cleared' AND d.cleared_at>?))
    AND d.raised_cycle_id NOT LIKE 'test-%'
    AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id=d.unit_id AND i2.cycle_id=d.raised_cycle_id
        AND i2.status IN ('reviewed','approved','certified','pending_followup') AND i2.review_submitted_at<=?)
  GROUP BY d.unit_id""", [TID, snap, snap, snap]).fetchall()
unit_open = {r['unit_id']: r['cnt'] for r in openr}
cyc = {r['unit_id']: r['m'] for r in completed}
c2_ready = [uid for uid in inspected if unit_open.get(uid, 0) == 0 and cyc.get(uid) == 2]

# ---- Identify the MISMATCH item ids (NTS over a defect that exists & none open) ----
target_item_ids = []
detail = []
for uid in c2_ready:
    u = c.execute("SELECT unit_number FROM unit WHERE id=?", [uid]).fetchone()
    insp = c.execute("""SELECT id FROM inspection WHERE unit_id=? AND tenant_id=? AND cycle_number=2
        ORDER BY created_at DESC LIMIT 1""", [uid, TID]).fetchone()
    if not insp:
        continue
    nts = c.execute("""SELECT ii.id, ii.item_template_id, it.item_description
        FROM inspection_item ii JOIN item_template it ON it.id=ii.item_template_id
        WHERE ii.inspection_id=? AND ii.status='not_to_standard'""", [insp['id']]).fetchall()
    for n in nts:
        defs = c.execute("SELECT status, cleared_at, cleared_cycle_id FROM defect WHERE unit_id=? AND item_template_id=? AND tenant_id=?",
                         [uid, n['item_template_id'], TID]).fetchall()
        if not defs:
            continue  # orphan
        if any(d['status'] == 'open' for d in defs):
            continue  # legit
        # MISMATCH — require ALL backing defects intact-cleared (safety gate)
        if not all(d['status'] == 'cleared' and d['cleared_at'] and d['cleared_cycle_id'] for d in defs):
            print(f"!! Unit {u['unit_number']} item {n['id']}: NOT all defects intact-cleared — EXCLUDING"); continue
        target_item_ids.append(n['id'])
        detail.append((u['unit_number'], n['id'], n['item_description'][:40]))

print("=== TARGET ITEMS (MISMATCH, all backing defects intact-cleared) ===")
for un, iid, desc in detail:
    print(f"  Unit {un} | item {iid} | {desc}")

# ---- PRECHECK ----
N = len(target_item_ids)
print(f"\n=== PRECHECK ===")
print(f"Target item count: {N}")
assert N == 7, f"EXPECTED 7 MISMATCH items, got {N} — STOP, investigate before proceeding"
# confirm all are currently not_to_standard
ph = ",".join("?" for _ in target_item_ids)
cur = c.execute(f"SELECT COUNT(*) FROM inspection_item WHERE id IN ({ph}) AND status='not_to_standard'", target_item_ids).fetchone()[0]
print(f"Currently status='not_to_standard': {cur}")
assert cur == 7, f"EXPECTED all 7 NTS, got {cur} — STOP"

# ---- BACKUP ----
c.execute(f"DROP TABLE IF EXISTS {BACKUP}")
c.execute(f"""CREATE TABLE {BACKUP} AS
    SELECT * FROM inspection_item WHERE id IN ({ph})""", target_item_ids)
c.commit()
bk = c.execute(f"SELECT COUNT(*) FROM {BACKUP}").fetchone()[0]
print(f"\n=== BACKUP ===")
print(f"Backup table '{BACKUP}' created with {bk} rows")
assert bk == 7, "BACKUP row count != 7 — STOP"

# ---- DRY RUN (no write) ----
print(f"\n=== DRY RUN (no mutation) ===")
print(f"WOULD execute: UPDATE inspection_item SET status='ok' WHERE id IN (...7 ids...)")
print(f"  marked_at: LEFT AS-IS (already set; hpd=1 so not misread as carried_ok)")
print(f"  defect layer: UNCHANGED (already intact-cleared)")
print(f"  inspection_defect: none to delete (confirmed NONE in prior read)")
print(f"\nExpected changes on live: 7 rows status not_to_standard -> ok")
print(f"\n*** STOPPED before live write. Review, then run the live script. ***")
