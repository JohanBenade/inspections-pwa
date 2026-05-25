"""
unit146_project_v3.py

Projects the C2 newly-visible item cohort for unit 146 (or any unit) by
mirroring the C2 inspection_item creation logic at
app/routes/inspection.py L150-275 — INCLUDING rules 2, 3, and 4.

Why: for SR-017 (and any unit without an active C2 inspection),
_desnag_progress returns items=0 because no inspection_item rows exist.
The projection is the canonical cohort estimator for those units.

Formula:
    total = defect_count + latent_count + projected_newly_visible_items

For unit 146 (current state — no live C2 inspection):
    expect defects=144, latents=0, items=54, TOTAL=198
"""
import sqlite3

UNIT_ID = 'd41d75d0'
TENANT_ID = 'MONOGRAPH'

conn = sqlite3.connect('/var/data/inspections.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ---- Unit info ----
unit = cur.execute("SELECT * FROM unit WHERE id=? AND tenant_id=?",
                   (UNIT_ID, TENANT_ID)).fetchone()
if not unit:
    print(f"ERROR: unit {UNIT_ID} not found")
    raise SystemExit(1)
try:
    unit_floor = int(unit['floor']) if unit['floor'] is not None else 0
except (ValueError, TypeError):
    unit_floor = 0
print(f"Unit {UNIT_ID}: floor={unit_floor}  unit_number={unit['unit_number']}")

# ---- Latest batch_unit + its exclusion_list_id ----
bu = cur.execute("""
    SELECT bu.exclusion_list_id, bu.batch_id
    FROM batch_unit bu
    JOIN inspection_batch ib ON bu.batch_id = ib.id
    WHERE bu.unit_id = ? AND bu.tenant_id = ?
    ORDER BY ib.created_at DESC LIMIT 1
""", (UNIT_ID, TENANT_ID)).fetchone()
excl_id = bu['exclusion_list_id'] if bu else None
print(f"Latest batch_unit: batch={bu['batch_id'][:8] if bu else 'NONE'}  excl_list_id={excl_id}")

current_exclusions = set()
if excl_id:
    rows = cur.execute(
        "SELECT item_template_id FROM exclusion_list_item WHERE exclusion_list_id=?",
        (excl_id,)).fetchall()
    current_exclusions = set(r['item_template_id'] for r in rows)
print(f"current_exclusions: {len(current_exclusions)} templates")

# ---- All templates (id, parent_item_id, floor_condition) ----
templates = {}
for r in cur.execute(
        "SELECT id, parent_item_id, floor_condition FROM item_template WHERE tenant_id=?",
        (TENANT_ID,)).fetchall():
    templates[r['id']] = dict(r)
print(f"item_template total: {len(templates)}")

# ---- Parent->children map ----
parent_to_children = {}
for tid, t in templates.items():
    pid = t['parent_item_id']
    if pid:
        parent_to_children.setdefault(pid, []).append(tid)
parents_with_kids = set(parent_to_children.keys())

# ---- C1 inspection_item statuses (prev_item_map) ----
c1_rows = cur.execute("""
    SELECT ii.item_template_id, ii.status
    FROM inspection_item ii
    JOIN inspection i ON ii.inspection_id = i.id
    WHERE i.unit_id = ? AND i.tenant_id = ? AND i.cycle_number = 1
""", (UNIT_ID, TENANT_ID)).fetchall()
prev_status = {r['item_template_id']: r['status'] for r in c1_rows}
print(f"C1 inspection_items: {len(prev_status)}")

# ---- has_prior_defects source: open defects raised in C1 ----
defect_tmpls = cur.execute("""
    SELECT DISTINCT item_template_id FROM defect
    WHERE unit_id = ? AND tenant_id = ?
    AND status = 'open' AND raised_cycle_number < 2
""", (UNIT_ID, TENANT_ID)).fetchall()
prior_defect_set = set(r['item_template_id'] for r in defect_tmpls)
print(f"templates with open prior defect: {len(prior_defect_set)}")

# ===========================================================================
# Step 1: Initial C2 status per template (mirrors L168-205)
# ===========================================================================
c2_status = {}
hpd = {}
for tid, prev_s in prev_status.items():
    t = templates.get(tid)
    if not t:
        continue
    if tid in current_exclusions:
        s = 'skipped'
    elif t['floor_condition'] == 'ground_only' and unit_floor > 0:
        s = 'skipped'
    else:
        if prev_s in (None, 'pending', 'ok'):
            s = 'ok'
        elif prev_s in ('not_to_standard', 'not_installed', 'skipped'):
            s = 'pending'
        else:
            s = 'pending'
    c2_status[tid] = s
    hpd[tid] = 1 if tid in prior_defect_set else 0

baseline = sum(1 for tid, s in c2_status.items() if s == 'pending' and hpd[tid] == 0)
print(f"\nStep 1 (initial): pending+hpd=0 = {baseline}")

# ===========================================================================
# Step 2: Rule 2 — orphan parent (pending parent, no_prior_defects,
#                                all children skipped) -> ok
# ===========================================================================
r2 = 0
for tid in list(c2_status.keys()):
    t = templates[tid]
    if t['parent_item_id'] is not None:
        continue
    if tid not in parents_with_kids:
        continue
    if c2_status[tid] != 'pending' or hpd[tid] != 0:
        continue
    kids = [c for c in parent_to_children.get(tid, []) if c in c2_status]
    if not kids:
        continue
    if all(c2_status[c] == 'skipped' for c in kids):
        c2_status[tid] = 'ok'
        r2 += 1
print(f"Rule 2 (orphan parents -> ok): {r2}")

# ===========================================================================
# Step 3: Rule 3 — pending children of pending top-level parents
#                  (parent hpd=0) -> ok
# ===========================================================================
r3 = 0
for tid in list(c2_status.keys()):
    t = templates[tid]
    if t['parent_item_id'] is None:
        continue
    if c2_status[tid] != 'pending' or hpd[tid] != 0:
        continue
    pid = t['parent_item_id']
    pt = templates.get(pid)
    if not pt or pt['parent_item_id'] is not None:
        continue  # parent must be top-level
    if c2_status.get(pid) == 'pending' and hpd.get(pid, 0) == 0:
        c2_status[tid] = 'ok'
        r3 += 1
print(f"Rule 3 (children of pending parents -> ok): {r3}")

# ===========================================================================
# Step 4: Rule 4 — all pending top-level parents with children
#                  (hpd=0) -> ok
# ===========================================================================
r4 = 0
for tid in list(c2_status.keys()):
    t = templates[tid]
    if t['parent_item_id'] is not None:
        continue
    if tid not in parents_with_kids:
        continue
    if c2_status[tid] != 'pending' or hpd[tid] != 0:
        continue
    c2_status[tid] = 'ok'
    r4 += 1
print(f"Rule 4 (all pending parents -> ok): {r4}")

# ===========================================================================
# Final: count remaining pending + hpd=0
# ===========================================================================
items = sum(1 for tid, s in c2_status.items() if s == 'pending' and hpd[tid] == 0)

# Defects + latents (same SQL as _desnag_progress)
d = cur.execute("""
    SELECT COUNT(*) as n FROM defect
    WHERE unit_id=? AND tenant_id=? AND raised_cycle_number < 2
    AND (status='open' OR (status='cleared' AND cleared_cycle_number = 2))
""", (UNIT_ID, TENANT_ID)).fetchone()['n']

l = cur.execute("""
    SELECT COUNT(*) as n FROM latent_area_note
    WHERE unit_id=? AND tenant_id=?
    AND (rectified_at IS NULL OR rectified_at_cycle_number = 2)
""", (UNIT_ID, TENANT_ID)).fetchone()['n']

print(f"\n========================================")
print(f"defects:  {d}")
print(f"latents:  {l}")
print(f"items:    {items}")
print(f"TOTAL:    {d + l + items}")
print(f"PWA:      198")
print(f"MATCH:    {d + l + items == 198}")
print(f"========================================")

conn.close()
