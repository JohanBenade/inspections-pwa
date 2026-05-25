"""Patch v310: Fix live monitor C2+ progress to match v308 Step 4 cohort.

The live monitor's C2+ block was built before Step 3 (latents) and Step 4
(newly-visible items) shipped. It currently measures progress as
"defects addressed / all prior-cycle defects" with three problems:

  1. Denominator includes prior-cycle defects already cleared in earlier
     cycles -- those need no action this cycle.
  2. B/fwd latents are not queried at all -- invisible to the dashboard.
  3. Newly-visible items (Step 4 cohort) are discarded by the override.

This patch makes 5 atomic edits in _build_live_monitor_data
(app/routes/batches.py), all assertion-guarded:

  A. Items area query: add `AND ii.has_prior_defects = 0` so the per-area
     items count matches Step 4's newly-visible cohort exactly.

  B. Initialize 6 new maps in the C2 tracking init block:
     - bfwd_action_map / bfwd_action_area_map (defects needing action)
     - latent_open_map / latent_open_area_map (open b/fwd latents)
     - latent_addressed_map / latent_addressed_area_map (latents acted on)

  C. Track bfwd_action_map inside the existing defect loop:
     defect needs action this cycle = status='open' OR cleared_cycle_id=current.

  D. Add a b/fwd latents query + loop after the inspection_defect chip loop.
     Builds latent_open_*_map (denominator) and latent_addressed_*_map
     (numerator) per the v308 Step 3 cohort definition.

  E. Rewrite the C2+ override block (lines ~1599-1631) so total/marked
     are the union of 3 cohorts:
         total  = items_total + open_b/fwd_latents + b/fwd_defects_needing_action
         marked = items_marked + latents_addressed + defects_addressed
     Areas list = union of areas from all 3 sources (fixes missing LOUNGE).
     Existing template-consumed keys (bfwd/cleared/new/open_now) keep
     their historical semantics; new breakdown fields added alongside.

Template impact: ZERO. All template-consumed keys keep semantics.
C1 path: COMPLETELY UNCHANGED. Every new code path gated by cycle>=2.

Run from repo root:
    python3 patch_v310_live_monitor_c2_fix.py
"""
import sys

PATH = 'app/routes/batches.py'


def apply(label, old, new, marker_for_skip):
    """Apply one find-replace operation with assertion + idempotency check."""
    with open(PATH, 'r') as f:
        content = f.read()
    if marker_for_skip in content:
        print(f'SKIP: {label} already applied to {PATH}')
        return
    count = content.count(old)
    assert count == 1, (
        f'{label}: OLD string found {count} times in {PATH} (expected 1). '
        f'Has a prior step in this script failed, or has the file drifted?'
    )
    new_content = content.replace(old, new)
    assert new in new_content, f'{label}: NEW string missing after replace'
    with open(PATH, 'w') as f:
        f.write(new_content)
    print(f'OK: {label} applied to {PATH}')


# ============================================================
# OP_A: items area query -- add has_prior_defects = 0 filter
# ============================================================
OLD_A = """            WHERE ii.inspection_id IN ({})
            AND ii.status != 'skipped'
            AND NOT (ii.status = 'ok' AND ii.marked_at IS NULL)
            GROUP BY i.unit_id, at2.area_name"""

NEW_A = """            WHERE ii.inspection_id IN ({})
            AND ii.status != 'skipped'
            AND NOT (ii.status = 'ok' AND ii.marked_at IS NULL)
            AND ii.has_prior_defects = 0
            GROUP BY i.unit_id, at2.area_name"""

# ============================================================
# OP_B: initialize 6 new maps in C2 tracking init block
# ============================================================
OLD_B = """    # --- C2 defect tracking: b/fwd (static), cleared (live), new (live) ---
    bfwd_map = {}
    bfwd_area_map = {}
    cleared_map = {}
    cleared_area_map = {}
    new_map = {}
    new_area_map = {}
    open_now_map = {}
    open_now_area_map = {}
    c2_units = [u for u in units if (u.get('cycle_number') or 1) >= 2]
    c2_unit_ids = [u['unit_id'] for u in c2_units]
    unit_cycle_num = {u['unit_id']: u.get('cycle_number', 1) for u in c2_units}
    addressed_map = {}
    addressed_area_map = {}"""

NEW_B = """    # --- C2 defect tracking: b/fwd (static), cleared (live), new (live) ---
    bfwd_map = {}
    bfwd_area_map = {}
    bfwd_action_map = {}        # b/fwd defects needing action this cycle (open + cleared-this-cycle)
    bfwd_action_area_map = {}
    cleared_map = {}
    cleared_area_map = {}
    new_map = {}
    new_area_map = {}
    open_now_map = {}
    open_now_area_map = {}
    c2_units = [u for u in units if (u.get('cycle_number') or 1) >= 2]
    c2_unit_ids = [u['unit_id'] for u in c2_units]
    unit_cycle_num = {u['unit_id']: u.get('cycle_number', 1) for u in c2_units}
    addressed_map = {}
    addressed_area_map = {}
    # --- B/fwd latents tracking (open + addressed this cycle) ---
    latent_open_map = {}
    latent_open_area_map = {}
    latent_addressed_map = {}
    latent_addressed_area_map = {}"""

# ============================================================
# OP_C: track bfwd_action_map inside defect loop
# ============================================================
OLD_C = """            if is_prior:
                # B/Fwd: prior-cycle defect, ANY status (static)
                bfwd_map[uid] = bfwd_map.get(uid, 0) + 1
                key = (uid, area)
                bfwd_area_map[key] = bfwd_area_map.get(key, 0) + 1
                # Cleared: prior defect cleared THIS cycle
                if r['status'] == 'cleared' and r['cleared_cycle_id'] == cyc:"""

NEW_C = """            if is_prior:
                # B/Fwd: prior-cycle defect, ANY status (static)
                bfwd_map[uid] = bfwd_map.get(uid, 0) + 1
                key = (uid, area)
                bfwd_area_map[key] = bfwd_area_map.get(key, 0) + 1
                # B/fwd needs action this cycle = currently open OR cleared this cycle
                if r['status'] == 'open' or (r['status'] == 'cleared' and r['cleared_cycle_id'] == cyc):
                    bfwd_action_map[uid] = bfwd_action_map.get(uid, 0) + 1
                    bfwd_action_area_map[key] = bfwd_action_area_map.get(key, 0) + 1
                # Cleared: prior defect cleared THIS cycle
                if r['status'] == 'cleared' and r['cleared_cycle_id'] == cyc:"""

# ============================================================
# OP_D: add latent query + loop after inspection_defect chip loop
# ============================================================
OLD_D = """        for r in [dict(x) for x in idef_raw]:
            uid = r['unit_id']
            area = r['area_name']
            cnt = r['cnt']
            new_map[uid] = new_map.get(uid, 0) + cnt
            new_area_map[(uid, area)] = new_area_map.get((uid, area), 0) + cnt
            open_now_map[uid] = open_now_map.get(uid, 0) + cnt
            open_now_area_map[(uid, area)] = open_now_area_map.get((uid, area), 0) + cnt

    # --- Batch started (earliest mark in entire batch) ---"""

NEW_D = """        for r in [dict(x) for x in idef_raw]:
            uid = r['unit_id']
            area = r['area_name']
            cnt = r['cnt']
            new_map[uid] = new_map.get(uid, 0) + cnt
            new_area_map[(uid, area)] = new_area_map.get((uid, area), 0) + cnt
            open_now_map[uid] = open_now_map.get(uid, 0) + cnt
            open_now_area_map[(uid, area)] = open_now_area_map.get((uid, area), 0) + cnt

        # --- B/fwd latents query (v308 Step 3 cohort) ---
        # Open b/fwd latent = raised in earlier cycle AND open at start of current cycle
        # Addressed this cycle = rectified_at_cycle_number=current
        #                        OR (addressed_cycle_number=current AND rectified_at IS NULL)
        latent_raw = query_db(\"\"\"
            SELECT lan.unit_id, lan.cycle_number AS raised_cycle_number,
                   lan.rectified_at, lan.rectified_at_cycle_number,
                   lan.addressed_cycle_number,
                   COALESCE(at2.area_name, lan.area_name_override, 'OTHER') AS area_name
            FROM latent_area_note lan
            LEFT JOIN area_template at2 ON lan.area_template_id = at2.id
            WHERE lan.unit_id IN ({}) AND lan.tenant_id = ?
        \"\"\".format(ph_od), c2_unit_ids + [tenant_id])
        for r in [dict(x) for x in latent_raw]:
            uid = r['unit_id']
            area = r['area_name']
            cyc_n = unit_cycle_num.get(uid)
            if cyc_n is None or (r['raised_cycle_number'] or 0) >= cyc_n:
                continue  # not a b/fwd latent for this unit's current cycle
            # Was it open at start of current cycle?
            if not (r['rectified_at'] is None or r['rectified_at_cycle_number'] == cyc_n):
                continue  # already rectified in an earlier cycle, no work needed
            latent_open_map[uid] = latent_open_map.get(uid, 0) + 1
            key = (uid, area)
            latent_open_area_map[key] = latent_open_area_map.get(key, 0) + 1
            # Addressed this cycle?
            if r['rectified_at_cycle_number'] == cyc_n or r['addressed_cycle_number'] == cyc_n:
                latent_addressed_map[uid] = latent_addressed_map.get(uid, 0) + 1
                latent_addressed_area_map[key] = latent_addressed_area_map.get(key, 0) + 1

    # --- Batch started (earliest mark in entire batch) ---"""

# ============================================================
# OP_E: rewrite C2+ override (3-cohort union)
# ============================================================
OLD_E = """        if (u.get('cycle_number') or 1) >= 2:
            for a in u['areas']:
                a['bfwd'] = bfwd_area_map.get((u['unit_id'], a['area']), 0)
                a['cleared'] = cleared_area_map.get((u['unit_id'], a['area']), 0)
                a['new'] = new_area_map.get((u['unit_id'], a['area']), 0)
                a['open_now'] = open_now_area_map.get((u['unit_id'], a['area']), 0)
        u['pct'] = round(u['total_marked'] / u['total_items'] * 100) if u['total_items'] else 0

        # C2+ de-snag: override progress from defects (not inspection_items)
        if (u.get('cycle_number') or 1) >= 2:
            uid = u['unit_id']
            u['total_items'] = bfwd_map.get(uid, 0)
            u['total_marked'] = addressed_map.get(uid, 0)
            u['pct'] = round(u['total_marked'] / u['total_items'] * 100) if u['total_items'] else 0
            c2_areas = []
            for aname in sorted(set(k[1] for k in bfwd_area_map if k[0] == uid)):
                bf = bfwd_area_map.get((uid, aname), 0)
                addr = addressed_area_map.get((uid, aname), 0)
                c2_areas.append({
                    'area': aname,
                    'total': bf,
                    'marked': addr,
                    'defects': open_now_area_map.get((uid, aname), 0),
                    'pct': round(addr / bf * 100) if bf else 0,
                    'duration': None,
                    'bfwd': bf,
                    'cleared': cleared_area_map.get((uid, aname), 0),
                    'new': new_area_map.get((uid, aname), 0),
                    'open_now': open_now_area_map.get((uid, aname), 0),
                })
            c2_areas.sort(key=lambda a: (area_order.get(a['area'], 10), a['area']))
            u['areas'] = c2_areas
            u['total_defects'] = sum(a['defects'] for a in c2_areas)"""

NEW_E = """        u['pct'] = round(u['total_marked'] / u['total_items'] * 100) if u['total_items'] else 0

        # C2+ de-snag: union of 3 cohorts (newly-visible items + open b/fwd latents + b/fwd defects needing action this cycle)
        if (u.get('cycle_number') or 1) >= 2:
            uid = u['unit_id']
            items_by_area = {a['area']: a for a in u['areas']}
            defect_areas_set = {area for (auid, area) in bfwd_action_area_map if auid == uid}
            latent_areas_set = {area for (auid, area) in latent_open_area_map if auid == uid}
            all_areas = set(items_by_area.keys()) | defect_areas_set | latent_areas_set
            c2_areas = []
            for aname in sorted(all_areas, key=lambda a: (area_order.get(a, 10), a)):
                item_a = items_by_area.get(aname, {})
                items_t = item_a.get('total', 0)
                items_m = item_a.get('marked', 0)
                defect_t = bfwd_action_area_map.get((uid, aname), 0)
                defect_m = addressed_area_map.get((uid, aname), 0)
                latent_t = latent_open_area_map.get((uid, aname), 0)
                latent_m = latent_addressed_area_map.get((uid, aname), 0)
                area_total = items_t + defect_t + latent_t
                area_marked = items_m + defect_m + latent_m
                c2_areas.append({
                    'area': aname,
                    'total': area_total,
                    'marked': area_marked,
                    'defects': open_now_area_map.get((uid, aname), 0),
                    'pct': round(area_marked / area_total * 100) if area_total else 0,
                    'duration': item_a.get('duration'),
                    'bfwd': bfwd_area_map.get((uid, aname), 0),
                    'cleared': cleared_area_map.get((uid, aname), 0),
                    'new': new_area_map.get((uid, aname), 0),
                    'open_now': open_now_area_map.get((uid, aname), 0),
                    'items_total': items_t,
                    'items_marked': items_m,
                    'latent_total': latent_t,
                    'latent_addressed': latent_m,
                    'defect_action_total': defect_t,
                    'defect_addressed': defect_m,
                })
            u['areas'] = c2_areas
            u['total_items'] = sum(a['total'] for a in c2_areas)
            u['total_marked'] = sum(a['marked'] for a in c2_areas)
            u['total_defects'] = sum(a['defects'] for a in c2_areas)
            u['pct'] = round(u['total_marked'] / u['total_items'] * 100) if u['total_items'] else 0"""


# Markers used for idempotency (chosen to be distinctive new strings introduced by each op)
MARKER_A = "AND ii.has_prior_defects = 0\n            GROUP BY i.unit_id, at2.area_name"
MARKER_B = "bfwd_action_map = {}"
MARKER_C = "B/fwd needs action this cycle = currently open OR cleared this cycle"
MARKER_D = "B/fwd latents query (v308 Step 3 cohort)"
MARKER_E = "C2+ de-snag: union of 3 cohorts"


def main():
    apply('OP_A items query filter', OLD_A, NEW_A, MARKER_A)
    apply('OP_B init new maps',        OLD_B, NEW_B, MARKER_B)
    apply('OP_C defect loop tracking', OLD_C, NEW_C, MARKER_C)
    apply('OP_D latent query + loop',  OLD_D, NEW_D, MARKER_D)
    apply('OP_E rewrite C2+ override', OLD_E, NEW_E, MARKER_E)
    print()
    print('All 5 operations applied. Verify with:')
    print('  python3 -c "import ast; ast.parse(open(\'app/routes/batches.py\').read()); print(\'AST clean\')"')
    print('  git --no-pager diff --stat app/routes/batches.py')


if __name__ == '__main__':
    main()
