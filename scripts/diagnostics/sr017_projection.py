"""
sr017_projection.py

Projects the C2 de-snag cohort for every unit in batch SR-017 (3237ea51),
ranks them ascending by total cohort size, and prints CSV to stdout.

Cohort formula per unit (validated against unit 146 via v4):
    total = open_prior_defects + open_latents + projected_newly_visible_items

The projected items count mirrors app/routes/inspection.py L60-275:
    - Templates filtered by active=1
    - C2 initial status from C1 + exclusion + ground_only/floor logic
    - has_prior_defects flag from open C1 defects
    - Rules 2/3/4 applied in order (orphan-parent, carry-forward children,
      all-pending-parents flips)
    - Cohort = templates remaining at status='pending' AND has_prior_defects=0

Sanity check: unit 146 must show defects=144, latents=0, items=54, total=198.
"""
import sqlite3

TENANT_ID = 'MONOGRAPH'
BATCH_ID = '3237ea51'  # SR-017 22 May 2026

conn = sqlite3.connect('/var/data/inspections.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ==========================================================================
# PRELOAD all global data once (avoids per-unit re-queries)
# ==========================================================================

# All templates
all_templates = {}
for r in cur.execute(
        "SELECT id, parent_item_id, floor_condition, active "
        "FROM item_template WHERE tenant_id=?", (TENANT_ID,)).fetchall():
    all_templates[r['id']] = dict(r)
n_active = sum(1 for t in all_templates.values() if t['active'] == 1)
print(f"# item_template: {len(all_templates)} total, {n_active} active", flush=True)

# Parent -> children map (from ALL templates, including inactive)
parent_to_children = {}
for tid, t in all_templates.items():
    pid = t['parent_item_id']
    if pid:
        parent_to_children.setdefault(pid, []).append(tid)
parents_with_kids = set(parent_to_children.keys())

# C1 inspection_items grouped by unit_id
c1_items_by_unit = {}
for r in cur.execute("""
    SELECT i.unit_id, ii.item_template_id, ii.status
    FROM inspection_item ii
    JOIN inspection i ON ii.inspection_id = i.id
    WHERE i.tenant_id=? AND i.cycle_number=1
""", (TENANT_ID,)).fetchall():
    c1_items_by_unit.setdefault(r['unit_id'], {})[r['item_template_id']] = r['status']
print(f"# units with C1 data: {len(c1_items_by_unit)}", flush=True)

# Open prior defects (for has_prior_defects flag) grouped by unit_id
prior_defects_by_unit = {}
for r in cur.execute("""
    SELECT unit_id, item_template_id
    FROM defect
    WHERE tenant_id=? AND status='open' AND raised_cycle_number < 2
""", (TENANT_ID,)).fetchall():
    prior_defects_by_unit.setdefault(r['unit_id'], set()).add(r['item_template_id'])

# Defect counts per unit (for the _desnag_progress defect query)
defect_counts = {}
for r in cur.execute("""
    SELECT unit_id, COUNT(*) as n FROM defect
    WHERE tenant_id=? AND raised_cycle_number < 2
    AND (status='open' OR (status='cleared' AND cleared_cycle_number=2))
    GROUP BY unit_id
""", (TENANT_ID,)).fetchall():
    defect_counts[r['unit_id']] = r['n']

# Latent counts per unit
latent_counts = {}
for r in cur.execute("""
    SELECT unit_id, COUNT(*) as n FROM latent_area_note
    WHERE tenant_id=?
    AND (rectified_at IS NULL OR rectified_at_cycle_number=2)
    GROUP BY unit_id
""", (TENANT_ID,)).fetchall():
    latent_counts[r['unit_id']] = r['n']

# Exclusions: by exclusion_list_id
excl_by_list = {}
for r in cur.execute(
        "SELECT exclusion_list_id, item_template_id FROM exclusion_list_item").fetchall():
    excl_by_list.setdefault(r['exclusion_list_id'], set()).add(r['item_template_id'])

# Exclusions: by cycle_id (fallback)
excl_by_cycle = {}
for r in cur.execute(
        "SELECT cycle_id, item_template_id FROM cycle_excluded_item WHERE tenant_id=?",
        (TENANT_ID,)).fetchall():
    excl_by_cycle.setdefault(r['cycle_id'], set()).add(r['item_template_id'])

print(f"# preload done", flush=True)

# ==========================================================================
# PROJECTION FUNCTION (mirrors L60-275 of inspection.py)
# ==========================================================================
def project_unit_items(unit_id, cycle_id, excl_list_id, unit_floor):
    if excl_list_id and excl_list_id in excl_by_list:
        current_exclusions = excl_by_list[excl_list_id]
    elif cycle_id and cycle_id in excl_by_cycle:
        current_exclusions = excl_by_cycle[cycle_id]
    else:
        current_exclusions = set()

    prev_status = c1_items_by_unit.get(unit_id, {})
    prior_defect_set = prior_defects_by_unit.get(unit_id, set())

    c2_status = {}
    hpd = {}
    for tid, prev_s in prev_status.items():
        t = all_templates.get(tid)
        if not t or t['active'] != 1:
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

    # Rule 2: orphan parent
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

    # Rule 3: pending children of pending parents
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

    # Rule 4: all pending parents -> ok
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
    return items

# ==========================================================================
# ITERATE SR-017 batch_units and build the ranked list
# ==========================================================================
batch_units = cur.execute("""
    SELECT bu.unit_id, bu.cycle_id, bu.exclusion_list_id, bu.status as bu_status,
           u.unit_number, u.floor, u.block
    FROM batch_unit bu
    JOIN unit u ON bu.unit_id = u.id
    WHERE bu.batch_id=? AND bu.tenant_id=?
    AND (bu.removed_at IS NULL OR bu.status != 'removed')
""", (BATCH_ID, TENANT_ID)).fetchall()
print(f"# SR-017 batch_units (non-removed): {len(batch_units)}", flush=True)

results = []
for r in batch_units:
    unit_id = r['unit_id']
    cycle_id = r['cycle_id']
    excl_id = r['exclusion_list_id']
    try:
        floor = int(r['floor']) if r['floor'] is not None else 0
    except (ValueError, TypeError):
        floor = 0

    items = project_unit_items(unit_id, cycle_id, excl_id, floor)
    d = defect_counts.get(unit_id, 0)
    l = latent_counts.get(unit_id, 0)
    total = d + l + items

    results.append({
        'unit_id': unit_id,
        'unit_number': r['unit_number'],
        'block': r['block'] or '',
        'floor': floor,
        'bu_status': r['bu_status'] or '',
        'defects': d,
        'latents': l,
        'items': items,
        'total': total,
    })

# Sort ascending by total (easy targets first)
results.sort(key=lambda x: (x['total'], x['unit_number']))

# ==========================================================================
# OUTPUT
# ==========================================================================
print()
print("rank,unit_number,block,floor,bu_status,defects,latents,items,total")
for i, row in enumerate(results, start=1):
    print(f"{i},{row['unit_number']},{row['block']},{row['floor']},"
          f"{row['bu_status']},{row['defects']},{row['latents']},"
          f"{row['items']},{row['total']}")

# Sanity check at the end
print()
unit146 = next((x for x in results if x['unit_id'] == 'd41d75d0'), None)
if unit146:
    print(f"# Sanity: unit 146 ({unit146['unit_number']}): "
          f"defects={unit146['defects']} latents={unit146['latents']} "
          f"items={unit146['items']} total={unit146['total']}  "
          f"{'PASS' if unit146['total']==198 else 'FAIL (expected 198)'}")
else:
    print("# Sanity: unit 146 not found in SR-017 batch_units")

# Summary stats
totals = [r['total'] for r in results]
if totals:
    print(f"# Summary: {len(totals)} units  "
          f"min={min(totals)} max={max(totals)} "
          f"avg={sum(totals)/len(totals):.1f}")

conn.close()
