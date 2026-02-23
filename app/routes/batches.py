"""
Batch routes - Operational batch management.
Create batches with unit numbers, auto-route to cycles, assign inspectors.
Access: Team Lead + Admin.
"""
from datetime import datetime, timezone
from flask import Blueprint, render_template, session, redirect, url_for, abort, request, flash
from app.auth import require_team_lead
from app.utils import generate_id
from app.utils.audit import log_audit
from app.services.db import get_db, query_db

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


@batches_bp.route('/')
@require_team_lead
def list_batches():
    """List all batches."""
    tenant_id = session['tenant_id']

    batches_raw = query_db("""
        SELECT ib.id, ib.name, ib.status, ib.notes, ib.created_at,
            COUNT(bu.id) AS total_units,
            SUM(CASE WHEN bu.status IN ('submitted','reviewed','approved','signed')
                THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN bu.status = 'inspecting' THEN 1 ELSE 0 END) AS in_progress,
            SUM(CASE WHEN bu.status IN ('pending','assigned') THEN 1 ELSE 0 END) AS pending
        FROM inspection_batch ib
        LEFT JOIN batch_unit bu ON bu.batch_id = ib.id
        WHERE ib.tenant_id = ?
        GROUP BY ib.id
        ORDER BY ib.created_at DESC
    """, [tenant_id])
    batches = [dict(r) for r in batches_raw]

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

        if not batch_name:
            batch_name = datetime.now().strftime('%Y-%m-%d')

        if not unit_input:
            flash('Enter at least one unit number.', 'error')
            return render_template('batches/create.html', name=batch_name, notes=notes)

        raw_numbers = []
        for part in unit_input.replace(',', ' ').replace('\n', ' ').split():
            part = part.strip()
            if part:
                raw_numbers.append(part.zfill(3))

        if not raw_numbers:
            flash('No valid unit numbers found.', 'error')
            return render_template('batches/create.html', name=batch_name, notes=notes)

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
                (id, tenant_id, batch_id, unit_id, cycle_id, inspector_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, NULL, 'pending', ?)
            """, (bu_id, tenant_id, batch_id, unit_row['id'], cycle_id, now))

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
    return render_template('batches/create.html', name=today, notes='')


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
        SELECT bu.id AS bu_id, bu.status AS bu_status, COALESCE(bu.inspector_id, i.inspector_id) AS inspector_id,
            bu.cycle_id, u.id AS unit_id, u.unit_number, u.block, u.floor,
            ic.cycle_number,
            i.id AS inspection_id, i.status AS inspection_status,
            COALESCE(insp.name, i.inspector_name) AS inspector_name
        FROM batch_unit bu
        JOIN unit u ON bu.unit_id = u.id
        JOIN inspection_cycle ic ON bu.cycle_id = ic.id
        LEFT JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = bu.cycle_id
        LEFT JOIN inspector insp ON bu.inspector_id = insp.id
        WHERE bu.batch_id = ? AND bu.tenant_id = ?
        ORDER BY u.block, u.floor, u.unit_number
    """, [batch_id, tenant_id])
    units = [dict(r) for r in units_raw]

    inspectors_raw = query_db("""
        SELECT id, name FROM inspector
        WHERE tenant_id = ? AND role IN ('inspector', 'team_lead') AND active = 1
        ORDER BY name
    """, [tenant_id])
    inspectors = [dict(r) for r in inspectors_raw]

    return render_template('batches/detail.html',
                           batch=batch, units=units, inspectors=inspectors,
                           floor_labels=FLOOR_LABELS)


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
        db.execute("""
            INSERT INTO inspection
            (id, tenant_id, unit_id, cycle_id, inspector_id, inspector_name,
             status, inspection_date, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'not_started', ?, ?, ?)
        """, [insp_id, tenant_id, bu['unit_id'], bu['cycle_id'],
              inspector_id, inspector['name'], today, now, now])

    log_audit(db, tenant_id, 'batch', batch_id, 'inspector_assigned',
              new_value=inspector_id,
              user_id=session['user_id'], user_name=session['user_name'],
              metadata='{{"unit_id": "{}"}}'.format(bu['unit_id']))

    db.commit()

    return '<span class="text-xs text-green-600">{}</span>'.format(inspector['name'])
