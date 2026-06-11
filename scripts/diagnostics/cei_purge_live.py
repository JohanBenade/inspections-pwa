#!/usr/bin/env python3
# PART 3 -- PURGE POLLUTED CEI ROWS
# Deletes cycle_excluded_item rows written 2026-05-19 onto current C3 cycles that
# have inspection.exclusion_list_id IS NULL (the cleanup-script pollution).
# These are already inert after the v417 guard; this removes them permanently.
# Discipline: backup -> precheck(assert 675/7) -> transactional delete -> verify.
# Run on RENDER:  python3 /app/scripts/diagnostics/cei_purge_live.py
import sqlite3, shutil, datetime, sys
DB = '/var/data/inspections.db'

stamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
bak = f'/var/data/inspections.db.bak_ceipurge_{stamp}'
shutil.copy2(DB, bak)
print(f"BACKUP: {bak}")

c = sqlite3.connect(DB); c.row_factory = sqlite3.Row

# The target cycles: distinct cycle_id of CEI rows dated 2026-05-19 whose joined
# inspection is cycle_number 3 with NULL exclusion_list_id.
TARGET = """
SELECT DISTINCT cei.cycle_id
FROM cycle_excluded_item cei
JOIN inspection i ON i.cycle_id = cei.cycle_id
WHERE cei.created_at LIKE '2026-05-19%'
  AND i.cycle_number = 3
  AND i.exclusion_list_id IS NULL
"""
cycles = [r['cycle_id'] for r in c.execute(TARGET).fetchall()]
print(f"TARGET CYCLES: {len(cycles)}")
assert len(cycles) == 7, f"ABORT: expected 7 cycles, got {len(cycles)}"

# Count rows to delete: ALL CEI rows on those target cycles dated 2026-05-19.
qmarks = ",".join("?" * len(cycles))
pre = c.execute(
    f"SELECT COUNT(*) n FROM cycle_excluded_item "
    f"WHERE cycle_id IN ({qmarks}) AND created_at LIKE '2026-05-19%'", cycles
).fetchone()['n']
total_before = c.execute("SELECT COUNT(*) n FROM cycle_excluded_item").fetchone()['n']
print(f"PRECHECK: rows to delete = {pre} ; total CEI before = {total_before}")
assert pre == 675, f"ABORT: expected 675 rows, got {pre}"

# DELETE (transaction)
try:
    cur = c.cursor()
    cur.execute("BEGIN")
    cur.execute(
        f"DELETE FROM cycle_excluded_item "
        f"WHERE cycle_id IN ({qmarks}) AND created_at LIKE '2026-05-19%'", cycles)
    n = cur.rowcount
    c.commit()
    print(f"DELETED: {n} rows")
except Exception as e:
    c.rollback(); print(f"ROLLED BACK: {e}"); sys.exit(1)

# VERIFY
remain = c.execute(
    f"SELECT COUNT(*) n FROM cycle_excluded_item "
    f"WHERE cycle_id IN ({qmarks}) AND created_at LIKE '2026-05-19%'", cycles
).fetchone()['n']
total_after = c.execute("SELECT COUNT(*) n FROM cycle_excluded_item").fetchone()['n']
print(f"VERIFY: rows remaining on target cycles = {remain} (expect 0)")
print(f"        total CEI after = {total_after} (before {total_before}, delta {total_before-total_after})")
assert remain == 0, "ABORT-WARN: residue remains on target cycles"
assert total_before - total_after == 675, "ABORT-WARN: total delta != 675 (collateral?)"
print("VERIFY PASS. Purge complete.")
print(f"Backup retained at: {bak}")
