"""
v2: Same projection as unit146_project.py, but pick the first non-NULL
exclusion_list_id from batch_unit rows (the most-recent row had None because
it's a post-reset row; we want the pre-reset 'inspecting' batch_unit's list).
"""
import sqlite3

conn = sqlite3.connect('/var/data/inspections.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

UID = 'd41d75d0'
TEN = 'MONOGRAPH'
CN = 2

u = cur.execute("SELECT * FROM unit WHERE id = ?", (UID,)).fetchone()
unit_floor = u['floor'] if 'floor' in u.keys() else 0
print(f'unit floor: {unit_floor}')

# First non-NULL exclusion list from batch_units (most recent valid)
excl_row = cur.execute(
    "SELECT exclusion_list_id FROM batch_unit "
    "WHERE unit_id = ? AND exclusion_list_id IS NOT NULL "
    "ORDER BY rowid DESC LIMIT 1", (UID,)
).fetchone()
excl_list_id = excl_row['exclusion_list_id'] if excl_row else None
print(f'using exclusion_list_id: {excl_list_id}')

n_excl = cur.execute(
    "SELECT COUNT(*) AS n FROM exclusion_list_item WHERE exclusion_list_id = ?",
    (excl_list_id,)
).fetchone()['n']
print(f'exclusion list size: {n_excl} items')

d = cur.execute(
    "SELECT COUNT(*) AS n FROM defect "
    "WHERE unit_id = ? AND tenant_id = ? AND raised_cycle_number < ? "
    "AND (status = 'open' OR (status = 'cleared' AND cleared_cycle_number = ?))",
    (UID, TEN, CN, CN)
).fetchone()['n']

l = cur.execute(
    "SELECT COUNT(*) AS n FROM latent_area_note "
    "WHERE unit_id = ? AND tenant_id = ? "
    "AND (rectified_at IS NULL OR rectified_at_cycle_number = ?)",
    (UID, TEN, CN)
).fetchone()['n']

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

print(f'\ndefects:        {d}')
print(f'latents:        {l}')
print(f'items (proj):   {i}')
print(f'TOTAL:          {d+l+i}')
print(f'PWA TARGET:     198')
print(f'MATCH:          {d+l+i == 198}')

conn.close()
