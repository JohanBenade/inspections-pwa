"""
Batch routes - Operational batch management.
Create batches with unit numbers, auto-route to cycles, assign inspectors.
Access: Team Lead + Admin.
"""
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, session, redirect, url_for, abort, request, flash, make_response, jsonify
from app.auth import require_team_lead
from app.utils import generate_id
from app.utils.audit import log_audit
from app.services.db import get_db, query_db
import bleach

ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'b', 'i', 'u', 'ol', 'ul', 'li']

batches_bp = Blueprint('batches', __name__, url_prefix='/batches')

FLOOR_LABELS = {0: 'Ground', 1: '1st Floor', 2: '2nd Floor', 3: '3rd Floor'}


def _route_unit_to_cycle(cur, unit_id, block, floor, tenant_id, phase_id):
    """
    Auto-route a unit to the correct cycle based on inspection history.
    Returns (cycle_id, round_number, created_new_cycle).
    """
    row = cur.execute("""
        SELECT MAX(ic.cycle_number)
        FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.unit_id = ? AND i.tenant_id = ?
        AND i.status NOT IN ('not_started')
    """, (unit_id, tenant_id)).fetchone()

    round_number = (row[0] or 0) + 1

    cycle_row = cur.execute("""
        SELECT id FROM inspection_cycle
        WHERE block = ? AND floor = ? AND cycle_number = ? AND tenant_id = ?
    """, (block, floor, round_number, tenant_id)).fetchone()

    if cycle_row:
        return cycle_row[0], round_number, False

    prev_row = cur.execute("""
        SELECT id FROM inspection_cycle
        WHERE block = ? AND floor = ? AND tenant_id = ?
        ORDER BY cycle_number DESC LIMIT 1
    """, (block, floor, tenant_id)).fetchone()

    now = datetime.now(timezone.utc).isoformat()
    cycle_id = generate_id()
    cur.execute("""
        INSERT INTO inspection_cycle
        (id, tenant_id, phase_id, cycle_number, block, floor,
         created_by, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')
    """, (cycle_id, tenant_id, phase_id, round_number, block, floor,
          'admin', now))

    exclusions_copied = 0
    if prev_row:
        excls = cur.execute(
            "SELECT item_template_id, reason FROM cycle_excluded_item WHERE cycle_id = ?",
            (prev_row[0],)
        ).fetchall()
        for tmpl_id, reason in excls:
            eid = generate_id()
            cur.execute("""
                INSERT INTO cycle_excluded_item
                (id, tenant_id, cycle_id, item_template_id, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (eid, tenant_id, cycle_id, tmpl_id, reason, now))
            exclusions_copied += 1

    return cycle_id, round_number, True


@batches_bp.route('/validate-units', methods=['POST'])
@require_team_lead
def validate_units():
    """AJAX endpoint: validate unit numbers and return classification."""
    tenant_id = session['tenant_id']
    unit_input = request.form.get('units', '').strip()

    if not unit_input:
        return jsonify({'units': [], 'summary': {}})

    raw_numbers = []
    for part in unit_input.replace(',', ' ').replace(chr(10), ' ').split():
        part = part.strip()
        if part:
            raw_numbers.append(part.zfill(3))

    seen = set()
    unit_numbers = []
    for n in raw_numbers:
        if n not in seen:
            seen.add(n)
            unit_numbers.append(n)

    results = []
    for un in unit_numbers:
        row = query_db(
            "SELECT id, block, floor FROM unit WHERE unit_number = ? AND tenant_id = ?",
            [un, tenant_id], one=True)

        if not row:
            results.append({'unit_number': un, 'status': 'not_found'})
            continue

        # Check max completed cycle
        max_cycle = query_db("""
            SELECT MAX(ic.cycle_number) as mc
            FROM inspection i
            JOIN inspection_cycle ic ON i.cycle_id = ic.id
            WHERE i.unit_id = ? AND i.tenant_id = ?
            AND i.status NOT IN ('not_started')
        """, [row['id'], tenant_id], one=True)

        round_number = (max_cycle['mc'] or 0) + 1
        floor_label = FLOOR_LABELS.get(row['floor'], str(row['floor']))

        # Get open defect count
        defect_row = query_db(
            "SELECT COUNT(*) as cnt FROM defect WHERE unit_id = ? AND status = 'open'",
            [row['id']], one=True)

        results.append({
            'unit_number': un,
            'block': row['block'],
            'floor_label': floor_label,
            'round': round_number,
            'is_desnag': round_number > 1,
            'defects': defect_row['cnt'] or 0,
            'status': 'found',
        })

    c1 = sum(1 for r in results if r['status'] == 'found' and not r.get('is_desnag'))
    c2 = sum(1 for r in results if r['status'] == 'found' and r.get('is_desnag'))
    not_found = sum(1 for r in results if r['status'] == 'not_found')

    return jsonify({
        'units': results,
        'summary': {'c1': c1, 'c2': c2, 'not_found': not_found, 'total': len(results)}
    })


@batches_bp.route('/')
@require_team_lead
def list_batches():
    """List all batches."""
    tenant_id = session['tenant_id']

    batches_raw = query_db("""
        SELECT ib.id, ib.name, ib.status, ib.notes, ib.created_at,
            COUNT(bu.id) AS total_units,
            SUM(CASE WHEN i.status = 'submitted' THEN 1 ELSE 0 END) AS submitted,
            SUM(CASE WHEN i.status = 'reviewed' THEN 1 ELSE 0 END) AS reviewed,
            SUM(CASE WHEN i.status IN ('pending_followup','approved','certified','closed')
                THEN 1 ELSE 0 END) AS signed,
            SUM(CASE WHEN i.status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress,
            SUM(CASE WHEN i.status IS NULL OR i.status = 'not_started' THEN 1 ELSE 0 END) AS pending
        FROM inspection_batch ib
        LEFT JOIN batch_unit bu ON bu.batch_id = ib.id AND bu.status != 'removed'
        LEFT JOIN inspection i ON i.unit_id = bu.unit_id AND i.cycle_id = bu.cycle_id
        WHERE ib.tenant_id = ?
        GROUP BY ib.id
        ORDER BY ib.created_at DESC
    """, [tenant_id])
    batches = [dict(r) for r in batches_raw]

    # Status comes from DB (managed by approval flow)

    return render_template('batches/list.html', batches=batches)


@batches_bp.route('/new', methods=['GET', 'POST'])
@require_team_lead
def create_batch():
    """Create a new batch with auto-routing."""
    tenant_id = session['tenant_id']
    user_id = session['user_id']

    if request.method == 'POST':
        batch_name = request.form.get('name', '').strip()
        notes = request.form.get('notes', '').strip() or None
        unit_input = request.form.get('units', '').strip()
        exclusion_list_id = request.form.get('exclusion_list_id', '').strip() or None

        if not batch_name:
            batch_name = datetime.now().strftime('%Y-%m-%d')

        if not unit_input:
            flash('Enter at least one unit number.', 'error')
            excl_lists = [dict(r) for r in query_db("SELECT id, name, item_count FROM exclusion_list WHERE tenant_id = ? AND is_active = 1 ORDER BY created_at DESC", [tenant_id])]
            return render_template('batches/create.html', name=batch_name, notes=notes, excl_lists=excl_lists)

        raw_numbers = []
        for part in unit_input.replace(',', ' ').replace('\n', ' ').split():
            part = part.strip()
            if part:
                raw_numbers.append(part.zfill(3))

        if not raw_numbers:
            flash('No valid unit numbers found.', 'error')
            excl_lists = [dict(r) for r in query_db("SELECT id, name, item_count FROM exclusion_list WHERE tenant_id = ? AND is_active = 1 ORDER BY created_at DESC", [tenant_id])]
            return render_template('batches/create.html', name=batch_name, notes=notes, excl_lists=excl_lists)

        seen = set()
        unit_numbers = []
        for n in raw_numbers:
            if n not in seen:
                seen.add(n)
                unit_numbers.append(n)

        db = get_db()
        cur = db.cursor()
        now = datetime.now(timezone.utc).isoformat()

        phase = query_db(
            "SELECT id FROM phase WHERE tenant_id = ? LIMIT 1",
            [tenant_id], one=True)
        if not phase:
            abort(404)
        phase_id = phase['id']

        batch_id = generate_id()
        cur.execute("""
            INSERT INTO inspection_batch
            (id, tenant_id, name, notes, status, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'open', ?, ?, ?)
        """, (batch_id, tenant_id, batch_name, notes, user_id, now, now))

        results = []
        errors = []
        cycles_created = []

        for un in unit_numbers:
            unit_row = query_db(
                "SELECT id, block, floor FROM unit WHERE unit_number = ? AND tenant_id = ?",
                [un, tenant_id], one=True)

            if not unit_row:
                errors.append(un)
                continue

            unit_row = dict(unit_row)
            cycle_id, round_number, new_cycle = _route_unit_to_cycle(
                cur, unit_row['id'], unit_row['block'], unit_row['floor'],
                tenant_id, phase_id)

            if new_cycle:
                floor_label = FLOOR_LABELS.get(unit_row['floor'], str(unit_row['floor']))
                cycles_created.append(
                    '{} {} C{}'.format(unit_row['block'], floor_label, round_number))

            existing_bu = cur.execute(
                "SELECT id FROM batch_unit WHERE batch_id = ? AND unit_id = ?",
                (batch_id, unit_row['id'])).fetchone()
            if existing_bu:
                continue

            bu_id = generate_id()
            cur.execute("""
                INSERT INTO batch_unit
                (id, tenant_id, batch_id, unit_id, cycle_id, inspector_id, status, created_at, exclusion_list_id)
                VALUES (?, ?, ?, ?, ?, NULL, 'pending', ?, ?)
            """, (bu_id, tenant_id, batch_id, unit_row['id'], cycle_id, now, exclusion_list_id))

            floor_label = FLOOR_LABELS.get(unit_row['floor'], str(unit_row['floor']))
            results.append({
                'unit_number': un,
                'block': unit_row['block'],
                'floor_label': floor_label,
                'round': round_number,
                'is_re': round_number > 1,
            })

        log_audit(db, tenant_id, 'batch', batch_id, 'batch_created',
                  new_value=batch_name,
                  user_id=user_id, user_name=session['user_name'],
                  metadata='{{"units": {}}}'.format(len(results)))

        db.commit()

        msg = 'Batch "{}" created with {} units.'.format(batch_name, len(results))
        if cycles_created:
            msg += ' New cycles: {}.'.format(', '.join(sorted(set(cycles_created))))
        if errors:
            msg += ' Units not found: {}.'.format(', '.join(errors))
            flash(msg, 'error')
        else:
            flash(msg, 'success')

        return redirect(url_for('batches.detail', batch_id=batch_id))

    today = datetime.now().strftime('%Y-%m-%d')
    excl_lists = query_db(
        "SELECT id, name, item_count FROM exclusion_list WHERE tenant_id = ? AND is_active = 1 ORDER BY created_at DESC",
        [tenant_id])
    excl_lists = [dict(r) for r in excl_lists]
    return render_template('batches/create.html', name=today, notes='', excl_lists=excl_lists)


@batches_bp.route('/<batch_id>')
@require_team_lead
def detail(batch_id):
    """Batch detail - units with inspector assignment."""
    tenant_id = session['tenant_id']

    batch = query_db(
        "SELECT * FROM inspection_batch WHERE id = ? AND tenant_id = ?",
        [batch_id, tenant_id], one=True)
    if not batch:
        abort(404)
    batch = dict(batch)

    units_raw = query_db("""
        SELECT bu.id AS bu_id, COALESCE(i.status, 'not_started') AS bu_status, COALESCE(bu.inspector_id, i.inspector_id) AS inspector_id,
            bu.cycle_id, u.id AS unit_id, u.unit_number, u.block, u.floor,
            (SELECT cycle_number FROM inspection_cycle WHERE id = bu.cycle_id) AS cycle_number,
            i.id AS inspection_id, i.status AS inspection_status,
            COALESCE(insp.name, i.inspector_name) AS inspector_name,
            bu.exclusion_list_id
        FROM batch_unit bu
        JOIN unit u ON bu.unit_id = u.id
        LEFT JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = bu.cycle_id
        LEFT JOIN inspector insp ON bu.inspector_id = insp.id
        WHERE bu.batch_id = ? AND bu.tenant_id = ?
        AND bu.status != 'removed'
        ORDER BY u.block, u.floor, u.unit_number
    """, [batch_id, tenant_id])
    units = [dict(r) for r in units_raw]

    # --- Exclusion count + Checkpoints ---
    excl_count_map = {}
    if units:
        el_ids = list(set(u['exclusion_list_id'] for u in units if u.get('exclusion_list_id')))
        if el_ids:
            el_ph = ','.join(['?'] * len(el_ids))
            el_rows = query_db(f"""
                SELECT exclusion_list_id, COUNT(*) as cnt
                FROM exclusion_list_item
                WHERE exclusion_list_id IN ({el_ph})
                GROUP BY exclusion_list_id
            """, el_ids)
            excl_count_map = {r['exclusion_list_id']: r['cnt'] for r in el_rows}

    for u in units:
        el_count = excl_count_map.get(u.get('exclusion_list_id'), 0)
        ground_only_skips = 3 if (u.get('floor') or 0) > 0 else 0
        u['excl_count'] = el_count + ground_only_skips
        u['checkpoints_c1'] = 509 - u['excl_count']

    # --- Defect ledger columns (B/fwd, Cleared, New, Open) ---
    if units:
        d_unit_ids = list(set(u['unit_id'] for u in units))
        d_ph = ','.join(['?'] * len(d_unit_ids))
        d_rows = query_db(f"""
            SELECT unit_id, raised_cycle_number, cleared_cycle_number, status,
                   COUNT(*) as cnt
            FROM defect
            WHERE tenant_id = ? AND unit_id IN ({d_ph})
            GROUP BY unit_id, raised_cycle_number, cleared_cycle_number, status
        """, [tenant_id] + d_unit_ids)

        d_cn_map = {u['unit_id']: (u.get('cycle_number') or 1) for u in units}
        d_map = {}
        for dr in d_rows:
            d_uid = dr['unit_id']
            d_cn = d_cn_map.get(d_uid, 1)
            if d_uid not in d_map:
                d_map[d_uid] = {'defect_bfwd': 0, 'defect_cleared': 0, 'defect_new': 0, 'defect_open': 0}
            d_rcn = dr['raised_cycle_number'] or 1
            d_ccn = dr['cleared_cycle_number']
            if d_rcn < d_cn:
                d_map[d_uid]['defect_bfwd'] += dr['cnt']
            if d_rcn == d_cn:
                d_map[d_uid]['defect_new'] += dr['cnt']
            if d_ccn == d_cn:
                d_map[d_uid]['defect_cleared'] += dr['cnt']
            if dr['status'] == 'open':
                d_map[d_uid]['defect_open'] += dr['cnt']

        for u in units:
            u.update(d_map.get(u['unit_id'], {'defect_bfwd': 0, 'defect_cleared': 0, 'defect_new': 0, 'defect_open': 0}))

    # Set checkpoints: C1 = items after exclusions, C2+ = b/fwd defects
    for u in units:
        cn = u.get('cycle_number') or 1
        u['checkpoints'] = u['defect_bfwd'] if cn > 1 else u['checkpoints_c1']

    # --- Items marked (for live Inspecting progress) ---
    inspection_ids = [u.get('inspection_id') for u in units if u.get('inspection_id')]
    items_map = {}
    if inspection_ids:
        ii_ph = ','.join(['?'] * len(inspection_ids))
        ii_rows = query_db(f"""
            SELECT inspection_id,
                   SUM(CASE WHEN status NOT IN ('pending', 'skipped') THEN 1 ELSE 0 END) AS items_marked
            FROM inspection_item
            WHERE inspection_id IN ({ii_ph})
            GROUP BY inspection_id
        """, inspection_ids)
        items_map = {r['inspection_id']: (r['items_marked'] or 0) for r in ii_rows}

    for u in units:
        u['items_marked'] = items_map.get(u.get('inspection_id'), 0)

    # Removed units (separate section)
    removed_raw = query_db("""
        SELECT bu.id AS bu_id, bu.removed_at, bu.removed_by, bu.removed_reason,
               u.unit_number, u.block, u.floor,
               (SELECT cycle_number FROM inspection_cycle WHERE id = bu.cycle_id) AS cycle_number,
               COALESCE(insp.name, bu.removed_by) AS removed_by_name
        FROM batch_unit bu
        JOIN unit u ON bu.unit_id = u.id
        LEFT JOIN inspector insp ON bu.removed_by = insp.id
        WHERE bu.batch_id = ? AND bu.tenant_id = ?
        AND bu.status = 'removed'
        ORDER BY bu.removed_at DESC
    """, [batch_id, tenant_id])
    removed_units = [dict(r) for r in removed_raw]

    inspectors_raw = query_db("""
        SELECT id, name FROM inspector
        WHERE tenant_id = ? AND role IN ('inspector', 'team_lead', 'office_admin') AND active = 1
        ORDER BY name
    """, [tenant_id])
    inspectors = [dict(r) for r in inspectors_raw]

    # Distinct cycle IDs for exclusion management links
    cycle_ids = list(set(u['cycle_id'] for u in units))

    excl_lists = query_db(
        "SELECT id, name, item_count FROM exclusion_list WHERE tenant_id = ? AND is_active = 1 ORDER BY created_at DESC",
        [tenant_id])
    excl_lists = [dict(r) for r in excl_lists]

    refreshed_at = datetime.now().strftime('%H:%M:%S')
    return render_template('batches/detail.html',
                           batch=batch, units=units, inspectors=inspectors,
                           floor_labels=FLOOR_LABELS, cycle_ids=cycle_ids,
                           excl_lists=excl_lists,
                           removed_units=removed_units,
                           refreshed_at=refreshed_at)



@batches_bp.route('/<batch_id>/data')
@require_team_lead
def detail_data(batch_id):
    """HTMX partial: refreshable tbody + timestamp for batch detail."""
    tenant_id = session['tenant_id']

    batch_row = query_db(
        "SELECT * FROM inspection_batch WHERE id = ? AND tenant_id = ?",
        [batch_id, tenant_id], one=True)
    if not batch_row:
        abort(404)
    batch = dict(batch_row)

    units_raw = query_db("""
        SELECT bu.id AS bu_id, COALESCE(i.status, 'not_started') AS bu_status,
            COALESCE(bu.inspector_id, i.inspector_id) AS inspector_id,
            bu.cycle_id, u.id AS unit_id, u.unit_number, u.block, u.floor,
            (SELECT cycle_number FROM inspection_cycle WHERE id = bu.cycle_id) AS cycle_number,
            i.id AS inspection_id, i.status AS inspection_status,
            COALESCE(insp.name, i.inspector_name) AS inspector_name,
            bu.exclusion_list_id
        FROM batch_unit bu
        JOIN unit u ON bu.unit_id = u.id
        LEFT JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = bu.cycle_id
        LEFT JOIN inspector insp ON bu.inspector_id = insp.id
        WHERE bu.batch_id = ? AND bu.tenant_id = ?
        AND bu.status != 'removed'
        ORDER BY u.block, u.floor, u.unit_number
    """, [batch_id, tenant_id])
    units = [dict(r) for r in units_raw]

    excl_count_map = {}
    if units:
        el_ids = list(set(u['exclusion_list_id'] for u in units if u.get('exclusion_list_id')))
        if el_ids:
            el_ph = ','.join(['?'] * len(el_ids))
            el_rows = query_db(f"""
                SELECT exclusion_list_id, COUNT(*) as cnt
                FROM exclusion_list_item
                WHERE exclusion_list_id IN ({el_ph})
                GROUP BY exclusion_list_id
            """, el_ids)
            excl_count_map = {r['exclusion_list_id']: r['cnt'] for r in el_rows}

    for u in units:
        el_count = excl_count_map.get(u.get('exclusion_list_id'), 0)
        ground_only_skips = 3 if (u.get('floor') or 0) > 0 else 0
        u['excl_count'] = el_count + ground_only_skips
        u['checkpoints_c1'] = 509 - u['excl_count']

    if units:
        d_unit_ids = list(set(u['unit_id'] for u in units))
        d_ph = ','.join(['?'] * len(d_unit_ids))
        d_rows = query_db(f"""
            SELECT unit_id, raised_cycle_number, cleared_cycle_number, status, COUNT(*) as cnt
            FROM defect
            WHERE tenant_id = ? AND unit_id IN ({d_ph})
            GROUP BY unit_id, raised_cycle_number, cleared_cycle_number, status
        """, [tenant_id] + d_unit_ids)
        d_cn_map = {u['unit_id']: (u.get('cycle_number') or 1) for u in units}
        d_map = {}
        for dr in d_rows:
            d_uid = dr['unit_id']
            d_cn = d_cn_map.get(d_uid, 1)
            if d_uid not in d_map:
                d_map[d_uid] = {'defect_bfwd': 0, 'defect_cleared': 0, 'defect_new': 0, 'defect_open': 0}
            d_rcn = dr['raised_cycle_number'] or 1
            d_ccn = dr['cleared_cycle_number']
            if d_rcn < d_cn:
                d_map[d_uid]['defect_bfwd'] += dr['cnt']
            if d_rcn == d_cn:
                d_map[d_uid]['defect_new'] += dr['cnt']
            if d_ccn == d_cn:
                d_map[d_uid]['defect_cleared'] += dr['cnt']
            if dr['status'] == 'open':
                d_map[d_uid]['defect_open'] += dr['cnt']
        for u in units:
            u.update(d_map.get(u['unit_id'], {'defect_bfwd': 0, 'defect_cleared': 0, 'defect_new': 0, 'defect_open': 0}))

    for u in units:
        cn = u.get('cycle_number') or 1
        u['checkpoints'] = u['defect_bfwd'] if cn > 1 else u['checkpoints_c1']

    inspection_ids = [u.get('inspection_id') for u in units if u.get('inspection_id')]
    items_map = {}
    if inspection_ids:
        ii_ph = ','.join(['?'] * len(inspection_ids))
        ii_rows = query_db(f"""
            SELECT inspection_id,
                   SUM(CASE WHEN status NOT IN ('pending', 'skipped') THEN 1 ELSE 0 END) AS items_marked
            FROM inspection_item
            WHERE inspection_id IN ({ii_ph})
            GROUP BY inspection_id
        """, inspection_ids)
        items_map = {r['inspection_id']: (r['items_marked'] or 0) for r in ii_rows}
    for u in units:
        u['items_marked'] = items_map.get(u.get('inspection_id'), 0)

    inspectors_raw = query_db("""
        SELECT id, name FROM inspector
        WHERE tenant_id = ? AND role IN ('inspector', 'team_lead', 'office_admin') AND active = 1
        ORDER BY name
    """, [tenant_id])
    inspectors = [dict(r) for r in inspectors_raw]

    excl_lists = query_db(
        "SELECT id, name, item_count FROM exclusion_list WHERE tenant_id = ? AND is_active = 1 ORDER BY created_at DESC",
        [tenant_id])
    excl_lists = [dict(r) for r in excl_lists]

    refreshed_at = datetime.now().strftime('%H:%M:%S')

    return render_template('batches/_detail_tbody.html',
                           batch=batch,
                           units=units,
                           inspectors=inspectors,
                           excl_lists=excl_lists,
                           floor_labels=FLOOR_LABELS,
                           refreshed_at=refreshed_at,
                           is_partial_refresh=True)


@batches_bp.route('/<batch_id>/assign-exclusion-list', methods=['POST'])
@require_team_lead
def assign_exclusion_list(batch_id):
    """HTMX: assign exclusion list to a batch_unit and its inspection."""
    tenant_id = session['tenant_id']
    bu_id = request.form.get('bu_id')
    exclusion_list_id = request.form.get('exclusion_list_id') or None

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    db.execute(
        "UPDATE batch_unit SET exclusion_list_id = ? WHERE id = ? AND tenant_id = ?",
        [exclusion_list_id, bu_id, tenant_id])

    # Also update inspection if exists
    bu = db.execute(
        "SELECT unit_id, cycle_id FROM batch_unit WHERE id = ?", [bu_id]).fetchone()
    if bu:
        db.execute("""
            UPDATE inspection SET exclusion_list_id = ?, updated_at = ?
            WHERE unit_id = ? AND cycle_id = ? AND tenant_id = ?
        """, [exclusion_list_id, now, bu['unit_id'], bu['cycle_id'], tenant_id])

    db.commit()
    return f'<span class="text-xs text-green-600">Saved</span>'


@batches_bp.route('/<batch_id>/apply-exclusion-list-all', methods=['POST'])
@require_team_lead
def apply_exclusion_list_all(batch_id):
    """Bulk-apply exclusion list to all eligible units in batch."""
    tenant_id = session['tenant_id']
    exclusion_list_id = request.form.get('exclusion_list_id') or None

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    # Get all batch_units that haven't started inspection yet
    bus = db.execute("""
        SELECT bu.id, bu.unit_id, bu.cycle_id
        FROM batch_unit bu
        LEFT JOIN inspection i ON i.unit_id = bu.unit_id AND i.cycle_id = bu.cycle_id
        WHERE bu.batch_id = ? AND bu.tenant_id = ?
        AND bu.status != 'removed'
        AND (i.status IS NULL OR i.status IN ('not_started'))
    """, [batch_id, tenant_id]).fetchall()

    updated = 0
    for bu in bus:
        db.execute("UPDATE batch_unit SET exclusion_list_id = ? WHERE id = ? AND tenant_id = ?",
            [exclusion_list_id, bu['id'], tenant_id])
        db.execute("""UPDATE inspection SET exclusion_list_id = ?, updated_at = ?
            WHERE unit_id = ? AND cycle_id = ? AND tenant_id = ?""",
            [exclusion_list_id, now, bu['unit_id'], bu['cycle_id'], tenant_id])
        updated += 1

    db.commit()
    return redirect(url_for('batches.detail', batch_id=batch_id))


@batches_bp.route('/<batch_id>/exclusions')
@require_team_lead
def exclusions(batch_id):
    """Manage exclusions for a batch - inspection-style UI with area tabs."""
    tenant_id = session['tenant_id']

    batch = query_db(
        "SELECT * FROM inspection_batch WHERE id = ? AND tenant_id = ?",
        [batch_id, tenant_id], one=True)
    if not batch:
        abort(404)
    batch = dict(batch)

    # Get distinct cycles in this batch
    cycles = query_db("""
        SELECT DISTINCT ic.id as cycle_id, ic.block, ic.floor, ic.cycle_number
        FROM batch_unit bu
        JOIN inspection_cycle ic ON bu.cycle_id = ic.id
        WHERE bu.batch_id = ? AND bu.tenant_id = ?
        ORDER BY ic.block, ic.floor
    """, [batch_id, tenant_id])

    if not cycles:
        abort(404)

    cycle_id = cycles[0]['cycle_id']

    # Get unit_type
    unit = query_db("""
        SELECT u.unit_type FROM batch_unit bu
        JOIN unit u ON bu.unit_id = u.id
        WHERE bu.batch_id = ? LIMIT 1
    """, [batch_id], one=True)
    if not unit:
        abort(404)

    # Build area summary for tabs
    areas = query_db("""
        SELECT * FROM area_template
        WHERE tenant_id = ? AND unit_type = ?
        ORDER BY area_order
    """, [tenant_id, unit['unit_type']])

    total_items = 0
    total_excluded = 0
    area_tabs = []

    for area in areas:
        stats = query_db("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN cei.id IS NOT NULL THEN 1 ELSE 0 END) as excluded
            FROM item_template it
            LEFT JOIN cycle_excluded_item cei ON cei.item_template_id = it.id AND cei.cycle_id = ?
            JOIN category_template ct ON it.category_id = ct.id
            WHERE ct.area_id = ?
        """, [cycle_id, area['id']], one=True)

        a_total = stats['total'] or 0
        a_excluded = stats['excluded'] or 0
        total_items += a_total
        total_excluded += a_excluded

        area_tabs.append({
            'id': area['id'],
            'name': area['area_name'],
            'total': a_total,
            'excluded': a_excluded,
        })

    return render_template('batches/exclusions.html',
                           batch=batch, cycle_id=cycle_id,
                           area_tabs=area_tabs,
                           total_items=total_items,
                           total_excluded=total_excluded)


@batches_bp.route('/<batch_id>/exclusions/area/<area_id>')
@require_team_lead
def exclusions_area(batch_id, area_id):
    """HTMX partial: load exclusion items for one area."""
    tenant_id = session['tenant_id']

    batch = query_db(
        "SELECT * FROM inspection_batch WHERE id = ? AND tenant_id = ?",
        [batch_id, tenant_id], one=True)
    if not batch:
        abort(404)

    cycle_id = request.args.get('cycle_id')
    if not cycle_id:
        abort(400)

    categories = query_db("""
        SELECT * FROM category_template
        WHERE area_id = ?
        ORDER BY category_order
    """, [area_id])

    cat_list = []
    for cat in categories:
        items = query_db("""
            SELECT it.*,
                CASE WHEN cei.id IS NOT NULL THEN 1 ELSE 0 END as is_excluded,
                cei.reason as exclude_reason
            FROM item_template it
            LEFT JOIN cycle_excluded_item cei ON cei.item_template_id = it.id AND cei.cycle_id = ?
            WHERE it.category_id = ?
            ORDER BY it.item_order
        """, [cycle_id, cat['id']])

        cat_items = len(items)
        cat_excluded = sum(1 for i in items if i['is_excluded'])

        cat_list.append({
            'id': cat['id'],
            'name': cat['category_name'],
            'checklist': items,
            'total': cat_items,
            'excluded': cat_excluded,
        })

    return render_template('batches/_exclusion_area.html',
                           batch=batch, cycle_id=cycle_id,
                           categories=cat_list)




@batches_bp.route('/<batch_id>/exclusions/counts')
@require_team_lead
def exclusions_counts(batch_id):
    """HTMX partial: return updated exclusion counts for header + tabs."""
    tenant_id = session['tenant_id']
    cycle_id = request.args.get('cycle_id')
    if not cycle_id:
        abort(400)

    batch = query_db(
        "SELECT * FROM inspection_batch WHERE id = ? AND tenant_id = ?",
        [batch_id, tenant_id], one=True)
    if not batch:
        abort(404)

    unit = query_db("""
        SELECT u.unit_type FROM batch_unit bu
        JOIN unit u ON bu.unit_id = u.id
        WHERE bu.batch_id = ? LIMIT 1
    """, [batch_id], one=True)

    areas = query_db("""
        SELECT * FROM area_template
        WHERE tenant_id = ? AND unit_type = ?
        ORDER BY area_order
    """, [tenant_id, unit['unit_type']])

    total_items = 0
    total_excluded = 0
    area_tabs = []

    for area in areas:
        stats = query_db("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN cei.id IS NOT NULL THEN 1 ELSE 0 END) as excluded
            FROM item_template it
            LEFT JOIN cycle_excluded_item cei ON cei.item_template_id = it.id AND cei.cycle_id = ?
            JOIN category_template ct ON it.category_id = ct.id
            WHERE ct.area_id = ?
        """, [cycle_id, area['id']], one=True)

        a_total = stats['total'] or 0
        a_excluded = stats['excluded'] or 0
        total_items += a_total
        total_excluded += a_excluded

        area_tabs.append({
            'id': area['id'],
            'name': area['area_name'],
            'total': a_total,
            'excluded': a_excluded,
        })

    return render_template('batches/_exclusion_counts.html',
                           batch=batch, cycle_id=cycle_id,
                           area_tabs=area_tabs,
                           total_items=total_items,
                           total_excluded=total_excluded)


@batches_bp.route('/<batch_id>/save-exclusion-notes', methods=['POST'])
@require_team_lead
def save_exclusion_notes(batch_id):
    """AJAX: save exclusion notes from Manage Exclusions page."""
    tenant_id = session['tenant_id']
    import bleach
    ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'b', 'i', 'u', 'ol', 'ul', 'li']
    raw = request.form.get('exclusion_notes', '').strip()
    cleaned = bleach.clean(raw, tags=ALLOWED_TAGS, strip=True) if raw else None
    db = get_db()
    db.execute("UPDATE inspection_batch SET exclusion_notes = ?, updated_at = ? WHERE id = ? AND tenant_id = ?",
               [cleaned, datetime.now(timezone.utc).isoformat(), batch_id, tenant_id])
    db.commit()
    return '', 204

@batches_bp.route('/<batch_id>/edit', methods=['GET', 'POST'])
@require_team_lead
def edit_batch(batch_id):
    """Edit batch name, received_date, notes. Show audit trail."""
    tenant_id = session['tenant_id']

    batch = query_db(
        'SELECT * FROM inspection_batch WHERE id = ? AND tenant_id = ?',
        [batch_id, tenant_id], one=True)
    if not batch:
        abort(404)
    batch = dict(batch)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        received_date = request.form.get('received_date', '').strip() or None
        notes_raw = request.form.get('notes', '').strip()
        notes = bleach.clean(notes_raw, tags=ALLOWED_TAGS, strip=True) if notes_raw else None
        excl_notes_raw = request.form.get('exclusion_notes', '').strip()
        excl_notes = bleach.clean(excl_notes_raw, tags=ALLOWED_TAGS, strip=True) if excl_notes_raw else None

        if not name:
            flash('Batch name is required.', 'error')
            return render_template('batches/edit.html', batch=batch, milestones={})

        now = datetime.now(timezone.utc).isoformat()
        get_db().execute(
            'UPDATE inspection_batch SET name = ?, received_date = ?, notes = ?, exclusion_notes = ?, updated_at = ? WHERE id = ? AND tenant_id = ?',
            [name, received_date, notes, excl_notes, now, batch_id, tenant_id])
        get_db().commit()
        flash('Batch updated.', 'success')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    # Build audit trail milestones
    batch_started_row = query_db("""
        SELECT MIN(ii.marked_at) AS first_mark
        FROM inspection_item ii
        JOIN inspection i ON ii.inspection_id = i.id
        JOIN batch_unit bu ON bu.unit_id = i.unit_id AND bu.cycle_id = i.cycle_id
        WHERE bu.batch_id = ? AND bu.tenant_id = ?
        AND ii.marked_at IS NOT NULL AND ii.status NOT IN ('pending', 'skipped')
    """, [batch_id, tenant_id], one=True)
    batch_started = batch_started_row['first_mark'] if batch_started_row else None

    # Compute duration
    batch_duration = None
    if batch_started and batch.get('submitted_at'):
        try:
            from datetime import datetime as dt2
            s = batch_started.replace('Z', '+00:00')
            e = batch['submitted_at'].replace('Z', '+00:00')
            start_dt = dt2.fromisoformat(s)
            end_dt = dt2.fromisoformat(e)
            diff_secs = (end_dt - start_dt).total_seconds()
            if diff_secs > 0:
                h = int(diff_secs // 3600)
                m = int((diff_secs % 3600) // 60)
                batch_duration = '{}h {:02d}m'.format(h, m)
        except (ValueError, TypeError):
            pass

    milestones = {
        'received': batch.get('received_date'),
        'created': batch.get('created_at', '')[:10] if batch.get('created_at') else None,
        'first_inspection': _format_local_hhmm(batch_started) + ' ' + batch_started[:10] if batch_started else None,
        'submitted': batch.get('submitted_at', '')[:10] if batch.get('submitted_at') else None,
        'reviewed': batch.get('reviewed_at', '')[:10] if batch.get('reviewed_at') else None,
        'approved': batch.get('approved_at', '')[:10] if batch.get('approved_at') else None,
        'signed_off': batch.get('signed_off_at', '')[:10] if batch.get('signed_off_at') else None,
        'pushed': batch.get('pushed_at', '')[:10] if batch.get('pushed_at') else None,
        'closed': batch.get('closed_at', '')[:10] if batch.get('closed_at') else None,
        'duration': batch_duration,
    }

    return render_template('batches/edit.html', batch=batch, milestones=milestones)


@batches_bp.route('/<batch_id>/assign', methods=['POST'])
@require_team_lead
def assign_inspector(batch_id):
    """Assign inspector to a unit in this batch (HTMX). Creates CUA + inspection."""
    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    bu_id = request.form.get('bu_id')
    inspector_id = request.form.get('inspector_id')

    if not bu_id:
        return '', 400

    bu = query_db(
        "SELECT * FROM batch_unit WHERE id = ? AND batch_id = ? AND tenant_id = ?",
        [bu_id, batch_id, tenant_id], one=True)
    if not bu:
        return '', 404
    bu = dict(bu)

    if not inspector_id:
        db.execute("UPDATE batch_unit SET inspector_id = NULL, status = 'pending' WHERE id = ?",
                   [bu_id])
        db.execute(
            "DELETE FROM cycle_unit_assignment WHERE cycle_id = ? AND unit_id = ?",
            [bu['cycle_id'], bu['unit_id']])
        db.commit()
        return '<span class="text-xs text-gray-400">Unassigned</span>'

    inspector = query_db("SELECT name FROM inspector WHERE id = ?",
                         [inspector_id], one=True)
    if not inspector:
        return '', 404

    db.execute(
        "UPDATE batch_unit SET inspector_id = ?, status = 'assigned' WHERE id = ?",
        [inspector_id, bu_id])

    existing_cua = query_db(
        "SELECT id FROM cycle_unit_assignment WHERE cycle_id = ? AND unit_id = ?",
        [bu['cycle_id'], bu['unit_id']], one=True)
    if existing_cua:
        db.execute(
            "UPDATE cycle_unit_assignment SET inspector_id = ? WHERE id = ?",
            [inspector_id, existing_cua['id']])
    else:
        cua_id = generate_id()
        db.execute("""
            INSERT INTO cycle_unit_assignment
            (id, tenant_id, cycle_id, unit_id, inspector_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [cua_id, tenant_id, bu['cycle_id'], bu['unit_id'], inspector_id, now])

    existing_insp = query_db(
        "SELECT id FROM inspection WHERE unit_id = ? AND cycle_id = ? AND tenant_id = ?",
        [bu['unit_id'], bu['cycle_id'], tenant_id], one=True)
    if existing_insp:
        db.execute(
            "UPDATE inspection SET inspector_id = ?, inspector_name = ?, updated_at = ? WHERE id = ?",
            [inspector_id, inspector['name'], now, existing_insp['id']])
    else:
        insp_id = generate_id()
        today = datetime.now().strftime('%Y-%m-%d')
        cn_row = query_db("SELECT cycle_number FROM inspection_cycle WHERE id = ?", [bu['cycle_id']], one=True)
        cn = cn_row['cycle_number'] if cn_row else 1
        db.execute("""
            INSERT INTO inspection
            (id, tenant_id, unit_id, cycle_id, cycle_number, inspector_id, inspector_name,
             status, inspection_date, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'not_started', ?, ?, ?)
        """, [insp_id, tenant_id, bu['unit_id'], bu['cycle_id'], cn,
              inspector_id, inspector['name'], today, now, now])

    log_audit(db, tenant_id, 'batch', batch_id, 'inspector_assigned',
              new_value=inspector_id,
              user_id=session['user_id'], user_name=session['user_name'],
              metadata='{{"unit_id": "{}"}}'.format(bu['unit_id']))

    db.commit()

    from flask import make_response
    resp = make_response('<span class="text-xs text-green-600">{}</span>'.format(inspector['name']))
    resp.headers['HX-Refresh'] = 'true'
    return resp



@batches_bp.route('/<batch_id>/remove-confirm/<bu_id>')
@require_team_lead
def remove_confirm(batch_id, bu_id):
    """HTMX partial: inline confirmation strip for removing a unit."""
    tenant_id = session['tenant_id']
    bu = query_db("""
        SELECT bu.id AS bu_id, u.unit_number
        FROM batch_unit bu
        JOIN unit u ON bu.unit_id = u.id
        WHERE bu.id = ? AND bu.batch_id = ? AND bu.tenant_id = ?
    """, [bu_id, batch_id, tenant_id], one=True)
    if not bu:
        abort(404)
    return render_template('batches/_remove_confirm.html',
                           batch_id=batch_id, bu=dict(bu))


@batches_bp.route('/<batch_id>/add-units', methods=['POST'])
@require_team_lead
def add_units(batch_id):
    """Add units to an existing batch."""
    tenant_id = session['tenant_id']
    user_id = session['user_id']

    batch = query_db('SELECT id, name, status FROM inspection_batch WHERE id=? AND tenant_id=?',
        [batch_id, tenant_id], one=True)
    if not batch:
        abort(404)

    unit_input = request.form.get('units', '').strip()
    if not unit_input:
        flash('Enter at least one unit number.', 'error')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    exclusion_list_id = request.form.get('exclusion_list_id', '').strip() or None

    raw_numbers = []
    for part in unit_input.replace(',', ' ').replace(chr(10), ' ').split():
        part = part.strip()
        if part:
            raw_numbers.append(part.zfill(3))

    seen = set()
    unit_numbers = []
    for n in raw_numbers:
        if n not in seen:
            seen.add(n)
            unit_numbers.append(n)

    db = get_db()
    cur = db.cursor()
    now = datetime.now(timezone.utc).isoformat()

    phase = query_db('SELECT id FROM phase WHERE tenant_id=? LIMIT 1', [tenant_id], one=True)
    if not phase:
        abort(404)

    results = []
    errors = []
    skipped = []

    for un in unit_numbers:
        unit_row = query_db('SELECT id, block, floor FROM unit WHERE unit_number=? AND tenant_id=?',
            [un, tenant_id], one=True)
        if not unit_row:
            errors.append(un)
            continue

        unit_row = dict(unit_row)
        existing = cur.execute(
            'SELECT id FROM batch_unit WHERE batch_id=? AND unit_id=? AND removed_at IS NULL',
            (batch_id, unit_row['id'])).fetchone()
        if existing:
            skipped.append(un)
            continue

        cycle_id, round_number, new_cycle = _route_unit_to_cycle(
            cur, unit_row['id'], unit_row['block'], unit_row['floor'],
            tenant_id, phase['id'])

        bu_id = generate_id()
        cur.execute("""INSERT INTO batch_unit
            (id, tenant_id, batch_id, unit_id, cycle_id, inspector_id, status, created_at, exclusion_list_id)
            VALUES (?, ?, ?, ?, ?, NULL, 'pending', ?, ?)""",
            (bu_id, tenant_id, batch_id, unit_row['id'], cycle_id, now, exclusion_list_id))
        results.append(un)

    db.commit()

    msg = '{} units added.'.format(len(results))
    if skipped:
        msg += ' {} already in batch.'.format(len(skipped))
    if errors:
        msg += ' Not found: {}.'.format(', '.join(errors))
        flash(msg, 'error')
    else:
        flash(msg, 'success')

    return redirect(url_for('batches.detail', batch_id=batch_id))


@batches_bp.route('/<batch_id>/remove-unit', methods=['POST'])
@require_team_lead
def remove_unit(batch_id):
    """Remove a unit from this batch (not_started/pending/assigned only)."""
    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    bu_id = request.form.get('bu_id')
    reason = request.form.get('reason', '').strip() or None

    if not bu_id:
        return '', 400

    bu = query_db(
        "SELECT * FROM batch_unit WHERE id = ? AND batch_id = ? AND tenant_id = ?",
        [bu_id, batch_id, tenant_id], one=True)
    if not bu:
        abort(404)
    bu = dict(bu)

    # Only allow removal for not-yet-started units
    allowed = ('not_started', 'pending', 'assigned')
    insp = query_db(
        "SELECT id, status FROM inspection WHERE unit_id = ? AND cycle_id = ? AND tenant_id = ?",
        [bu['unit_id'], bu['cycle_id'], tenant_id], one=True)
    insp_status = insp['status'] if insp else 'not_started'

    if bu['status'] not in allowed and insp_status not in ('not_started',):
        flash('Cannot remove a unit that is already in progress.', 'error')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    if bu['status'] == 'removed':
        flash('Unit already removed.', 'error')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    # Get unit number for flash message
    unit = query_db("SELECT unit_number FROM unit WHERE id = ?", [bu['unit_id']], one=True)
    unit_number = unit['unit_number'] if unit else bu['unit_id']

    # Clean up not_started inspection + CUA
    if insp and insp['status'] == 'not_started':
        db.execute("DELETE FROM inspection_item WHERE inspection_id = ?", [insp['id']])
        db.execute("DELETE FROM inspection WHERE id = ?", [insp['id']])
        db.execute(
            "DELETE FROM cycle_unit_assignment WHERE cycle_id = ? AND unit_id = ?",
            [bu['cycle_id'], bu['unit_id']])

    # Mark batch_unit as removed
    db.execute("""
        UPDATE batch_unit
        SET status = 'removed', removed_at = ?, removed_by = ?, removed_reason = ?
        WHERE id = ?
    """, [now, session['user_id'], reason, bu_id])

    log_audit(db, tenant_id, 'batch', batch_id, 'unit_removed',
              new_value=unit_number,
              user_id=session['user_id'], user_name=session['user_name'],
              metadata='{{"unit": "{}", "reason": "{}"}}'.format(
                  unit_number, reason or ''))

    db.commit()

    flash('Unit {} removed from batch.'.format(unit_number), 'success')
    return redirect(url_for('batches.detail', batch_id=batch_id))


# ============================================================
# LIVE MONITOR V2
# ============================================================

# SAST offset: South Africa is always UTC+2, no DST
SAST_OFFSET = timedelta(hours=2)


def _get_defect_thresholds(tenant_id):
    """Calculate Q1/Q3 defect thresholds from all completed inspections."""
    rows = query_db("""
        SELECT COUNT(d.id) AS defect_count
        FROM inspection i
        JOIN unit u ON i.unit_id = u.id
        LEFT JOIN defect d ON d.unit_id = u.id AND d.raised_cycle_id = i.cycle_id
            AND d.status = 'open' AND d.tenant_id = i.tenant_id
        WHERE i.tenant_id = ? AND i.status IN ('submitted','reviewed','approved')
        GROUP BY u.id
        ORDER BY defect_count
    """, [tenant_id])
    counts = [dict(r)['defect_count'] for r in rows]
    if len(counts) < 4:
        return 20, 47
    q1 = counts[len(counts) // 4]
    q3 = counts[3 * len(counts) // 4]
    return q1, q3


def _get_initials(name):
    """Get 2-letter initials from a full name."""
    if not name:
        return '??'
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper()


def _get_severity(defect_count, threshold_low, threshold_high):
    """Assign severity color key based on defect count."""
    if defect_count <= threshold_low:
        return 'green'
    elif defect_count <= threshold_high:
        return 'gold'
    else:
        return 'red'


def _parse_iso(ts):
    """Parse ISO timestamp string to timezone-aware datetime. Returns None on failure."""
    if not ts:
        return None
    try:
        s = ts.replace('Z', '+00:00')
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError, TypeError):
        return None


def _minutes_between(start_iso, end_iso):
    """Calculate whole minutes between two ISO timestamp strings."""
    start = _parse_iso(start_iso)
    end = _parse_iso(end_iso)
    if not start or not end:
        return None
    secs = (end - start).total_seconds()
    return max(1, int(secs / 60))


def _format_local_hhmm(iso_str):
    """Format ISO timestamp as HH:MM in SAST (UTC+2)."""
    dt = _parse_iso(iso_str)
    if not dt:
        return None
    local = dt + SAST_OFFSET
    return local.strftime('%H:%M')


def _build_live_monitor_data(batch_id, tenant_id):
    """Build all data needed for Live Monitor V2 display."""
    batch = query_db(
        "SELECT * FROM inspection_batch WHERE id = ? AND tenant_id = ?",
        [batch_id, tenant_id], one=True)
    if not batch:
        return None
    batch = dict(batch)

    # --- Defect thresholds from historical data ---
    threshold_low, threshold_high = _get_defect_thresholds(tenant_id)

    # --- Units in batch ---
    units_raw = query_db("""
        SELECT bu.id AS bu_id, bu.inspector_id, bu.unit_id, bu.cycle_id,
               u.unit_number, u.block, u.floor,
               COALESCE(i.status, 'not_started') AS insp_status,
               i.id AS inspection_id,
               i.started_at, i.submitted_at,
               (SELECT cycle_number FROM inspection_cycle WHERE id = bu.cycle_id) AS cycle_number,
               COALESCE(insp.name, i.inspector_name) AS inspector_name
        FROM batch_unit bu
        JOIN unit u ON bu.unit_id = u.id
        LEFT JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = bu.cycle_id
        LEFT JOIN inspector insp ON bu.inspector_id = insp.id
        WHERE bu.batch_id = ? AND bu.tenant_id = ?
        AND bu.status != 'removed'
        ORDER BY u.unit_number
    """, [batch_id, tenant_id])
    units = [dict(r) for r in units_raw]

    total_units = len(units)
    units_complete = sum(1 for u in units if u['insp_status'] in ('submitted', 'reviewed', 'approved'))
    units_in_progress = sum(1 for u in units if u['insp_status'] == 'in_progress')
    units_not_started = sum(1 for u in units if u['insp_status'] == 'not_started')

    # --- Collect all inspection_ids for batch queries ---
    inspection_ids = [u['inspection_id'] for u in units if u['inspection_id']]

    items_marked = 0
    total_items = 0
    defects_found = 0

    # Lookup dicts built from batch queries
    unit_timing_map = {}      # inspection_id -> {started, ended}
    last_activity_map = {}    # inspection_id -> last_mark ISO string
    area_progress = {}        # unit_id -> [area dicts]

    if inspection_ids:
        ph = ','.join('?' * len(inspection_ids))

        # --- Items marked / total ---
        row = query_db("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status NOT IN ('pending','skipped') THEN 1 ELSE 0 END) AS marked
            FROM inspection_item WHERE inspection_id IN ({})
            AND NOT (status = 'ok' AND marked_at IS NULL)
        """.format(ph), inspection_ids, one=True)
        if row:
            row = dict(row)
            total_items = row['total'] or 0
            items_marked = row['marked'] or 0

        # --- Defects from defect table (batch KPI) ---
        unit_ids = [u['unit_id'] for u in units]
        cycle_ids = list(set(u['cycle_id'] for u in units))
        ph_u = ','.join('?' * len(unit_ids))
        ph_c = ','.join('?' * len(cycle_ids))
        d_row = query_db("""
            SELECT COUNT(*) AS cnt FROM defect
            WHERE unit_id IN ({}) AND raised_cycle_id IN ({})
            AND tenant_id = ? AND status = 'open'
        """.format(ph_u, ph_c), unit_ids + cycle_ids + [tenant_id], one=True)
        defects_found = dict(d_row)['cnt'] if d_row else 0

        # --- Per-unit timing (batch query, no N+1) ---
        timing_raw = query_db("""
            SELECT inspection_id,
                   MIN(marked_at) AS started,
                   MAX(marked_at) AS ended
            FROM inspection_item
            WHERE inspection_id IN ({})
            AND marked_at IS NOT NULL AND status NOT IN ('pending','skipped')
            GROUP BY inspection_id
        """.format(ph), inspection_ids)
        for r in [dict(x) for x in timing_raw]:
            unit_timing_map[r['inspection_id']] = {
                'started': r['started'],
                'ended': r['ended'],
            }
            # Also populate last_activity per inspection
            last_activity_map[r['inspection_id']] = r['ended']

        # --- Area progress with timing (enhanced) ---
        area_raw = query_db("""
            SELECT i.unit_id, at2.area_name,
                   COUNT(ii.id) AS total,
                   SUM(CASE WHEN ii.status NOT IN ('pending','skipped') THEN 1 ELSE 0 END) AS marked,
                   SUM(CASE WHEN ii.status IN ('not_to_standard','not_installed') THEN 1 ELSE 0 END) AS defects,
                   MIN(CASE WHEN ii.status NOT IN ('pending','skipped') THEN ii.marked_at END) AS area_started,
                   MAX(CASE WHEN ii.status NOT IN ('pending','skipped') THEN ii.marked_at END) AS area_ended
            FROM inspection_item ii
            JOIN inspection i ON ii.inspection_id = i.id
            JOIN item_template it ON ii.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at2 ON ct.area_id = at2.id
            WHERE ii.inspection_id IN ({})
            AND ii.status != 'skipped'
            AND NOT (ii.status = 'ok' AND ii.marked_at IS NULL)
            GROUP BY i.unit_id, at2.area_name
            ORDER BY at2.area_name
        """.format(ph), inspection_ids)
        for r in [dict(x) for x in area_raw]:
            uid = r['unit_id']
            if uid not in area_progress:
                area_progress[uid] = []
            pct = round(r['marked'] / r['total'] * 100) if r['total'] else 0
            area_dur = None
            if pct >= 100 and r['area_started'] and r['area_ended']:
                area_dur = _minutes_between(r['area_started'], r['area_ended'])
            area_progress[uid].append({
                'area': r['area_name'],
                'total': r['total'],
                'marked': r['marked'] or 0,
                'defects': r['defects'] or 0,
                'pct': pct,
                'duration': area_dur,
            })

        # --- Overlay defect table counts for submitted units ---
        # In-progress: keep inspection_item counts (real-time, updates on tap)
        # Submitted+: use defect table (accurate, one item can have multiple defects)
        submitted_uids = set(u['unit_id'] for u in units
                             if u['insp_status'] in ('submitted', 'reviewed', 'approved'))
        if submitted_uids:
            sub_list = list(submitted_uids)
            ph_su = ','.join('?' * len(sub_list))
            sub_cycles = list(set(u['cycle_id'] for u in units
                                  if u['unit_id'] in submitted_uids))
            ph_sc = ','.join('?' * len(sub_cycles))
            defect_area_raw = query_db("""
                SELECT d.unit_id, at2.area_name, COUNT(d.id) AS defect_count
                FROM defect d
                JOIN item_template it ON d.item_template_id = it.id
                JOIN category_template ct ON it.category_id = ct.id
                JOIN area_template at2 ON ct.area_id = at2.id
                WHERE d.unit_id IN ({}) AND d.raised_cycle_id IN ({})
                AND d.tenant_id = ? AND d.status = 'open'
                GROUP BY d.unit_id, at2.area_name
            """.format(ph_su, ph_sc), sub_list + sub_cycles + [tenant_id])
            defect_area_map = {}
            for r in [dict(x) for x in defect_area_raw]:
                defect_area_map[(r['unit_id'], r['area_name'])] = r['defect_count']
            for uid in submitted_uids:
                if uid in area_progress:
                    for area_dict in area_progress[uid]:
                        key = (uid, area_dict['area'])
                        if key in defect_area_map:
                            area_dict['defects'] = defect_area_map[key]

    # Sort areas: Kitchen, Lounge, Bathroom, then Bedrooms
    area_order = {'KITCHEN': 0, 'LOUNGE': 1, 'BATHROOM': 2}
    for uid in area_progress:
        area_progress[uid].sort(key=lambda a: (area_order.get(a['area'], 10), a['area']))

    # --- C2 defect tracking: b/fwd (static), cleared (live), new (live) ---
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
    addressed_area_map = {}
    if c2_unit_ids:
        # Build unit_id -> cycle_id mapping for per-unit bucketing
        unit_cycle = {u['unit_id']: u['cycle_id'] for u in c2_units}
        ph_od = ','.join('?' * len(c2_unit_ids))
        # Single query: ALL defects for C2 units (any status)
        all_defects_raw = query_db("""
            SELECT d.unit_id, d.status, d.raised_cycle_id, d.cleared_cycle_id,
                   d.addressed_cycle_number, at2.area_name
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at2 ON ct.area_id = at2.id
            WHERE d.unit_id IN ({}) AND d.tenant_id = ?
        """.format(ph_od), c2_unit_ids + [tenant_id])
        for r in [dict(x) for x in all_defects_raw]:
            uid = r['unit_id']
            area = r['area_name']
            cyc = unit_cycle.get(uid)
            is_prior = (r['raised_cycle_id'] != cyc)
            if is_prior:
                # B/Fwd: prior-cycle defect, ANY status (static)
                bfwd_map[uid] = bfwd_map.get(uid, 0) + 1
                key = (uid, area)
                bfwd_area_map[key] = bfwd_area_map.get(key, 0) + 1
                # Cleared: prior defect cleared THIS cycle
                if r['status'] == 'cleared' and r['cleared_cycle_id'] == cyc:
                    cleared_map[uid] = cleared_map.get(uid, 0) + 1
                    cleared_area_map[key] = cleared_area_map.get(key, 0) + 1
                # Addressed: inspector acted on this defect this cycle
                if r.get('addressed_cycle_number') == unit_cycle_num.get(uid):
                    addressed_map[uid] = addressed_map.get(uid, 0) + 1
                    addressed_area_map[key] = addressed_area_map.get(key, 0) + 1
            else:
                # New: raised THIS cycle (regression)
                new_map[uid] = new_map.get(uid, 0) + 1
                key = (uid, area)
                new_area_map[key] = new_area_map.get(key, 0) + 1
            # Open now: any open defect (unit + area level)
            if r['status'] == 'open':
                open_now_map[uid] = open_now_map.get(uid, 0) + 1
                open_now_area_map[(uid, area)] = open_now_area_map.get((uid, area), 0) + 1

        # Include inspection_defect chips (not yet submitted) in new + open counts
        idef_raw = query_db("""
            SELECT i.unit_id, at2.area_name, COUNT(*) as cnt
            FROM inspection_defect idef
            JOIN inspection i ON idef.inspection_id = i.id
            JOIN item_template it ON idef.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at2 ON ct.area_id = at2.id
            WHERE i.unit_id IN ({}) AND i.tenant_id = ?
            AND i.status IN ('in_progress', 'not_started')
            GROUP BY i.unit_id, at2.area_name
        """.format(ph_od), c2_unit_ids + [tenant_id])
        for r in [dict(x) for x in idef_raw]:
            uid = r['unit_id']
            area = r['area_name']
            cnt = r['cnt']
            new_map[uid] = new_map.get(uid, 0) + cnt
            new_area_map[(uid, area)] = new_area_map.get((uid, area), 0) + cnt
            open_now_map[uid] = open_now_map.get(uid, 0) + cnt
            open_now_area_map[(uid, area)] = open_now_area_map.get((uid, area), 0) + cnt

    # --- Batch started (earliest mark in entire batch) ---
    batch_started = None
    if unit_timing_map:
        all_starts = [v['started'] for v in unit_timing_map.values() if v['started']]
        if all_starts:
            batch_started = min(all_starts)

    # --- Attach enriched data to each unit ---
    now_utc = datetime.now(timezone.utc)
    for u in units:
        u['areas'] = area_progress.get(u['unit_id'], [])
        u['total_marked'] = sum(a['marked'] for a in u['areas'])
        u['total_items'] = sum(a['total'] for a in u['areas'])
        u['total_defects'] = sum(a['defects'] for a in u['areas'])
        u['bfwd_defects'] = bfwd_map.get(u['unit_id'], 0)
        u['cleared_defects'] = cleared_map.get(u['unit_id'], 0)
        u['new_defects'] = new_map.get(u['unit_id'], 0)
        u['open_defects'] = open_now_map.get(u['unit_id'], 0)
        if (u.get('cycle_number') or 1) >= 2:
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
            u['total_defects'] = sum(a['defects'] for a in c2_areas)

        u['floor_label'] = FLOOR_LABELS.get(u['floor'], u['floor'])

        # Timing (with started_at fallback for C2 carry-forward units)
        timing = unit_timing_map.get(u['inspection_id'], {})
        u['started_iso'] = timing.get('started') or u.get('started_at')
        u['ended_iso'] = timing.get('ended') or u.get('submitted_at')
        u['start_time'] = _format_local_hhmm(u['started_iso'])
        u['end_time'] = _format_local_hhmm(u['ended_iso'])
        u['duration_minutes'] = _minutes_between(u['started_iso'], u['ended_iso'])

        # Last activity + idle detection
        u['last_activity'] = last_activity_map.get(u['inspection_id'])
        u['is_idle'] = False
        if u['last_activity'] and u['insp_status'] == 'in_progress':
            last_dt = _parse_iso(u['last_activity'])
            if last_dt:
                idle_secs = (now_utc - last_dt).total_seconds()
                u['is_idle'] = idle_secs > 600

        # Severity (only meaningful for completed units, but calculate for all)
        u['severity'] = _get_severity(u['total_defects'], threshold_low, threshold_high)

    # Sort: in_progress first, then not_started, then completed
    status_order = {'in_progress': 0, 'not_started': 1}
    units.sort(key=lambda u: (status_order.get(u['insp_status'], 2), u['unit_number']))

    # --- Inspector data with pace, idle, initials, current_unit ---
    inspector_map = {}
    for u in units:
        iid = u.get('inspector_id')
        if not iid:
            continue
        if iid not in inspector_map:
            inspector_map[iid] = {
                'id': iid,
                'name': u['inspector_name'] or iid,
                'initials': _get_initials(u['inspector_name']),
                'units_total': 0,
                'units_done': 0,
                'items_marked': 0,
                'items_total': 0,
                'durations': [],
                'current_unit': None,
                'last_activity': None,
                'is_idle': False,
                'idle_minutes': 0,
                'avg_pace': None,
            }
        im = inspector_map[iid]
        im['units_total'] += 1
        im['items_marked'] += u.get('total_marked', 0)
        im['items_total'] += u.get('total_items', 0)

        if u['insp_status'] in ('submitted', 'reviewed', 'approved'):
            im['units_done'] += 1
            if u['duration_minutes']:
                im['durations'].append(u['duration_minutes'])

        if u['insp_status'] == 'in_progress':
            im['current_unit'] = u['unit_number']

        # Track latest activity across all units for this inspector
        if u.get('last_activity'):
            if not im['last_activity'] or u['last_activity'] > im['last_activity']:
                im['last_activity'] = u['last_activity']

    # Calculate derived inspector fields
    for iid, im in inspector_map.items():
        if im['durations']:
            im['avg_pace'] = round(sum(im['durations']) / len(im['durations']))
        del im['durations']

        # Use sum of each unit's total_items for this inspector (handles C1+C2 mix)
        inspector_units = [u for u in units if u.get('inspector_id') == iid]
        expected_total = sum(u.get('total_items', 0) for u in inspector_units)
        im['items_pct'] = round(im['items_marked'] / expected_total * 100) if expected_total else 0

        if im['last_activity']:
            last_dt = _parse_iso(im['last_activity'])
            if last_dt:
                idle_secs = (now_utc - last_dt).total_seconds()
                im["is_idle"] = idle_secs > 600 and im["items_pct"] < 100
                im['idle_minutes'] = int(idle_secs / 60) if im['is_idle'] else 0

    inspectors = sorted(inspector_map.values(), key=lambda x: x['items_pct'], reverse=True)

    # --- Activity feed (last 20) ---
    feed = []
    if inspection_ids:
        ph = ','.join('?' * len(inspection_ids))
        feed_raw = query_db("""
            SELECT ii.marked_at, ii.status AS item_status, ii.comment,
                   COALESCE(insp.name, i.inspector_name) AS inspector_name,
                   u.unit_number,
                   at2.area_name, ct.category_name, it.item_description
            FROM inspection_item ii
            JOIN inspection i ON ii.inspection_id = i.id
            JOIN unit u ON i.unit_id = u.id
            JOIN item_template it ON ii.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at2 ON ct.area_id = at2.id
            LEFT JOIN inspector insp ON i.inspector_id = insp.id
            WHERE ii.inspection_id IN ({})
            AND ii.marked_at IS NOT NULL AND ii.status NOT IN ('pending','skipped')
            ORDER BY ii.marked_at DESC LIMIT 20
        """.format(ph), inspection_ids)
        feed = [dict(r) for r in feed_raw]
        for f in feed:
            f['initials'] = _get_initials(f['inspector_name'])

    # --- Recompute batch totals from corrected per-unit data (handles C1+C2 mix) ---
    # items_marked/total_items = C1 only (item-based inspection metrics)
    items_marked = sum(u.get('total_marked', 0) for u in units if (u.get('cycle_number') or 1) == 1)
    total_items = sum(u.get('total_items', 0) for u in units if (u.get('cycle_number') or 1) == 1)

    # --- Computed KPIs ---
    # C1 units: defects found during this batch's inspection
    c1_units = [u for u in units if (u.get('cycle_number') or 1) == 1]
    c1_defects = sum(u.get('total_defects', 0) for u in c1_units)
    c1_with_marks = sum(1 for u in c1_units if u.get('total_marked', 0) > 0)
    c1_items_marked = sum(u.get('total_marked', 0) for u in c1_units)
    # C2 units: open defects (pre-existing, not found this batch)
    c2_open = sum(u.get('open_defects', 0) for u in units if (u.get('cycle_number') or 1) >= 2)
    live_defects = c1_defects  # batch KPI = C1 defects found only
    completion_pct = round(units_complete / total_units * 100) if total_units else 0
    defect_rate = round(c1_defects / c1_items_marked * 100, 1) if c1_items_marked else 0
    avg_defects = round(c1_defects / c1_with_marks, 1) if c1_with_marks else 0

    # Zone summary for header
    zones = {}
    for u in units:
        key = (u["block"], u["floor_label"])
        zones[key] = zones.get(key, 0) + 1
    zone_parts = ["{} {} ({})".format(b, f, n) for (b, f), n in sorted(zones.items())]
    batch_zones = " | ".join(zone_parts)

    # Sort: in_progress by unit_number, then not_started, then completed by defects DESC
    status_order = {'in_progress': 0, 'not_started': 1}
    units.sort(key=lambda u: (
        status_order.get(u.get('insp_status', ''), 2),
        u.get('unit_number', '') if u.get('insp_status') in ('in_progress', 'not_started') else '',
        -(u.get('total_defects', 0) or 0)
    ))

    return {
        'batch': batch,
        'units': units,
        'total_units': total_units,
        'units_complete': units_complete,
        'units_in_progress': units_in_progress,
        'units_not_started': units_not_started,
        'items_marked': items_marked,
        'total_items': total_items,
        'defects_found': live_defects,
        'inspectors': inspectors,
        'feed': feed,
        'floor_labels': FLOOR_LABELS,
        # V2 additions
        'threshold_low': threshold_low,
        'threshold_high': threshold_high,
        'batch_started': batch_started,
        'batch_started_hhmm': _format_local_hhmm(batch_started),
        'batch_ended': batch.get('submitted_at') or '',
        'batch_ended_hhmm': _format_local_hhmm(batch.get('submitted_at')) or '',
        'batch_ended': batch.get('submitted_at') or '',
        'batch_ended_hhmm': _format_local_hhmm(batch.get('submitted_at')) or '',
        'completion_pct': completion_pct,
        'defect_rate': defect_rate,
        'avg_defects': avg_defects,
        'total_items_inspected': items_marked,
        'batch_zones': batch_zones,
        'global_max_area_defects': max((a['defects'] for u in units if u['insp_status'] in ('submitted','reviewed','approved') for a in u.get('areas', [])), default=0),
    }


@batches_bp.route('/<batch_id>/live')
@require_team_lead
def live_monitor(batch_id):
    """Live Monitor V2 - full standalone page."""
    tenant_id = session['tenant_id']
    data = _build_live_monitor_data(batch_id, tenant_id)
    if not data:
        abort(404)
    resp = make_response(render_template('batches/live_monitor.html', **data))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@batches_bp.route('/<batch_id>/live/data')
@require_team_lead
def live_monitor_data(batch_id):
    """Live Monitor V2 - HTMX partial refresh."""
    tenant_id = session['tenant_id']
    data = _build_live_monitor_data(batch_id, tenant_id)
    if not data:
        abort(404)
    resp = make_response(render_template('batches/live_monitor_data.html', **data))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp



# ============================================================
# B1 — Reset / Reassign Unit
# Allows team lead / admin to reset a unit's inspection progress
# and/or reassign it to a different inspector.
# 4 options via action + markings radios:
#   A: Unassign + Reset        -> batch_unit.status='pending', delete inspection
#   B: Unassign + Keep         -> batch_unit.status='paused',  inspection.status='paused'
#   C: Reassign + Reset        -> batch_unit.status='pending', delete inspection, set inspector
#   D: Reassign + Keep         -> batch_unit.status='inspecting', inspection.status='in_progress', set inspector
# ============================================================

def _get_reset_target_inspectors(tenant_id):
    """Inspectors eligible for reassignment: inspector, team_lead, admin roles."""
    return query_db("""
        SELECT id, name, role
        FROM inspector
        WHERE tenant_id = ?
          AND role IN ('inspector', 'team_lead', 'admin')
        ORDER BY
            CASE role
                WHEN 'team_lead' THEN 1
                WHEN 'admin' THEN 2
                WHEN 'inspector' THEN 3
            END,
            name
    """, [tenant_id])


def _get_unit_defect_counts(unit_id, cycle_id, cycle_number, tenant_id):
    """Count defects that would be affected by a reset on this inspection cycle.
    Returns dict: {'raised_this_cycle': N, 'cleared_this_cycle': N}"""
    raised = query_db("""
        SELECT COUNT(*) AS c FROM defect
        WHERE unit_id = ? AND raised_cycle_id = ? AND tenant_id = ?
    """, [unit_id, cycle_id, tenant_id], one=True)
    cleared = query_db("""
        SELECT COUNT(*) AS c FROM defect
        WHERE unit_id = ? AND cleared_cycle_id = ? AND tenant_id = ?
    """, [unit_id, cycle_id, tenant_id], one=True)
    return {
        'raised_this_cycle': raised['c'] if raised else 0,
        'cleared_this_cycle': cleared['c'] if cleared else 0,
    }


@batches_bp.route('/<batch_id>/reset-confirm/<bu_id>')
@require_team_lead
def reset_confirm(batch_id, bu_id):
    """HTMX partial: modal row for reset/reassign."""
    tenant_id = session['tenant_id']

    bu = query_db("""
        SELECT bu.id AS bu_id, bu.status AS bu_status,
               bu.inspector_id, bu.unit_id, bu.cycle_id,
               u.unit_number, u.block, u.floor,
               ic.cycle_number
        FROM batch_unit bu
        JOIN unit u ON bu.unit_id = u.id
        LEFT JOIN inspection_cycle ic ON bu.cycle_id = ic.id
        WHERE bu.id = ? AND bu.batch_id = ? AND bu.tenant_id = ?
    """, [bu_id, batch_id, tenant_id], one=True)
    if not bu:
        abort(404)
    bu = dict(bu)

    # Current inspection (if any)
    insp = query_db("""
        SELECT id, status, inspector_id, inspector_name
        FROM inspection
        WHERE unit_id = ? AND cycle_id = ? AND tenant_id = ?
    """, [bu['unit_id'], bu['cycle_id'], tenant_id], one=True)
    insp = dict(insp) if insp else None

    # Defect counts
    defect_counts = _get_unit_defect_counts(
        bu['unit_id'], bu['cycle_id'], bu['cycle_number'], tenant_id)

    # Non-pending item count (what would be "kept" or "reset")
    non_pending_items = 0
    if insp:
        row = query_db("""
            SELECT COUNT(*) AS c FROM inspection_item
            WHERE inspection_id = ? AND status NOT IN ('pending','skipped')
        """, [insp['id']], one=True)
        non_pending_items = row['c'] if row else 0

    has_inspector = bool(bu.get('inspector_id'))
    has_captured_work = (non_pending_items > 0 or
                         defect_counts['raised_this_cycle'] > 0 or
                         defect_counts['cleared_this_cycle'] > 0)

    # Eligible inspectors for reassign
    inspectors = _get_reset_target_inspectors(tenant_id)
    inspectors = [dict(i) for i in inspectors]

    return render_template('batches/_reset_confirm.html',
                           batch_id=batch_id, bu=bu, insp=insp,
                           defect_counts=defect_counts,
                           non_pending_items=non_pending_items,
                           has_inspector=has_inspector,
                           has_captured_work=has_captured_work,
                           inspectors=inspectors)


@batches_bp.route('/<batch_id>/reset-unit', methods=['POST'])
@require_team_lead
def reset_unit(batch_id):
    """Execute reset/reassign action.
    Form fields:
      bu_id                  (required)
      action                 (required) 'unassign' | 'reassign'
      new_inspector_id       (required if action=reassign)
      markings               (required) 'reset' | 'keep'
      reason                 (required, >=3 chars)
      confirm_destructive    (required if reset chosen AND defects exist, value='yes')
    """
    tenant_id = session['tenant_id']
    user_id = session['user_id']
    user_name = session['user_name']
    db = get_db()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    bu_id = request.form.get('bu_id', '').strip()
    action = request.form.get('action', '').strip()
    new_inspector_id = request.form.get('new_inspector_id', '').strip() or None
    markings = request.form.get('markings', '').strip()
    reason = request.form.get('reason', '').strip()
    confirm_destructive = request.form.get('confirm_destructive', '').strip() == 'yes'

    # --- Validate ---
    if not bu_id or action not in ('unassign', 'reassign') or markings not in ('reset', 'keep'):
        return 'Missing or invalid fields.', 400
    if not reason or len(reason) < 3:
        return 'Reason is required (min 3 characters).', 400
    if action == 'reassign' and not new_inspector_id:
        return 'Inspector required for reassign.', 400

    bu = query_db("""
        SELECT bu.*, u.unit_number, ic.cycle_number
        FROM batch_unit bu
        JOIN unit u ON bu.unit_id = u.id
        LEFT JOIN inspection_cycle ic ON bu.cycle_id = ic.id
        WHERE bu.id = ? AND bu.batch_id = ? AND bu.tenant_id = ?
    """, [bu_id, batch_id, tenant_id], one=True)
    if not bu:
        abort(404)
    bu = dict(bu)

    # --- Preconditions ---
    allowed_bu_statuses = ('pending', 'not_started', 'assigned', 'in_progress', 'inspecting', 'paused')
    if bu['status'] not in allowed_bu_statuses:
        return 'Cannot reset a unit that is already submitted, reviewed, approved, or signed off.', 400
    if bu.get('removed_at'):
        return 'Cannot reset a removed unit.', 400

    # Validate new inspector if reassigning
    if action == 'reassign':
        insp_row = query_db("""
            SELECT id, name, role FROM inspector
            WHERE id = ? AND tenant_id = ?
              AND role IN ('inspector', 'team_lead', 'admin')
        """, [new_inspector_id, tenant_id], one=True)
        if not insp_row:
            return 'Invalid inspector.', 400
        insp_row = dict(insp_row)
        new_inspector_name = insp_row['name']
    else:
        new_inspector_name = None

    # Current inspection (if any)
    insp = query_db("""
        SELECT id, status, inspector_id, inspector_name
        FROM inspection
        WHERE unit_id = ? AND cycle_id = ? AND tenant_id = ?
    """, [bu['unit_id'], bu['cycle_id'], tenant_id], one=True)
    insp = dict(insp) if insp else None

    # Defect counts
    defect_counts = _get_unit_defect_counts(
        bu['unit_id'], bu['cycle_id'], bu['cycle_number'], tenant_id)
    has_destructive_defects = (markings == 'reset' and
        (defect_counts['raised_this_cycle'] > 0 or defect_counts['cleared_this_cycle'] > 0))

    if has_destructive_defects and not confirm_destructive:
        return 'Destructive action requires explicit confirmation.', 400

    # --- Execute ---
    # Determine outcome
    if action == 'unassign' and markings == 'reset':
        outcome = 'A'
        new_bu_status = 'pending'
        new_bu_inspector = None
        delete_inspection = True
        set_inspection_paused = False
    elif action == 'unassign' and markings == 'keep':
        outcome = 'B'
        new_bu_status = 'paused'
        new_bu_inspector = None
        delete_inspection = False
        set_inspection_paused = True
    elif action == 'reassign' and markings == 'reset':
        outcome = 'C'
        new_bu_status = 'pending'
        new_bu_inspector = new_inspector_id
        delete_inspection = True
        set_inspection_paused = False
    else:  # reassign + keep
        outcome = 'D'
        new_bu_status = 'inspecting'
        new_bu_inspector = new_inspector_id
        delete_inspection = False
        set_inspection_paused = False

    # Collect before-state for audit
    before_state = {
        'bu_status': bu['status'],
        'bu_inspector_id': bu.get('inspector_id'),
        'inspection_id': insp['id'] if insp else None,
        'inspection_status': insp['status'] if insp else None,
        'inspection_inspector_id': insp['inspector_id'] if insp else None,
        'defects_raised_this_cycle': defect_counts['raised_this_cycle'],
        'defects_cleared_this_cycle': defect_counts['cleared_this_cycle'],
    }

    # Handle defects on reset
    if markings == 'reset':
        # Reopen defects cleared during this cycle (de-snag rollback)
        db.execute("""
            UPDATE defect
            SET status = 'open',
                cleared_cycle_id = NULL,
                cleared_cycle_number = NULL,
                cleared_at = NULL,
                clearance_note = NULL,
                addressed_cycle_number = NULL,
                updated_at = ?
            WHERE unit_id = ? AND cleared_cycle_id = ? AND tenant_id = ?
        """, [now, bu['unit_id'], bu['cycle_id'], tenant_id])
        # Delete defects raised during this cycle (C1 rollback)
        db.execute("""
            DELETE FROM defect
            WHERE unit_id = ? AND raised_cycle_id = ? AND tenant_id = ?
        """, [bu['unit_id'], bu['cycle_id'], tenant_id])

    # Handle inspection record
    if delete_inspection and insp:
        db.execute("DELETE FROM inspection_item WHERE inspection_id = ?", [insp['id']])
        db.execute("DELETE FROM inspection WHERE id = ?", [insp['id']])
        # Outcome C (reassign + reset): create fresh inspection for new inspector
        # so the unit appears on their /my-inspections home page.
        # Outcome A (unassign + reset): no inspector yet, so no inspection row
        # is created here — the existing assignment dropdown will create one
        # when an inspector is next assigned.
        if outcome == 'C':
            import uuid
            new_insp_id = uuid.uuid4().hex[:8]
            today = now.split(' ')[0]
            db.execute("""INSERT INTO inspection
                (id, tenant_id, unit_id, cycle_id, inspector_id, inspector_name,
                 status, inspection_date, cycle_number, exclusion_list_id,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [new_insp_id, tenant_id, bu['unit_id'], bu['cycle_id'],
                 new_inspector_id, new_inspector_name,
                 'not_started', today, bu['cycle_number'],
                 bu.get('exclusion_list_id'), now, now])
    elif set_inspection_paused and insp:
        db.execute("""
            UPDATE inspection
            SET status = 'paused',
                inspector_id = '',
                inspector_name = '',
                updated_at = ?
            WHERE id = ?
        """, [now, insp['id']])
    elif outcome == 'D' and insp:
        # Reassign + keep: swap inspector on inspection record
        db.execute("""
            UPDATE inspection
            SET status = 'in_progress',
                inspector_id = ?,
                inspector_name = ?,
                updated_at = ?
            WHERE id = ?
        """, [new_inspector_id, new_inspector_name, now, insp['id']])

    # Update batch_unit
    db.execute("""
        UPDATE batch_unit
        SET status = ?, inspector_id = ?
        WHERE id = ?
    """, [new_bu_status, new_bu_inspector, bu_id])

    # Audit log
    after_state = {
        'bu_status': new_bu_status,
        'bu_inspector_id': new_bu_inspector,
        'outcome': outcome,
        'new_inspector_name': new_inspector_name,
    }
    import json
    metadata = json.dumps({
        'batch_id': batch_id,
        'unit_number': bu['unit_number'],
        'cycle_number': bu['cycle_number'],
        'outcome': outcome,
        'action': action,
        'markings': markings,
        'reason': reason,
        'before': before_state,
        'after': after_state,
    })
    log_audit(db, tenant_id, 'batch_unit', bu_id,
              'reset_' + outcome.lower(),
              old_value=bu['status'],
              new_value=new_bu_status,
              user_id=user_id, user_name=user_name,
              metadata=metadata)

    db.commit()

    messages = {
        'A': 'Unit {un} unassigned and markings cleared.',
        'B': 'Unit {un} paused.',
        'C': 'Unit {un} reassigned to {nm}.',
        'D': 'Unit {un} handed to {nm}.',
    }
    flash(messages[outcome].format(un=bu['unit_number'], nm=new_inspector_name or ''), 'success')
    return redirect(url_for('batches.detail', batch_id=batch_id))
