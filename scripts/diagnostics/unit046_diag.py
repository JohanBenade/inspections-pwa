"""
unit046_diag.py
Diagnose why unit 046's projected items = 6 when Johan expects ~54.
"""
import sqlite3

TENANT_ID = 'MONOGRAPH'
BATCH_ID = '3237ea51'

conn = sqlite3.connect('/var/data/inspections.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

u = cur.execute(
    "SELECT id, floor, block, unit_number FROM unit "
    "WHERE unit_number = ? AND tenant_id = ?",
    ('046', TENANT_ID)).fetchone()
print(f"Unit 046: id={u['id']} floor={u['floor']} block={u['block']}")
unit_floor = int(u['floor']) if u['floor'] is not None else 0
print()

# C1 inspections for this unit
print("C1 inspections:")
for r in cur.execute(
        "SELECT id, cycle_id, exclusion_list_id, status FROM inspection "
        "WHERE unit_id = ? AND tenant_id = ? AND cycle_number = 1",
        (u['id'], TENANT_ID)).fetchall():
    print(f"  insp={r['id'][:8]} cycle={r['cycle_id'][:8] if r['cycle_id'] else 'NONE'} "
          f"excl={r['exclusion_list_id']} status={r['status']}")
print()

# C1 status distribution
print("C1 inspection_item status distribution:")
for r in cur.execute("""
    SELECT ii.status, COUNT(*) as n
    FROM inspection_item ii
    JOIN inspection i ON ii.inspection_id = i.id
    WHERE i.unit_id = ? AND i.cycle_number = 1
    GROUP BY ii.status
    ORDER BY n DESC
""", (u['id'],)).fetchall():
    print(f"  {r['status']:25} {r['n']:>4}")
print()

# Skipped templates broken down by active and floor_condition
print("C1 'skipped' templates breakdown by active + floor_condition:")
for r in cur.execute("""
    SELECT it.active, COALESCE(it.floor_condition, 'NULL') as fc, COUNT(*) as n
    FROM inspection_item ii
    JOIN inspection i ON ii.inspection_id = i.id
    JOIN item_template it ON ii.item_template_id = it.id
    WHERE i.unit_id = ? AND i.cycle_number = 1 AND ii.status = 'skipped'
    GROUP BY it.active, fc
    ORDER BY n DESC
""", (u['id'],)).fetchall():
    print(f"  active={r['active']} floor_condition={r['fc']:15} n={r['n']}")
print()

# Whatever would project as pending+hpd=0 (newly visible) per my formula
n_proj = cur.execute("""
    SELECT COUNT(*) as n FROM inspection_item ii
    JOIN inspection i ON ii.inspection_id = i.id
    JOIN item_template it ON ii.item_template_id = it.id
    WHERE i.unit_id = ? AND i.cycle_number = 1
      AND ii.status IN ('not_to_standard', 'not_installed', 'skipped')
      AND it.active = 1
      AND NOT (COALESCE(it.floor_condition, '') = 'ground_only' AND ? > 0)
      AND ii.item_template_id NOT IN (
          SELECT item_template_id FROM defect
          WHERE unit_id = ? AND tenant_id = ? AND status = 'open'
            AND raised_cycle_number < 2
      )
""", (u['id'], unit_floor, u['id'], TENANT_ID)).fetchone()['n']
print(f"Projected newly-visible items (no C2 exclusion filter applied): {n_proj}")
print()

# SR-017 batch_unit
bu = cur.execute("""
    SELECT cycle_id, exclusion_list_id, status, removed_at
    FROM batch_unit
    WHERE unit_id = ? AND batch_id = ?
""", (u['id'], BATCH_ID)).fetchone()
if bu:
    print(f"SR-017 batch_unit: cycle_id={bu['cycle_id']} "
          f"excl_list={bu['exclusion_list_id']} status={bu['status']} "
          f"removed_at={bu['removed_at']}")

    # cycle_excluded_item count for that cycle
    n_excl = cur.execute(
        "SELECT COUNT(*) as n FROM cycle_excluded_item WHERE cycle_id = ?",
        (bu['cycle_id'],)).fetchone()['n']
    print(f"cycle_excluded_item count for cycle {bu['cycle_id'][:8]}: {n_excl}")

    # If exclusion_list_item set
    if bu['exclusion_list_id']:
        n_li = cur.execute(
            "SELECT COUNT(*) as n FROM exclusion_list_item WHERE exclusion_list_id = ?",
            (bu['exclusion_list_id'],)).fetchone()['n']
        print(f"exclusion_list_item count for list {bu['exclusion_list_id']}: {n_li}")
else:
    print("SR-017 batch_unit: NOT FOUND")
print()

# Comparison: same query against unit 146 for sanity
u146 = cur.execute(
    "SELECT id, floor FROM unit WHERE unit_number = ? AND tenant_id = ?",
    ('146', TENANT_ID)).fetchone()
unit146_floor = int(u146['floor']) if u146['floor'] is not None else 0
print("--- Sanity check: same C1 skipped breakdown for unit 146 ---")
for r in cur.execute("""
    SELECT it.active, COALESCE(it.floor_condition, 'NULL') as fc, COUNT(*) as n
    FROM inspection_item ii
    JOIN inspection i ON ii.inspection_id = i.id
    JOIN item_template it ON ii.item_template_id = it.id
    WHERE i.unit_id = ? AND i.cycle_number = 1 AND ii.status = 'skipped'
    GROUP BY it.active, fc
    ORDER BY n DESC
""", (u146['id'],)).fetchall():
    print(f"  active={r['active']} floor_condition={r['fc']:15} n={r['n']}")

conn.close()
