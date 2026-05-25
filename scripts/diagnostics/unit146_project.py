"""
Project the C2 cohort for unit 146 by mirroring the inspection_item creation
logic at app/routes/inspection.py L150-250 (in pure SQL, no live C2 inspection row needed).
Target: total = 198 (matching PWA before reset).
"""
import sqlite3

conn = sqlite3.connect('/var/data/inspections.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

UID = 'd41d75d0'
TEN = 'MONOGRAPH'
CN = 2

# Unit floor (column name unknown; detect)
u = cur.execute("SELECT * FROM unit WHERE id = ?", (UID,)).fetchone()
keys = u.keys()
floor_col = 'floor_number' if 'floor_number' in keys else ('floor' if 'floor' in keys else None)
unit_floor = u[floor_col] if floor_col else 0
print(f'unit floor: {unit_floor} (column: {floor_col})')

# Latest 3 batch_unit rows; most-recent should be C2 (SR-017)
bus = cur.execute(
    "SELECT id, batch_id, cycle_id, exclusion_list_id, status "
    "FROM batch_unit WHERE unit_id = ? ORDER BY rowid DESC LIMIT 3", (UID,)
).fetchall()
print('\nbatch_unit rows (latest 3):')
for r in bus:
    print(' ', dict(r))

excl_list_id = bus[0]['exclusion_list_id'] if bus else None
print(f'\nusing exclusion_list_id: {excl_list_id}')

# === Component 1: Defects ===
d = cur.execute(
    "SELECT COUNT(*) AS n FROM defect "
    "WHERE unit_id = ? AND tenant_id = ? AND raised_cycle_number < ? "
    "AND (status = 'open' OR (status = 'cleared' AND cleared_cycle_number = ?))",
    (UID, TEN, CN, CN)
).fetchone()['n']

# === Component 2: Latents ===
l = cur.execute(
    "SELECT COUNT(*) AS n FROM latent_area_note "
    "WHERE unit_id = ? AND tenant_id = ? "
    "AND (rectified_at IS NULL OR rectified_at_cycle_number = ?)",
    (UID, TEN, CN)
).fetchone()['n']

# === Component 3: Projected newly-visible items ===
# Templates where prev C1 status was NTS/NI/skipped, NOT on current exclusion list,
# NOT ground-only on upper floor, AND NO open prior defect (already in defects bucket).
i = cur.execute(
    "SELECT COUNT(DISTINCT it.id) AS n "
    "FROM item_template it "
    "JOIN inspection_item ii ON ii.item_template_id = it.id "
    "JOIN inspection insp ON ii.inspection_id = insp.id "
    "WHERE insp.unit_id = ? AND insp.tenant_id = ? AND insp.cycle_number = 1 "
    "  AND ii.status IN ('not_to_standard', 'not_installed', 'skipped') "
    "  AND NOT (COALESCE(it.floor_condition, '') = 'ground_only' AND ? > 0) "
    "  AND it.id NOT IN ("
    "    SELECT item_template_id FROM exclusion_list_item "
    "    WHERE exclusion_list_id = ?"
    "  ) "
    "  AND it.id NOT IN ("
    "    SELECT item_template_id FROM defect "
    "    WHERE unit_id = ? AND tenant_id = ? "
    "    AND raised_cycle_number < ? AND status = 'open'"
    "  )",
    (UID, TEN, unit_floor, excl_list_id, UID, TEN, CN)
).fetchone()['n']

# === Roll-up ===
print(f'\ndefects:        {d}')
print(f'latents:        {l}')
print(f'items (proj):   {i}')
print(f'TOTAL:          {d+l+i}')
print(f'PWA TARGET:     198')
print(f'MATCH:          {d+l+i == 198}')

# === Diagnostic breakdown of C1 statuses (helps if total != 198) ===
print('\n--- C1 inspection_item status histogram for unit 146 ---')
for r in cur.execute(
    "SELECT ii.status, COUNT(*) AS n "
    "FROM inspection_item ii JOIN inspection insp ON ii.inspection_id = insp.id "
    "WHERE insp.unit_id = ? AND insp.tenant_id = ? AND insp.cycle_number = 1 "
    "GROUP BY ii.status", (UID, TEN)
).fetchall():
    print(' ', dict(r))

conn.close()
