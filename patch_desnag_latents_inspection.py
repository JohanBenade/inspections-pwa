#!/usr/bin/env python3
"""
Patch app/routes/inspection.py for Step 3: unified defect+latent rendering
in de-snag UI.

Changes:
1. desnag_view: add latent fetching, merge into areas dict, recompute totals
   with combined defect+latent counts. Rename total_bfwd to total_items in
   render_template call.
2. desnag_submit: extend unaddressed gate to also block on open latents.
3. _desnag_progress helper: return combined defect+latent counts.
4. _desnag_area_progress helper: return combined defect+latent counts per area.
5. NEW routes desnag_latent_address and desnag_latent_undo, inserted before
   desnag_submit (mirror the defect address/undo flow).
"""

PATH = 'app/routes/inspection.py'

with open(PATH, 'r') as f:
    content = f.read()

# ============================================================
# Change 1: desnag_view — latent loading + combined totals
# ============================================================

old_1 = '''    # Regression defects (raised this cycle)
    regressions = query_db("""
        SELECT d.id, d.defect_type, d.original_comment, d.status,
               d.item_template_id, it.item_description,
               ct.category_name, at2.area_name
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.unit_id = ? AND d.tenant_id = ?
          AND d.raised_cycle_number = ?
        ORDER BY at2.area_order, ct.category_order, it.item_order
    """, [unit_id, tenant_id, cycle_number])

    # Group by area -> category
    from collections import OrderedDict
    areas = OrderedDict()
    for d in list(bfwd_open) + list(bfwd_cleared):
        area = d['area_name']
        cat = d['category_name']
        if area not in areas:
            areas[area] = {'categories': OrderedDict(), 'total': 0, 'addressed': 0}
        if cat not in areas[area]['categories']:
            areas[area]['categories'][cat] = []
        areas[area]['categories'][cat].append(dict(d))
        areas[area]['total'] += 1
        if d['addressed_cycle_number'] == cycle_number:
            areas[area]['addressed'] += 1

    total_bfwd = len(bfwd_open) + len(bfwd_cleared)
    total_addressed = sum(1 for d in list(bfwd_open) + list(bfwd_cleared) if d['addressed_cycle_number'] == cycle_number)
    total_cleared = len(bfwd_cleared)
    total_still_open = sum(1 for d in bfwd_open if d['addressed_cycle_number'] == cycle_number)

    is_readonly = inspection['status'] in ('submitted', 'reviewed', 'approved', 'pending_followup', 'certified')
    can_submit = (total_bfwd > 0 and total_addressed == total_bfwd and not is_readonly)

    floor_label = FLOOR_LABELS.get(inspection['floor'], f"Floor {inspection['floor']}")

    return render_template('inspection/desnag.html',
        inspection=inspection,
        inspection_id=inspection_id,
        areas=areas,
        regressions=regressions,
        total_bfwd=total_bfwd,
        total_addressed=total_addressed,
        total_cleared=total_cleared,
        total_still_open=total_still_open,
        cycle_number=cycle_number,
        is_readonly=is_readonly,
        can_submit=can_submit,
        floor_label=floor_label)'''

new_1 = '''    # Regression defects (raised this cycle)
    regressions = query_db("""
        SELECT d.id, d.defect_type, d.original_comment, d.status,
               d.item_template_id, it.item_description,
               ct.category_name, at2.area_name
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.unit_id = ? AND d.tenant_id = ?
          AND d.raised_cycle_number = ?
        ORDER BY at2.area_order, ct.category_order, it.item_order
    """, [unit_id, tenant_id, cycle_number])

    # Latents: open + this-cycle rectified (mirrors bfwd_open/bfwd_cleared pattern)
    latents = query_db("""
        SELECT lan.id, lan.note_html, lan.cycle_number AS raised_cycle,
               lan.addressed_cycle_number, lan.rectified_at,
               lan.rectified_at_cycle_number,
               COALESCE(lan.area_name_override, at2.area_name) AS area_name,
               at2.area_order
        FROM latent_area_note lan
        LEFT JOIN area_template at2 ON lan.area_template_id = at2.id
        WHERE lan.unit_id = ? AND lan.tenant_id = ?
          AND (lan.rectified_at IS NULL OR lan.rectified_at_cycle_number = ?)
        ORDER BY at2.area_order, lan.created_at
    """, [unit_id, tenant_id, cycle_number])

    # Group by area -> category, with latents as a per-area subsection
    from collections import OrderedDict
    areas = OrderedDict()
    for d in list(bfwd_open) + list(bfwd_cleared):
        area = d['area_name']
        cat = d['category_name']
        if area not in areas:
            areas[area] = {'categories': OrderedDict(), 'latents': [], 'total': 0, 'addressed': 0}
        if cat not in areas[area]['categories']:
            areas[area]['categories'][cat] = []
        areas[area]['categories'][cat].append(dict(d))
        areas[area]['total'] += 1
        if d['addressed_cycle_number'] == cycle_number:
            areas[area]['addressed'] += 1

    for l in latents:
        area = l['area_name'] or 'OTHER'
        if area not in areas:
            areas[area] = {'categories': OrderedDict(), 'latents': [], 'total': 0, 'addressed': 0}
        areas[area]['latents'].append(dict(l))
        areas[area]['total'] += 1
        if l['addressed_cycle_number'] == cycle_number:
            areas[area]['addressed'] += 1

    # Combined totals (defects + latents). UI uses these for gates and progress.
    defect_count = len(bfwd_open) + len(bfwd_cleared)
    defect_addressed = sum(1 for d in list(bfwd_open) + list(bfwd_cleared) if d['addressed_cycle_number'] == cycle_number)
    defect_cleared = len(bfwd_cleared)
    defect_still_open = sum(1 for d in bfwd_open if d['addressed_cycle_number'] == cycle_number)

    latent_count = len(latents)
    latent_addressed = sum(1 for l in latents if l['addressed_cycle_number'] == cycle_number)
    latent_rectified = sum(1 for l in latents if l['rectified_at_cycle_number'] == cycle_number)
    latent_still_open = sum(1 for l in latents if l['addressed_cycle_number'] == cycle_number and l['rectified_at'] is None)

    total_items = defect_count + latent_count
    total_addressed = defect_addressed + latent_addressed
    total_cleared = defect_cleared + latent_rectified
    total_still_open = defect_still_open + latent_still_open

    is_readonly = inspection['status'] in ('submitted', 'reviewed', 'approved', 'pending_followup', 'certified')
    can_submit = (total_items > 0 and total_addressed == total_items and not is_readonly)

    floor_label = FLOOR_LABELS.get(inspection['floor'], f"Floor {inspection['floor']}")

    return render_template('inspection/desnag.html',
        inspection=inspection,
        inspection_id=inspection_id,
        areas=areas,
        regressions=regressions,
        total_items=total_items,
        total_addressed=total_addressed,
        total_cleared=total_cleared,
        total_still_open=total_still_open,
        cycle_number=cycle_number,
        is_readonly=is_readonly,
        can_submit=can_submit,
        floor_label=floor_label)'''

assert old_1 in content, "Change 1 anchor not found"
assert content.count(old_1) == 1, f"Change 1 anchor not unique: {content.count(old_1)}"
content = content.replace(old_1, new_1)
print("OK change 1: desnag_view augmented with latent loading and combined totals")

# ============================================================
# Change 2: desnag_submit gate — block on unaddressed latents too
# ============================================================

old_2 = '''    # Verify all b/fwd defects addressed
    unaddressed = query_db("""
        SELECT COUNT(*) as cnt FROM defect
        WHERE unit_id = ? AND tenant_id = ?
        AND raised_cycle_number < ?
        AND status = 'open' AND addressed_cycle_number IS NULL
    """, [inspection['unit_id'], tenant_id, inspection['cycle_number']], one=True)['cnt']

    if unaddressed > 0:
        abort(400)'''

new_2 = '''    # Verify all b/fwd defects AND open latents addressed at this cycle
    unaddressed_defects = query_db("""
        SELECT COUNT(*) as cnt FROM defect
        WHERE unit_id = ? AND tenant_id = ?
        AND raised_cycle_number < ?
        AND status = 'open' AND addressed_cycle_number IS NULL
    """, [inspection['unit_id'], tenant_id, inspection['cycle_number']], one=True)['cnt']

    unaddressed_latents = query_db("""
        SELECT COUNT(*) as cnt FROM latent_area_note
        WHERE unit_id = ? AND tenant_id = ?
        AND rectified_at IS NULL
        AND (addressed_cycle_number IS NULL OR addressed_cycle_number != ?)
    """, [inspection['unit_id'], tenant_id, inspection['cycle_number']], one=True)['cnt']

    if unaddressed_defects + unaddressed_latents > 0:
        abort(400)'''

assert old_2 in content, "Change 2 anchor not found"
assert content.count(old_2) == 1, f"Change 2 anchor not unique: {content.count(old_2)}"
content = content.replace(old_2, new_2)
print("OK change 2: desnag_submit gate extended to include unaddressed latents")

# ============================================================
# Change 3: _desnag_progress — combined defect+latent counts
# ============================================================

old_3 = '''def _desnag_progress(unit_id, tenant_id, cycle_number):
    """Calculate overall de-snag progress."""
    row = query_db("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN addressed_cycle_number = ? THEN 1 ELSE 0 END) as addressed,
            SUM(CASE WHEN status = 'cleared' AND addressed_cycle_number = ? THEN 1 ELSE 0 END) as cleared,
            SUM(CASE WHEN status = 'open' AND addressed_cycle_number = ? THEN 1 ELSE 0 END) as still_open
        FROM defect
        WHERE unit_id = ? AND tenant_id = ?
        AND raised_cycle_number < ?
        AND (status = 'open' OR (status = 'cleared' AND cleared_cycle_number = ?))
    """, [cycle_number, cycle_number, cycle_number, unit_id, tenant_id, cycle_number, cycle_number], one=True)
    return {
        'total': row['total'] or 0,
        'addressed': row['addressed'] or 0,
        'cleared': row['cleared'] or 0,
        'still_open': row['still_open'] or 0,
    }'''

new_3 = '''def _desnag_progress(unit_id, tenant_id, cycle_number):
    """Calculate overall de-snag progress (defects + latents combined)."""
    d_row = query_db("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN addressed_cycle_number = ? THEN 1 ELSE 0 END) as addressed,
            SUM(CASE WHEN status = 'cleared' AND addressed_cycle_number = ? THEN 1 ELSE 0 END) as cleared,
            SUM(CASE WHEN status = 'open' AND addressed_cycle_number = ? THEN 1 ELSE 0 END) as still_open
        FROM defect
        WHERE unit_id = ? AND tenant_id = ?
        AND raised_cycle_number < ?
        AND (status = 'open' OR (status = 'cleared' AND cleared_cycle_number = ?))
    """, [cycle_number, cycle_number, cycle_number, unit_id, tenant_id, cycle_number, cycle_number], one=True)
    l_row = query_db("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN addressed_cycle_number = ? THEN 1 ELSE 0 END) as addressed,
            SUM(CASE WHEN rectified_at_cycle_number = ? THEN 1 ELSE 0 END) as cleared,
            SUM(CASE WHEN addressed_cycle_number = ? AND rectified_at IS NULL THEN 1 ELSE 0 END) as still_open
        FROM latent_area_note
        WHERE unit_id = ? AND tenant_id = ?
        AND (rectified_at IS NULL OR rectified_at_cycle_number = ?)
    """, [cycle_number, cycle_number, cycle_number, unit_id, tenant_id, cycle_number], one=True)
    return {
        'total': (d_row['total'] or 0) + (l_row['total'] or 0),
        'addressed': (d_row['addressed'] or 0) + (l_row['addressed'] or 0),
        'cleared': (d_row['cleared'] or 0) + (l_row['cleared'] or 0),
        'still_open': (d_row['still_open'] or 0) + (l_row['still_open'] or 0),
    }'''

assert old_3 in content, "Change 3 anchor not found"
assert content.count(old_3) == 1, f"Change 3 anchor not unique: {content.count(old_3)}"
content = content.replace(old_3, new_3)
print("OK change 3: _desnag_progress now returns combined defect+latent counts")

# ============================================================
# Change 4: _desnag_area_progress — combined per-area counts
# ============================================================

old_4 = '''def _desnag_area_progress(unit_id, tenant_id, cycle_number, area_name):
    """Calculate de-snag progress for a specific area."""
    row = query_db("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN d.addressed_cycle_number = ? THEN 1 ELSE 0 END) as addressed
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.unit_id = ? AND d.tenant_id = ?
        AND d.raised_cycle_number < ?
        AND (d.status = 'open' OR (d.status = 'cleared' AND d.cleared_cycle_number = ?))
        AND at2.area_name = ?
    """, [cycle_number, unit_id, tenant_id, cycle_number, cycle_number, area_name], one=True)
    return {
        'total': row['total'] or 0,
        'addressed': row['addressed'] or 0,
    }'''

new_4 = '''def _desnag_area_progress(unit_id, tenant_id, cycle_number, area_name):
    """Calculate de-snag progress for a specific area (defects + latents)."""
    d_row = query_db("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN d.addressed_cycle_number = ? THEN 1 ELSE 0 END) as addressed
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.unit_id = ? AND d.tenant_id = ?
        AND d.raised_cycle_number < ?
        AND (d.status = 'open' OR (d.status = 'cleared' AND d.cleared_cycle_number = ?))
        AND at2.area_name = ?
    """, [cycle_number, unit_id, tenant_id, cycle_number, cycle_number, area_name], one=True)
    l_row = query_db("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN lan.addressed_cycle_number = ? THEN 1 ELSE 0 END) as addressed
        FROM latent_area_note lan
        LEFT JOIN area_template at2 ON lan.area_template_id = at2.id
        WHERE lan.unit_id = ? AND lan.tenant_id = ?
        AND (lan.rectified_at IS NULL OR lan.rectified_at_cycle_number = ?)
        AND COALESCE(lan.area_name_override, at2.area_name) = ?
    """, [cycle_number, unit_id, tenant_id, cycle_number, area_name], one=True)
    return {
        'total': (d_row['total'] or 0) + (l_row['total'] or 0),
        'addressed': (d_row['addressed'] or 0) + (l_row['addressed'] or 0),
    }'''

assert old_4 in content, "Change 4 anchor not found"
assert content.count(old_4) == 1, f"Change 4 anchor not unique: {content.count(old_4)}"
content = content.replace(old_4, new_4)
print("OK change 4: _desnag_area_progress extended to include latents per area")

# ============================================================
# Change 5: Add latent_address + latent_undo routes BEFORE desnag_submit
# ============================================================

anchor_5 = '''@inspection_bp.route('/<inspection_id>/desnag/submit', methods=['POST'])
@require_auth
def desnag_submit(inspection_id):'''

new_routes_5 = '''@inspection_bp.route('/<inspection_id>/desnag/latent_address', methods=['POST'])
@require_auth
def desnag_latent_address(inspection_id):
    tenant_id = session['tenant_id']
    latent_id = request.form.get('latent_id')
    action = request.form.get('action')

    inspection = query_db(
        "SELECT id, unit_id, cycle_id, cycle_number FROM inspection WHERE id=? AND tenant_id=?",
        [inspection_id, tenant_id], one=True)
    if not inspection:
        abort(404)

    db = get_db()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    cycle_number = inspection['cycle_number']

    if action == 'rectified':
        db.execute("""UPDATE latent_area_note SET
            rectified_at=?, rectified_at_cycle_id=?, rectified_at_cycle_number=?,
            addressed_cycle_number=?, last_edited_at=?
            WHERE id=? AND rectified_at IS NULL AND tenant_id=?""",
            [now, inspection['cycle_id'], cycle_number,
             cycle_number, now, latent_id, tenant_id])
    elif action == 'still_open':
        db.execute("""UPDATE latent_area_note SET
            addressed_cycle_number=?, last_edited_at=?
            WHERE id=? AND rectified_at IS NULL AND tenant_id=?""",
            [cycle_number, now, latent_id, tenant_id])
    db.commit()

    latent = query_db("""
        SELECT lan.id, lan.note_html, lan.cycle_number AS raised_cycle,
               lan.addressed_cycle_number, lan.rectified_at,
               lan.rectified_at_cycle_number,
               COALESCE(lan.area_name_override, at2.area_name) AS area_name
        FROM latent_area_note lan
        LEFT JOIN area_template at2 ON lan.area_template_id = at2.id
        WHERE lan.id = ? AND lan.tenant_id = ?
    """, [latent_id, tenant_id], one=True)

    progress = _desnag_progress(inspection['unit_id'], tenant_id, cycle_number)
    area_progress = _desnag_area_progress(inspection['unit_id'], tenant_id, cycle_number, latent['area_name'])

    return render_template('inspection/_desnag_latent.html',
        latent=latent, cycle_number=cycle_number, is_readonly=False,
        inspection_id=inspection_id,
        progress=progress, area_progress=area_progress, swap_oob=True)


@inspection_bp.route('/<inspection_id>/desnag/latent_undo', methods=['POST'])
@require_auth
def desnag_latent_undo(inspection_id):
    tenant_id = session['tenant_id']
    latent_id = request.form.get('latent_id')

    inspection = query_db(
        "SELECT id, unit_id, cycle_id, cycle_number FROM inspection WHERE id=? AND tenant_id=?",
        [inspection_id, tenant_id], one=True)
    if not inspection:
        abort(404)

    db = get_db()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    cycle_number = inspection['cycle_number']

    state = query_db(
        'SELECT rectified_at, rectified_at_cycle_number, addressed_cycle_number FROM latent_area_note WHERE id=? AND tenant_id=?',
        [latent_id, tenant_id], one=True)

    if state['rectified_at'] is not None and state['rectified_at_cycle_number'] == cycle_number:
        db.execute("""UPDATE latent_area_note SET
            rectified_at=NULL, rectified_at_cycle_id=NULL, rectified_at_cycle_number=NULL,
            rectified_by=NULL, rectified_by_role=NULL,
            addressed_cycle_number=NULL, last_edited_at=?
            WHERE id=? AND tenant_id=?""", [now, latent_id, tenant_id])
    elif state['rectified_at'] is None and state['addressed_cycle_number'] == cycle_number:
        db.execute("""UPDATE latent_area_note SET
            addressed_cycle_number=NULL, last_edited_at=?
            WHERE id=? AND tenant_id=?""", [now, latent_id, tenant_id])
    db.commit()

    latent = query_db("""
        SELECT lan.id, lan.note_html, lan.cycle_number AS raised_cycle,
               lan.addressed_cycle_number, lan.rectified_at,
               lan.rectified_at_cycle_number,
               COALESCE(lan.area_name_override, at2.area_name) AS area_name
        FROM latent_area_note lan
        LEFT JOIN area_template at2 ON lan.area_template_id = at2.id
        WHERE lan.id = ? AND lan.tenant_id = ?
    """, [latent_id, tenant_id], one=True)

    progress = _desnag_progress(inspection['unit_id'], tenant_id, cycle_number)
    area_progress = _desnag_area_progress(inspection['unit_id'], tenant_id, cycle_number, latent['area_name'])

    return render_template('inspection/_desnag_latent.html',
        latent=latent, cycle_number=cycle_number, is_readonly=False,
        inspection_id=inspection_id,
        progress=progress, area_progress=area_progress, swap_oob=True)


''' + anchor_5

assert anchor_5 in content, "Change 5 anchor not found"
assert content.count(anchor_5) == 1, f"Change 5 anchor not unique: {content.count(anchor_5)}"
content = content.replace(anchor_5, new_routes_5)
print("OK change 5: latent_address + latent_undo routes added before desnag_submit")

with open(PATH, 'w') as f:
    f.write(content)

print()
print("All 5 changes applied to", PATH)
