"""
sr017_projection_v2.py

Per-unit cycle-aware projection of SR-017 cohort.

v2 fixes vs v1:
1. Looks up each unit's cycle_number from inspection_cycle (not hardcoded 2)
2. Uses prev_inspection at cycle_number-1 for carry-forward (not always C1)
3. Defect/latent filters use unit's cycle_number (not hardcoded 2)
4. has_prior_defects uses raised_cycle_id != current_cycle_id (matches the code's UPDATE)
5. Handles cycle_number=1 fresh-start branch correctly
"""
import sqlite3

TENANT_ID = 'MONOGRAPH'
BATCH_ID = '3237ea51'  # SR-017

conn = sqlite3.connect('/var/data/inspections.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ==========================================================================
# GLOBAL PRELOADS
# ==========================================================================

# inspection_cycle: id -> {cycle_number, block, floor}
cycle_meta = {}
for r in cur.execute(
        "SELECT id, cycle_number, block, floor FROM inspection_cycle WHERE tenant_id=?",
        (TENANT_ID,)).fetchall():
    cycle_meta[r['id']] = dict(r)
print(f"# inspection_cycle rows: {len(cycle_meta)}", flush=True)

# all templates
all_templates = {}
for r in cur.execute(
        "SELECT id, parent_item_id, floor_condition, active FROM item_template WHERE tenant_id=?",
        (TENANT_ID,)).fetchall():
    all_templates[r['id']] = dict(r)
n_active = sum(1 for t in all_templates.values() if t['active'] == 1)
print(f"# item_template: {len(all_templates)} total, {n_active} active", flush=True)

# parent->children from ALL templates (rule 4 doesn't filter active for EXISTS check)
parent_to_children = {}
for tid, t in all_templates.items():
    pid = t['parent_item_id']
    if pid:
        parent_to_children.setdefault(pid, []).append(tid)
parents_with_kids = set(parent_to_children.keys())

# inspection_item statuses indexed by (unit_id, cycle_number) -> {template_id: status}
prev_items_by_unit_cycle = {}
for r in cur.execute("""
    SELECT i.unit_id, i.cycle_number, ii.item_template_id, ii.status
    FROM inspection_item ii
    JOIN inspection i ON ii.inspection_id = i.id
    WHERE i.tenant_id = ?
""", (TENANT_ID,)).fetchall():
    key = (r['unit_id'], r['cycle_number'])
    prev_items_by_unit_cycle.setdefault(key, {})[r['item_template_id']] = r['status']
print(f"# unit/cycle status groups: {len(prev_items_by_unit_cycle)}", flush=True)

# defects: by unit, with raised_cycle_id (for has_prior_defects)
defects_by_unit = {}  # unit_id -> list of dicts {template_id, raised_cycle_id, raised_cycle_number, status, cleared_cycle_number}
for r in cur.execute("""
    SELECT unit_id, item_template_id, raised_cycle_id, raised_cycle_number, status, cleared_cycle_number
    FROM defect WHERE tenant_id = ?
""", (TENANT_ID,)).fetchall():
    defects_by_unit.setdefault(r['unit_id'], []).append(dict(r))

# latents: by unit
latents_by_unit = {}
for r in cur.execute("""
    SELECT unit_id, rectified_at, rectified_at_cycle_number
    FROM latent_area_note WHERE tenant_id = ?
""", (TENANT_ID,)).fetchall():
    latents_by_unit.setdefault(r['unit_id'], []).append(dict(r))

# exclusions: by list and by cycle
excl_by_list = {}
for r in cur.execute(
        "SELECT exclusion_list_id, item_template_id FROM exclusion_list_item").fetchall():
    excl_by_list.setdefault(r['exclusion_list_id'], set()).add(r['item_template_id'])

excl_by_cycle = {}
for r in cur.execute(
        "SELECT cycle_id, item_template_id FROM cycle_excluded_item WHERE tenant_id=?",
        (TENANT_ID,)).fetchall():
    excl_by_cycle.setdefault(r['cycle_id'], set()).add(r['item_template_id'])

print("# preload done", flush=True)

# ==========================================================================
# PER-UNIT PROJECTION
# ==========================================================================
def project(unit_id, cycle_id, excl_list_id, unit_floor, cycle_number):
    """Returns (defects, latents, items) tuple matching _desnag_progress."""
    # ---- current_exclusions ----
    if excl_list_id and excl_list_id in excl_by_list:
        current_exclusions = excl_by_list[excl_list_id]
    elif cycle_id and cycle_id in excl_by_cycle:
        current_exclusions = excl_by_cycle[cycle_id]
    else:
        current_exclusions = set()

    # ---- prev_item_map ----
    prev_item_map = {}
    if cycle_number > 1:
        prev_key = (unit_id, cycle_number - 1)
        prev_item_map = prev_items_by_unit_cycle.get(prev_key, {})

    # ---- has_prior_defects: open defects raised in a DIFFERENT cycle_id ----
    prior_defect_set = set()
    for d in defects_by_unit.get(unit_id, []):
        if d['status'] == 'open' and d['raised_cycle_id'] != cycle_id:
            prior_defect_set.add(d['item_template_id'])

    # ---- Step 1: Initial C2+ status per template (active only) ----
    c2_status = {}
    hpd = {}

    # Iterate ALL active templates (matches `for t in templates` in code)
    for tid, t in all_templates.items():
        if t['active'] != 1:
            continue
        if tid in current_exclusions:
            s = 'skipped'
        elif t['floor_condition'] == 'ground_only' and unit_floor > 0:
            s = 'skipped'
        elif cycle_number > 1 and prev_item_map:
            # Carry-forward branch
            prev_s = prev_item_map.get(tid)
            if not prev_s or prev_s == 'pending':
                s = 'ok'
            elif prev_s == 'ok':
                s = 'ok'
            elif prev_s in ('not_to_standard', 'not_installed'):
                s = 'pending'
            elif prev_s == 'skipped':
                s = 'pending'
            else:
                s = 'pending'
        else:
            # Fresh-start branch (C1 OR no prev_inspection)
            prev_s = prev_item_map.get(tid)
            if prev_s:
                s = prev_s
            else:
                s = 'pending'
        c2_status[tid] = s
        hpd[tid] = 1 if tid in prior_defect_set else 0

    # ---- Rules 2/3/4 (only for cycle_number > 1, mirrors code) ----
    if cycle_number > 1:
        # Rule 2: orphan parents
        for tid in list(c2_status.keys()):
            t = all_templates[tid]
            if t['parent_item_id'] is not None:
                continue
            if tid not in parents_with_kids:
                continue
            if c2_status[tid] != 'pending' or hpd[tid] != 0:
                continue
            kids = [c for c in parent_to_children.get(tid, []) if c in c2_status]
            if all(c2_status[c] == 'skipped' for c in kids):
                c2_status[tid] = 'ok'

        # Rule 3: pending children of pending top-level parents
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

        # Rule 4: all pending top-level parents
        for tid in list(c2_status.keys()):
            t = all_templates[tid]
            if t['parent_item_id'] is not None:
                continue
            if tid not in parents_with_kids:
                continue
            if c2_status[tid] != 'pending' or hpd[tid] != 0:
                continue
            c2_status[tid] = 'ok'

    items = sum(1 for tid, s in c2_status.items() if s == 'pending' and hpd[tid] == 0)

    # ---- Defect count (matches _desnag_progress) ----
    d_count = 0
    for d in defects_by_unit.get(unit_id, []):
        if d['raised_cycle_number'] is None or d['raised_cycle_number'] >= cycle_number:
            continue
        if d['status'] == 'open':
            d_count += 1
        elif d['status'] == 'cleared' and d['cleared_cycle_number'] == cycle_number:
            d_count += 1

    # ---- Latent count ----
    l_count = 0
    for l in latents_by_unit.get(unit_id, []):
        if l['rectified_at'] is None:
            l_count += 1
        elif l['rectified_at_cycle_number'] == cycle_number:
            l_count += 1

    return d_count, l_count, items

# ==========================================================================
# ITERATE SR-017 batch_units
# ==========================================================================
batch_units = cur.execute("""
    SELECT bu.unit_id, bu.cycle_id, bu.exclusion_list_id, bu.status as bu_status,
           u.unit_number, u.floor, u.block
    FROM batch_unit bu
    JOIN unit u ON bu.unit_id = u.id
    WHERE bu.batch_id=? AND bu.tenant_id=?
      AND (bu.removed_at IS NULL OR bu.status != 'removed')
""", (BATCH_ID, TENANT_ID)).fetchall()
print(f"# SR-017 batch_units: {len(batch_units)}", flush=True)

results = []
unmatched_cycles = 0
for r in batch_units:
    unit_id = r['unit_id']
    cycle_id = r['cycle_id']
    excl_id = r['exclusion_list_id']
    try:
        floor = int(r['floor']) if r['floor'] is not None else 0
    except (ValueError, TypeError):
        floor = 0

    cm = cycle_meta.get(cycle_id)
    if not cm:
        unmatched_cycles += 1
        cycle_number = 2  # fallback (shouldn't happen)
    else:
        cycle_number = cm['cycle_number']

    d, l, items = project(unit_id, cycle_id, excl_id, floor, cycle_number)
    total = d + l + items

    results.append({
        'unit_id': unit_id,
        'unit_number': r['unit_number'],
        'block': r['block'] or '',
        'floor': floor,
        'bu_status': r['bu_status'] or '',
        'cycle_number': cycle_number,
        'defects': d,
        'latents': l,
        'items': items,
        'total': total,
    })

if unmatched_cycles:
    print(f"# WARNING: {unmatched_cycles} batch_units had no inspection_cycle row", flush=True)

# Filter pending only and sort
pending = [r for r in results if r['bu_status'] == 'pending']
pending.sort(key=lambda x: (x['total'], x['unit_number']))

print()
print("rank,unit_number,block,floor,cycle,defects,latents,items,total")
for i, row in enumerate(pending, start=1):
    print(f"{i},{row['unit_number']},{row['block']},{row['floor']},"
          f"C{row['cycle_number']},{row['defects']},{row['latents']},"
          f"{row['items']},{row['total']}")

# Distribution
print()
by_cycle = {}
for r in results:
    by_cycle.setdefault(r['cycle_number'], 0)
    by_cycle[r['cycle_number']] += 1
print(f"# All 114 units by cycle: {dict(sorted(by_cycle.items()))}")

# Pending stats
totals = [r['total'] for r in pending]
if totals:
    print(f"# Pending only: {len(totals)} units  min={min(totals)} max={max(totals)} avg={sum(totals)/len(totals):.1f}")

conn.close()
