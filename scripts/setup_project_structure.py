"""
Project Structure Setup - PPSH Phase 3
Run on Render console. Creates all 192 units, fixes Block 6/7 split.

WHAT THIS DOES:
1. Creates all missing units across all 7 blocks / 3 floors
2. Moves units 053-056 from Block 6 to Block 7
3. Creates Block 7 Ground R1 cycle
4. Reassigns inspections + defects for 053-056 to new cycle
5. Reports what changed
"""
import sqlite3
import uuid
from datetime import datetime, timezone

conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()
TENANT = 'MONOGRAPH'
PHASE = 'phase-003'
now = datetime.now(timezone.utc).isoformat()

def gen_id():
    return uuid.uuid4().hex[:8]

# ============================================================
# FULL PROJECT UNIT MAP (from Kevin's handwritten breakdown)
# ============================================================
UNIT_MAP = {
    ('Block 1', 0): ['000'],
    ('Block 1', 1): [str(n).zfill(3) for n in range(101, 103)],
    ('Block 1', 2): [str(n).zfill(3) for n in range(201, 203)] + [str(n).zfill(3) for n in range(248, 252)],
    ('Block 2', 1): [str(n).zfill(3) for n in range(144, 148)],
    ('Block 2', 2): [str(n).zfill(3) for n in range(244, 248)],
    ('Block 3', 0): [str(n).zfill(3) for n in range(1, 13)],
    ('Block 3', 1): [str(n).zfill(3) for n in range(103, 116)],
    ('Block 3', 2): [str(n).zfill(3) for n in range(203, 216)],
    ('Block 4', 0): [str(n).zfill(3) for n in range(13, 27)],
    ('Block 4', 1): [str(n).zfill(3) for n in range(116, 130)],
    ('Block 4', 2): [str(n).zfill(3) for n in range(216, 230)],
    ('Block 5', 0): [str(n).zfill(3) for n in range(27, 41)],
    ('Block 5', 1): [str(n).zfill(3) for n in range(130, 144)],
    ('Block 5', 2): [str(n).zfill(3) for n in range(230, 244)],
    ('Block 6', 0): [str(n).zfill(3) for n in range(41, 53)],
    ('Block 6', 1): [str(n).zfill(3) for n in range(148, 160)],
    ('Block 6', 2): [str(n).zfill(3) for n in range(252, 264)],
    ('Block 7', 0): [str(n).zfill(3) for n in range(53, 58)],
    ('Block 7', 1): [str(n).zfill(3) for n in range(160, 166)],
    ('Block 7', 2): [str(n).zfill(3) for n in range(264, 270)],
}

print("=== PPSH PHASE 3 PROJECT STRUCTURE ===")
print()

# ============================================================
# STEP 1: Fix Block 6 -> Block 7 for units 053-056
# ============================================================
print("--- STEP 1: Fix Block 6 -> Block 7 (units 053-056) ---")

# Check current state of these units
fix_units = ['053', '054', '055', '056']
for unum in fix_units:
    cur.execute("SELECT id, block, floor FROM unit WHERE unit_number = ? AND tenant_id = ?", (unum, TENANT))
    row = cur.fetchone()
    if row:
        print(f"  Unit {unum}: id={row[0]}, block={row[1]}, floor={row[2]}")
    else:
        print(f"  Unit {unum}: NOT IN DB")

# Update block assignment
cur.execute("""
    UPDATE unit SET block = 'Block 7', updated_at = ?
    WHERE unit_number IN ('053','054','055','056') AND tenant_id = ?
""", (now, TENANT))
print(f"  Updated {cur.rowcount} units to Block 7")

# Create Block 7 Ground R1 cycle
B7G_CYCLE_ID = gen_id()
cur.execute("""
    INSERT INTO inspection_cycle
    (id, tenant_id, phase_id, cycle_number, block, floor, created_by, created_at, status)
    VALUES (?, ?, ?, 1, 'Block 7', 0, 'system', ?, 'active')
""", (B7G_CYCLE_ID, TENANT, PHASE, now))
print(f"  Created Block 7 Ground R1 cycle: {B7G_CYCLE_ID}")

# Reassign inspections for units 053-056 from Block 6 cycle to Block 7 cycle
B6G_CYCLE = '36e85327'
cur.execute("""
    SELECT i.id, u.unit_number
    FROM inspection i
    JOIN unit u ON i.unit_id = u.id
    WHERE i.cycle_id = ? AND u.unit_number IN ('053','054','055','056')
""", (B6G_CYCLE,))
insp_rows = cur.fetchall()
print(f"  Found {len(insp_rows)} inspections to reassign")

for insp_id, unum in insp_rows:
    cur.execute("UPDATE inspection SET cycle_id = ? WHERE id = ?", (B7G_CYCLE_ID, insp_id))
    print(f"    Inspection {insp_id} (Unit {unum}): {B6G_CYCLE} -> {B7G_CYCLE_ID}")

# Reassign defects
cur.execute("""
    SELECT d.id, u.unit_number
    FROM defect d
    JOIN unit u ON d.unit_id = u.id
    WHERE d.raised_cycle_id = ? AND u.unit_number IN ('053','054','055','056')
""", (B6G_CYCLE,))
defect_rows = cur.fetchall()
print(f"  Found {len(defect_rows)} defects to reassign")

cur.execute("""
    UPDATE defect SET raised_cycle_id = ?
    WHERE raised_cycle_id = ? AND unit_id IN (
        SELECT id FROM unit WHERE unit_number IN ('053','054','055','056') AND tenant_id = ?
    )
""", (B7G_CYCLE_ID, B6G_CYCLE, TENANT))
print(f"  Reassigned {cur.rowcount} defects to Block 7 cycle")

# Reassign cycle_unit_assignment
cur.execute("""
    UPDATE cycle_unit_assignment SET cycle_id = ?
    WHERE cycle_id = ? AND unit_id IN (
        SELECT id FROM unit WHERE unit_number IN ('053','054','055','056') AND tenant_id = ?
    )
""", (B7G_CYCLE_ID, B6G_CYCLE, TENANT))
print(f"  Reassigned {cur.rowcount} cycle_unit_assignments")

# Also handle unit 057 if it exists
cur.execute("SELECT id, block FROM unit WHERE unit_number = '057' AND tenant_id = ?", (TENANT,))
u057 = cur.fetchone()
if u057:
    cur.execute("UPDATE unit SET block = 'Block 7', updated_at = ? WHERE id = ?", (now, u057[0]))
    print(f"  Unit 057 also moved to Block 7")
    # Check for inspections
    cur.execute("SELECT id FROM inspection WHERE unit_id = ? AND cycle_id = ?", (u057[0], B6G_CYCLE))
    for (iid,) in cur.fetchall():
        cur.execute("UPDATE inspection SET cycle_id = ? WHERE id = ?", (B7G_CYCLE_ID, iid))
        print(f"    Inspection {iid} (Unit 057): reassigned")
    cur.execute("""
        UPDATE defect SET raised_cycle_id = ? WHERE raised_cycle_id = ? AND unit_id = ?
    """, (B7G_CYCLE_ID, B6G_CYCLE, u057[0]))

print()

# ============================================================
# STEP 2: Create all missing units
# ============================================================
print("--- STEP 2: Create missing units ---")

created = 0
existing = 0
for (block, floor), unit_numbers in sorted(UNIT_MAP.items()):
    for unum in unit_numbers:
        cur.execute("SELECT id FROM unit WHERE unit_number = ? AND tenant_id = ?", (unum, TENANT))
        if cur.fetchone():
            existing += 1
            continue
        unit_id = gen_id()
        cur.execute("""
            INSERT INTO unit
            (id, tenant_id, unit_number, block, floor, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'not_started', ?, ?)
        """, (unit_id, TENANT, unum, block, floor, now, now))
        created += 1

print(f"  Existing: {existing}")
print(f"  Created: {created}")
print(f"  Total: {existing + created}")
print()

# ============================================================
# STEP 3: Verify final state
# ============================================================
print("--- VERIFICATION ---")

# Count by block+floor
cur.execute("""
    SELECT block, floor, COUNT(*) as cnt
    FROM unit WHERE tenant_id = ? AND unit_number NOT LIKE 'TEST%'
    GROUP BY block, floor
    ORDER BY block, floor
""", (TENANT,))
total = 0
for row in cur.fetchall():
    floor_label = {0: 'GF', 1: 'FF', 2: 'SF'}.get(row[1], f'F{row[1]}')
    print(f"  {row[0]} {floor_label}: {row[2]} units")
    total += row[2]
print(f"  TOTAL: {total} units")
print()

# Verify Block 6 / Block 7 split
print("--- BLOCK 6/7 SPLIT VERIFICATION ---")
for block in ['Block 6', 'Block 7']:
    cur.execute("""
        SELECT u.unit_number FROM unit u
        WHERE u.block = ? AND u.floor = 0 AND u.tenant_id = ?
        ORDER BY u.unit_number
    """, (block, TENANT))
    units = [r[0] for r in cur.fetchall()]
    print(f"  {block} GF: {', '.join(units)}")

# Verify defect counts
print()
print("--- DEFECT COUNTS ---")
for label, cid in [('B5G-R1', '792812c7'), ('B5G-R2', '855cd617'), ('B6G-R1', '36e85327'), ('B5-1F', '179b2b9d'), ('B7G-R1', B7G_CYCLE_ID)]:
    cur.execute("SELECT COUNT(*) FROM defect WHERE status='open' AND raised_cycle_id=?", (cid,))
    defects = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT i.unit_id) FROM inspection i WHERE i.cycle_id=?", (cid,))
    units = cur.fetchone()[0]
    print(f"  {label} ({cid}): {defects} defects, {units} units")

cur.execute("SELECT COUNT(*) FROM defect WHERE status='open' AND tenant_id=?", (TENANT,))
print(f"  TOTAL open: {cur.fetchone()[0]}")

# COMMIT
conn.commit()
print()
print("=== COMMITTED SUCCESSFULLY ===")
conn.close()
