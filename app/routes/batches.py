"""
Batch routes - Operational batch management.
Create batches with unit numbers, auto-route to cycles, assign inspectors.
Access: Team Lead + Admin.
"""
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, session, redirect, url_for, abort, request, flash, make_response
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
            SUM(CASE WHEN i.status IN ('submitted','reviewed','pending_followup','approved','certified','closed')
                THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN i.status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress,
            SUM(CASE WHEN i.status IS NULL OR i.status = 'not_started' THEN 1 ELSE 0 END) AS pending
        FROM inspection_batch ib
        LEFT JOIN batch_unit bu ON bu.batch_id = ib.id
        LEFT JOIN inspection i ON i.unit_id = bu.unit_id AND i.cycle_id = bu.cycle_id
        WHERE ib.tenant_id = ?
        GROUP BY ib.id
        ORDER BY ib.created_at DESC
    """, [tenant_id])
    batches = [dict(r) for r in batches_raw]

    # Derive batch status from inspection progress
    for b in batches:
        if b["total_units"] == 0:
            b["status"] = "open"
        elif b["completed"] == b["total_units"]:
            b["status"] = "complete"
        elif b["in_progress"] > 0 or b["completed"] > 0:
            b["status"] = "in_progress"
        else:
            b["status"] = "open"

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
        SELECT bu.id AS bu_id, COALESCE(i.status, 'not_started') AS bu_status, COALESCE(bu.inspector_id, i.inspector_id) AS inspector_id,
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
        return datetime.fromisoformat(s)
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
               ic.cycle_number,
               COALESCE(insp.name, i.inspector_name) AS inspector_name
        FROM batch_unit bu
        JOIN unit u ON bu.unit_id = u.id
        JOIN inspection_cycle ic ON bu.cycle_id = ic.id
        LEFT JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = bu.cycle_id
        LEFT JOIN inspector insp ON bu.inspector_id = insp.id
        WHERE bu.batch_id = ? AND bu.tenant_id = ?
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

    # Sort areas: Kitchen, Lounge, Bathroom, then Bedrooms
    area_order = {'KITCHEN': 0, 'LOUNGE': 1, 'BATHROOM': 2}
    for uid in area_progress:
        area_progress[uid].sort(key=lambda a: (area_order.get(a['area'], 10), a['area']))

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
        u['pct'] = round(u['total_marked'] / u['total_items'] * 100) if u['total_items'] else 0
        u['floor_label'] = FLOOR_LABELS.get(u['floor'], u['floor'])

        # Timing
        timing = unit_timing_map.get(u['inspection_id'], {})
        u['started_iso'] = timing.get('started')
        u['ended_iso'] = timing.get('ended')
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
                'durations': [],
                'current_unit': None,
                'last_activity': None,
                'is_idle': False,
                'idle_minutes': 0,
                'avg_pace': None,
            }
        im = inspector_map[iid]
        im['units_total'] += 1

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

        if im['last_activity']:
            last_dt = _parse_iso(im['last_activity'])
            if last_dt:
                idle_secs = (now_utc - last_dt).total_seconds()
                im['is_idle'] = idle_secs > 600
                im['idle_minutes'] = int(idle_secs / 60) if im['is_idle'] else 0

    inspectors = sorted(inspector_map.values(), key=lambda x: x['name'])

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

    # --- Computed KPIs ---
    completion_pct = round(units_complete / total_units * 100) if total_units else 0
    total_non_skipped = items_marked  # items that have been marked (not pending/skipped)
    defect_rate = round(defects_found / total_non_skipped * 100, 1) if total_non_skipped else 0
    avg_defects = round(defects_found / units_complete, 1) if units_complete else 0

    return {
        'batch': batch,
        'units': units,
        'total_units': total_units,
        'units_complete': units_complete,
        'units_in_progress': units_in_progress,
        'units_not_started': units_not_started,
        'items_marked': items_marked,
        'total_items': total_items,
        'defects_found': defects_found,
        'inspectors': inspectors,
        'feed': feed,
        'floor_labels': FLOOR_LABELS,
        # V2 additions
        'threshold_low': threshold_low,
        'threshold_high': threshold_high,
        'batch_started': batch_started,
        'batch_started_hhmm': _format_local_hhmm(batch_started),
        'completion_pct': completion_pct,
        'defect_rate': defect_rate,
        'avg_defects': avg_defects,
        'total_items_inspected': items_marked,
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


@batches_bp.route('/<batch_id>/toggle-lock', methods=['POST'])
@require_team_lead
def toggle_lock(batch_id):
    """Lock or unlock a batch for inspectors."""
    tenant_id = session['tenant_id']
    db = get_db()

    batch = query_db(
        "SELECT id, locked FROM inspection_batch WHERE id = ? AND tenant_id = ?",
        [batch_id, tenant_id], one=True)
    if not batch:
        abort(404)

    new_state = 0 if batch['locked'] else 1
    db.execute("UPDATE inspection_batch SET locked = ?, updated_at = ? WHERE id = ?",
               [new_state, datetime.now(timezone.utc).isoformat(), batch_id])
    db.commit()

    label = 'locked' if new_state else 'unlocked'
    flash('Batch {}.'.format(label), 'success')
    return redirect(url_for('batches.detail', batch_id=batch_id))

