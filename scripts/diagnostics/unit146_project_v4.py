"""
unit146_project_v4.py

v4 fixes over v3:
1. active=1 filter on templates iteration (matches app/routes/inspection.py L122)
2. parent_to_children built from ALL templates (rule 4 EXISTS does not filter active)
3. Rule 2 fires correctly when kids list is empty (vacuous all() = True)
4. cycle_excluded_item fallback when no exclusion list on inspection/batch_unit
5. Uses batch_unit row matched on cycle_id (matches L82-86 lookup)

Expected for unit 146: defects=144, latents=0, items=54, TOTAL=198
"""
import sqlite3

UNIT_ID = 'd41d75d0'
TENANT_ID = 'MONOGRAPH'

conn = sqlite3.connect('/var/data/inspections.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ---- Unit ----
unit = cur.execute("SELECT * FROM unit WHERE id=? AND tenant_id=?",
                   (UNIT_ID, TENANT_ID)).fetchone()
try:
    unit_floor = int(unit['floor']) if unit and unit['floor'] is not None else 0
except (ValueError, TypeError):
    unit_floor = 0
print(f"Unit {UNIT_ID}: floor={unit_floor} unit_number={unit['unit_number']}")

# ---- C1 inspections (sanity) ----
c1_insps = cur.execute(
    "SELECT id, status FROM inspection WHERE unit_id=? AND tenant_id=? AND cycle_number=1",
    (UNIT_ID, TENANT_ID)).fetchall()
print(f"C1 inspections on unit: {len(c1_insps)}")

# ---- Latest batch_unit (its cycle_id + excl_list_id) ----
bu = cur.execute("""
    SELECT bu.exclusion_list_id, bu.batch_id, bu.cycle_id
    FROM batch_unit bu
    JOIN inspection_batch ib ON bu.batch_id = ib.id
    WHERE bu.unit_id=? AND bu.tenant_id=?
    AND (bu.removed_at IS NULL OR bu.status != 'removed')
    ORDER BY ib.created_at DESC LIMIT 1
""", (UNIT_ID, TENANT_ID)).fetchone()
excl_id = bu['exclusion_list_id'] if bu else None
cycle_id = bu['cycle_id'] if bu else None
print(f"Latest batch_unit: batch={bu['batch_id'][:8] if bu else 'NONE'}"
      f"  cycle_id={cycle_id[:8] if cycle_id else 'NONE'}"
      f"  excl_list_id={excl_id}")

# ---- Resolve current_exclusions: try exclusion_list, fall back to cycle_excluded_item ----
current_exclusions = set()
if excl_id:
    rows = cur.execute(
        "SELECT item_template_id FROM exclusion_list_item WHERE exclusion_list_id=?",
        (excl_id,)).fetchall()
    current_exclusions = set(r['item_template_id'] for r in rows)
    print(f"current_exclusions (from exclusion_list): {len(current_exclusions)}")
elif cycle_id:
    rows = cur.execute(
        "SELECT item_template_id FROM cycle_excluded_item WHERE cycle_id=? AND tenant_id=?",
        (cycle_id, TENANT_ID)).fetchall()
    current_exclusions = set(r['item_template_id'] for r in rows)
    print(f"current_exclusions (from cycle_excluded_item fallback): {len(current_exclusions)}")
else:
    print("current_exclusions: 0 (no excl_list_id and no cycle_id)")

# ---- ALL templates (active flag included) ----
all_templates = {}
for r in cur.execute(
        "SELECT id, parent_item_id, floor_condition, active FROM item_template WHERE tenant_id=?",
        (TENANT_ID,)).fetchall():
    all_templates[r['id']] = dict(r)
n_active = sum(1 for t in all_templates.values() if t['active'] == 1)
print(f"item_template total: {len(all_templates)} (active={n_active}, inactive={len(all_templates)-n_active})")

# ---- parent_to_children from ALL templates (rule 4 EXISTS does not filter by active) ----
parent_to_children = {}
for tid, t in all_templates.items():
    pid = t['parent_item_id']
    if pid:
        parent_to_children.setdefault(pid, []).append(tid)
parents_with_kids = set(parent_to_children.keys())

# ---- C1 inspection_item statuses ----
c1_rows = cur.execute("""
    SELECT ii.item_template_id, ii.status
    FROM inspection_item ii
    JOIN inspection i ON ii.inspection_id = i.id
    WHERE i.unit_id=? AND i.tenant_id=? AND i.cycle_number=1
""", (UNIT_ID, TENANT_ID)).fetchall()
prev_status = {r['item_template_id']: r['status'] for r in c1_rows}
print(f"C1 inspection_items (unique by template): {len(prev_status)}")

# DIAGNOSTIC: inactive templates that still have C1 rows
c1_inactive = [tid for tid in prev_status
               if all_templates.get(tid, {}).get('active') != 1]
print(f"C1 templates now inactive (excluded from C2 by active=1 filter): {len(c1_inactive)}")
for tid in c1_inactive:
    print(f"   inactive template: {tid[:8]} C1_status={prev_status[tid]}")

# ---- has_prior_defects source ----
defect_tmpls = cur.execute("""
    SELECT DISTINCT item_template_id FROM defect
    WHERE unit_id=? AND tenant_id=? AND status='open' AND raised_cycle_number < 2
""", (UNIT_ID, TENANT_ID)).fetchall()
prior_defect_set = set(r['item_template_id'] for r in defect_tmpls)
print(f"templates with open prior defect: {len(prior_defect_set)}")

# ===========================================================================
# Step 1: Initial C2 status (active templates only)
# ===========================================================================
c2_status = {}
hpd = {}
for tid, prev_s in prev_status.items():
    t = all_templates.get(tid)
    if not t:
        continue
    if t['active'] != 1:
        continue  # KEY FIX v4: code's L122 templates query filters by active=1
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
print(f"\nStep 1 (initial active): pending+hpd=0 = {baseline}")

# ===========================================================================
# Step 2: Rule 2 — orphan parent
# ===========================================================================
r2 = 0
for tid in list(c2_status.keys()):
    t = all_templates[tid]
    if t['parent_item_id'] is not None:
        continue
    if tid not in parents_with_kids:
        continue
    if c2_status[tid] != 'pending' or hpd[tid] != 0:
        continue
    kids = [c for c in parent_to_children.get(tid, []) if c in c2_status]
    # all() of empty list is True (vacuous) — matches code: count of non-skipped = 0
    if all(c2_status[c] == 'skipped' for c in kids):
        c2_status[tid] = 'ok'
        r2 += 1
print(f"Rule 2 (orphan parents -> ok): {r2}")

# ===========================================================================
# Step 3: Rule 3 — pending children of pending parents
# ===========================================================================
r3 = 0
for tid in list(c2_status.keys()):
    t = all_templates[tid]
    if t['parent_item_id'] is None:
        continue
    if c2_status[tid] != 'pending' or hpd[tid] != 0:
        continue
    pid = t['parent_item_id']
    pt = all_templates.get(pid)
    if not pt or pt['parent_item_id'] is not None:
        continue
    if c2_status.get(pid) == 'pending' and hpd.get(pid, 0) == 0:
        c2_status[tid] = 'ok'
        r3 += 1
print(f"Rule 3 (children of pending parents -> ok): {r3}")

# ===========================================================================
# Step 4: Rule 4 — all pending parents -> ok
# ===========================================================================
r4 = 0
for tid in list(c2_status.keys()):
    t = all_templates[tid]
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
# Final
# ===========================================================================
items = sum(1 for tid, s in c2_status.items() if s == 'pending' and hpd[tid] == 0)

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
