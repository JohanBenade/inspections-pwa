import sqlite3
c = sqlite3.connect('/var/data/inspections.db'); c.row_factory = sqlite3.Row
BACKUP = 'v401_mismatch_items'

# ---- Source target ids FROM the backup (frozen set, no re-derivation drift) ----
ids = [r['id'] for r in c.execute(f"SELECT id FROM {BACKUP}").fetchall()]
print(f"Backup '{BACKUP}' rows: {len(ids)}")
assert len(ids) == 7, f"BACKUP must have 7 rows, has {len(ids)} — STOP"
ph = ",".join("?" for _ in ids)

# ---- Re-assert all 7 still NTS right now ----
cur = c.execute(f"SELECT COUNT(*) FROM inspection_item WHERE id IN ({ph}) AND status='not_to_standard'", ids).fetchone()[0]
print(f"Still NTS now: {cur}")
assert cur == 7, f"EXPECTED 7 still NTS, got {cur} — state changed, STOP"

# ---- Confirm backup status snapshot is NTS (sanity: backup captured pre-state) ----
bk_nts = c.execute(f"SELECT COUNT(*) FROM {BACKUP} WHERE status='not_to_standard'").fetchone()[0]
assert bk_nts == 7, f"BACKUP snapshot not 7 NTS ({bk_nts}) — STOP"

# ---- LIVE WRITE ----
cur2 = c.execute(f"UPDATE inspection_item SET status='ok' WHERE id IN ({ph}) AND status='not_to_standard'", ids)
changed = cur2.rowcount
print(f"\n=== LIVE WRITE ===")
print(f"Rows changed: {changed}")
assert changed == 7, f"EXPECTED 7 changed, got {changed} — ROLLING BACK"
c.commit()
print("COMMITTED.")

# ---- VERIFY ----
ok_now = c.execute(f"SELECT COUNT(*) FROM inspection_item WHERE id IN ({ph}) AND status='ok'", ids).fetchone()[0]
nts_left = c.execute(f"SELECT COUNT(*) FROM inspection_item WHERE id IN ({ph}) AND status='not_to_standard'", ids).fetchone()[0]
print(f"\n=== VERIFY ===")
print(f"Now status='ok':  {ok_now} (expect 7)")
print(f"Still NTS:        {nts_left} (expect 0)")
for r in c.execute(f"SELECT id, status, marked_at, has_prior_defects FROM inspection_item WHERE id IN ({ph})", ids):
    print(f"  {r['id']} status={r['status']} marked_at={r['marked_at']} hpd={r['has_prior_defects']}")
assert ok_now == 7 and nts_left == 0, "VERIFY FAILED"
print("\n*** REPAIR COMPLETE — 7 MISMATCH items reset to ok. Backup retained. ***")
