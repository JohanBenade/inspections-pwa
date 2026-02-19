"""
Cycle routes - Inspection cycle management.
Create cycles, set exclusions, add general notes, assign inspectors.
"""
import re
from datetime import date, datetime, timezone
from flask import Blueprint, render_template, session, redirect, url_for, abort, request, flash
from app.auth import require_team_lead, require_manager
from app.utils import generate_id
from app.utils.audit import log_audit
from app.services.db import get_db, query_db

cycles_bp = Blueprint('cycles', __name__, url_prefix='/cycles')


# --- Rich text sanitization helpers ---

ALLOWED_TAGS = {'p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'b', 'i'}
EMPTY_QUILL_VALUES = {'', '<p><br></p>', '<p></p>'}


def sanitize_html(html_str):
    """Allow only safe formatting tags from rich text editor."""
    if not html_str:
        return html_str

    def replace_tag(match):
        full = match.group(0)
        tag_match = re.match(r'</?(\w+)', full)
        if tag_match:
            tag = tag_match.group(1).lower()
            if tag in ALLOWED_TAGS:
                if full.startswith('</'):
                    return '</{}>'.format(tag)
                elif tag == 'br':
                    return '<br>'
                else:
                    return '<{}>'.format(tag)
        return ''

    return re.sub(r'<[^>]+>', replace_tag, html_str).strip()


def clean_notes(value):
    """Sanitize and clean rich text notes. Return None if empty."""
    if not value:
        return None
    value = sanitize_html(value.strip())
    if value in EMPTY_QUILL_VALUES:
        return None
    return value


# --- Routes ---

@cycles_bp.route('/')
@require_team_lead
def list_cycles():
    """List all inspection cycles for current phase."""
    tenant_id = session['tenant_id']
    user_role = session.get('role', 'inspector')
    
    phase = query_db("""
        SELECT ph.*, p.project_name, p.client_name
        FROM phase ph
        JOIN project p ON ph.project_id = p.id
        WHERE ph.tenant_id = ?
        LIMIT 1
    """, [tenant_id], one=True)
    
    if not phase:
        abort(404)
    
    cycles = query_db("""
        SELECT ic.*, ic.block, ic.floor,
            insp.name as created_by_name,
            (SELECT COUNT(*) FROM unit u WHERE u.phase_id = ic.phase_id
                AND (ic.unit_start IS NULL OR u.unit_number >= ic.unit_start)
                AND (ic.unit_end IS NULL OR u.unit_number <= ic.unit_end)
                AND u.id NOT IN (SELECT ceu.unit_id FROM cycle_excluded_unit ceu WHERE ceu.cycle_id = ic.id)
            ) as total_units,
            (SELECT COUNT(DISTINCT i.unit_id) FROM inspection i WHERE i.cycle_id = ic.id) as units_inspected,
            (SELECT COUNT(DISTINCT i.unit_id) FROM inspection i WHERE i.cycle_id = ic.id AND i.status = 'submitted') as units_submitted,
            (SELECT COUNT(*) FROM cycle_excluded_item cei WHERE cei.cycle_id = ic.id) as excluded_count,
            (SELECT COUNT(*) FROM inspection_item ii JOIN inspection i ON ii.inspection_id = i.id WHERE i.cycle_id = ic.id AND ii.status IN ('not_to_standard', 'not_installed')) as defect_count,
            (SELECT COUNT(DISTINCT i2.id) FROM inspection i2 WHERE i2.cycle_id = ic.id AND i2.manager_reviewed_at IS NOT NULL) as spot_checked,
            (SELECT COUNT(DISTINCT i3.id) FROM inspection i3 WHERE i3.cycle_id = ic.id) as inspected_count
        FROM inspection_cycle ic
        JOIN inspector insp ON ic.created_by = insp.id
        WHERE ic.phase_id = ?
        ORDER BY ic.cycle_number DESC
    """, [phase['id']])
    
    return render_template('cycles/list.html', phase=phase, cycles=cycles, user_role=user_role)


@cycles_bp.route('/create', methods=['GET', 'POST'])
@require_team_lead
def create_cycle():
    """Create a new inspection cycle with optional unit creation and exclusion copying."""
    tenant_id = session['tenant_id']
    user_id = session['user_id']
    db = get_db()
    
    phase = query_db("""
        SELECT ph.*, p.project_name
        FROM phase ph
        JOIN project p ON ph.project_id = p.id
        WHERE ph.tenant_id = ?
        LIMIT 1
    """, [tenant_id], one=True)
    
    if not phase:
        abort(404)
    
    if request.method == 'POST':
        cycle_number = int(request.form.get('cycle_number', 1))
        block = request.form.get('block', '').strip() or None
        floor_val = request.form.get('floor', '')
        floor = int(floor_val) if floor_val.strip() != '' else None
        unit_start = request.form.get('unit_start', '').strip() or None
        unit_end = request.form.get('unit_end', '').strip() or None
        unit_type = request.form.get('unit_type', '4-Bed').strip()
        copy_from = request.form.get('copy_exclusions_from', '').strip() or None
        general_notes = clean_notes(request.form.get('general_notes', ''))
        exclusion_notes = clean_notes(request.form.get('exclusion_notes', ''))
        
        # Audit trail fields
        request_received_date = request.form.get('request_received_date', '').strip() or None
        started_at_date = request.form.get('started_at', '').strip() or None
        # Convert date to timestamp if provided
        started_at = None
        if started_at_date:
            started_at = started_at_date + 'T00:00:00'
        
        # Create missing units in range
        units_created = 0
        if unit_start and unit_end:
            start_num = int(unit_start)
            end_num = int(unit_end)
            for num in range(start_num, end_num + 1):
                unit_number = str(num).zfill(3)
                existing = query_db(
                    "SELECT id FROM unit WHERE unit_number = ? AND phase_id = ?",
                    [unit_number, phase['id']], one=True
                )
                if not existing:
                    unit_id = generate_id()
                    db.execute("""
                        INSERT INTO unit (id, tenant_id, phase_id, unit_number, unit_type, block, floor, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'not_started')
                    """, [unit_id, tenant_id, phase['id'], unit_number, unit_type, block, floor])
                    units_created += 1
        
        # Create cycle record with audit trail fields
        cycle_id = generate_id()
        db.execute("""
            INSERT INTO inspection_cycle 
            (id, tenant_id, phase_id, cycle_number, unit_start, unit_end, block, floor, 
             general_notes, exclusion_notes, created_by, request_received_date, started_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [cycle_id, tenant_id, phase['id'], cycle_number, unit_start, unit_end, block, floor, 
              general_notes, exclusion_notes, user_id, request_received_date, started_at])
        
        log_audit(db, tenant_id, 'cycle', cycle_id, 'cycle_created',
                  new_value='active',
                  user_id=user_id, user_name=session['user_name'],
                  metadata=f'{{"cycle_number": {cycle_number}, "block": "{block}", "units": "{unit_start}-{unit_end}"}}')
        
        # Copy exclusions from source cycle
        exclusions_copied = 0
        if copy_from:
            source_exclusions = query_db(
                "SELECT item_template_id, reason FROM cycle_excluded_item WHERE cycle_id = ?",
                [copy_from]
            )
            for exc in source_exclusions:
                exc_id = generate_id()
                db.execute("""
                    INSERT INTO cycle_excluded_item (id, tenant_id, cycle_id, item_template_id, reason)
                    VALUES (?, ?, ?, ?, ?)
                """, [exc_id, tenant_id, cycle_id, exc['item_template_id'], exc['reason']])
                exclusions_copied += 1
            
            # Also copy area notes from source cycle
            source_notes = query_db(
                "SELECT area_template_id, note FROM cycle_area_note WHERE cycle_id = ?",
                [copy_from]
            )
            for note in source_notes:
                note_id = generate_id()
                db.execute("""
                    INSERT INTO cycle_area_note (id, tenant_id, cycle_id, area_template_id, note)
                    VALUES (?, ?, ?, ?, ?)
                """, [note_id, tenant_id, cycle_id, note['area_template_id'], note['note']])
        
        db.commit()
        
        msg_parts = ['Cycle {} created'.format(cycle_number)]
        if units_created > 0:
            msg_parts.append('{} units added'.format(units_created))
        if exclusions_copied > 0:
            msg_parts.append('{} exclusions copied'.format(exclusions_copied))
        flash('. '.join(msg_parts), 'success')
        
        return redirect(url_for('cycles.manage_units', cycle_id=cycle_id))
    
    # GET - show form
    existing_cycles = query_db("""
        SELECT ic.id, ic.cycle_number, ic.block, ic.unit_start, ic.unit_end,
            (SELECT COUNT(*) FROM cycle_excluded_item WHERE cycle_id = ic.id) as exclusion_count
        FROM inspection_cycle ic
        WHERE ic.tenant_id = ?
        ORDER BY ic.cycle_number DESC
    """, [tenant_id])
    
    existing_blocks = query_db("""
        SELECT DISTINCT block FROM unit 
        WHERE tenant_id = ? AND block IS NOT NULL 
        ORDER BY block
    """, [tenant_id])
    
    return render_template('cycles/create.html', 
                          phase=phase, 
                          existing_cycles=existing_cycles,
                          existing_blocks=existing_blocks)


@cycles_bp.route('/<cycle_id>')
@require_team_lead
def view_cycle(cycle_id):
    """View cycle details and inspection status."""
    tenant_id = session['tenant_id']
    
    cycle = query_db("""
        SELECT ic.*, ph.phase_name, p.project_name, insp.name as created_by_name
        FROM inspection_cycle ic
        JOIN phase ph ON ic.phase_id = ph.id
        JOIN project p ON ph.project_id = p.id
        JOIN inspector insp ON ic.created_by = insp.id
        WHERE ic.id = ? AND ic.tenant_id = ?
    """, [cycle_id, tenant_id], one=True)
    
    if not cycle:
        abort(404)
    
    # Get units with inspection status for this cycle (filtered by range if set)
    range_filter = ""
    params = [cycle_id, cycle['phase_id']]
    if cycle['unit_start'] and cycle['unit_end']:
        range_filter = "AND u.unit_number >= ? AND u.unit_number <= ?"
        params.extend([cycle['unit_start'], cycle['unit_end']])
    
    units = query_db("""
        SELECT u.unit_number, u.status as unit_status, u.id as unit_id,
            i.id as inspection_id, i.status as inspection_status,
            i.inspection_date, COALESCE(i.inspector_name, assigned_insp.name) as inspector_name,
            (SELECT COUNT(*) FROM inspection_item ii WHERE ii.inspection_id = i.id AND ii.status IN ('not_to_standard', 'not_installed')) as open_defects
        FROM unit u
        LEFT JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = ?
        LEFT JOIN cycle_unit_assignment cua ON cua.unit_id = u.id AND cua.cycle_id = ?
        LEFT JOIN inspector assigned_insp ON cua.inspector_id = assigned_insp.id
        WHERE u.phase_id = ? {}
        ORDER BY u.unit_number
    """.format(range_filter), [cycle_id, cycle_id] + params[1:])
    
    # Get excluded items
    excluded = query_db("""
        SELECT cei.*, it.item_description, ct.category_name, at.area_name,
            parent.item_description as parent_description
        FROM cycle_excluded_item cei
        JOIN item_template it ON cei.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        LEFT JOIN item_template parent ON it.parent_item_id = parent.id
        WHERE cei.cycle_id = ?
        ORDER BY at.area_order, ct.category_order, it.item_order
    """, [cycle_id])
    
    # Get area notes
    area_notes = query_db("""
        SELECT can.*, at.area_name
        FROM cycle_area_note can
        JOIN area_template at ON can.area_template_id = at.id
        WHERE can.cycle_id = ?
        ORDER BY at.area_order
    """, [cycle_id])
    
    # Check if any inspections exist (for delete button)
    has_inspections = any(u['inspection_id'] for u in units)
    
    # Get all inspectors for assignment dropdown
    inspectors = query_db("""
        SELECT id, name FROM inspector 
        WHERE tenant_id = ? AND role IN ('inspector', 'team_lead') AND active = 1
        ORDER BY name
    """, [tenant_id])
    
    # Get current assignments
    assignments = query_db("""
        SELECT unit_id, inspector_id FROM cycle_unit_assignment
        WHERE cycle_id = ?
    """, [cycle_id])
    assignment_map = {a['unit_id']: a['inspector_id'] for a in assignments}
    
    # Get excluded units for this cycle
    excluded_units = query_db(
        "SELECT unit_id FROM cycle_excluded_unit WHERE cycle_id = ?",
        [cycle_id]
    )
    excluded_unit_ids = set(eu['unit_id'] for eu in excluded_units)

    # Get defaults for Add Unit form (most common values from units in this cycle)
    unit_defaults_row = query_db("""
        SELECT block, floor, unit_type, COUNT(*) as cnt
        FROM unit
        WHERE phase_id = ?
            AND (? IS NULL OR unit_number >= ?)
            AND (? IS NULL OR unit_number <= ?)
        GROUP BY block, floor, unit_type
        ORDER BY cnt DESC
        LIMIT 1
    """, [cycle['phase_id'], cycle['unit_start'], cycle['unit_start'], 
         cycle['unit_end'], cycle['unit_end']], one=True)
    unit_defaults = {
        'block': unit_defaults_row['block'] if unit_defaults_row else '',
        'floor': unit_defaults_row['floor'] if unit_defaults_row else 0,
        'unit_type': unit_defaults_row['unit_type'] if unit_defaults_row else '4-Bed'
    }

    return render_template('cycles/view.html', cycle=cycle, units=units, excluded=excluded, 
                          area_notes=area_notes, has_inspections=has_inspections,
                          inspectors=inspectors, assignment_map=assignment_map,
                          excluded_unit_ids=excluded_unit_ids, unit_defaults=unit_defaults)



@cycles_bp.route('/<cycle_id>/manage')
@require_team_lead
def manage_units(cycle_id):
    """Manage units in cycle - assign inspectors, add/remove units."""
    tenant_id = session['tenant_id']

    cycle = query_db("""
        SELECT ic.*, ph.phase_name, p.project_name
        FROM inspection_cycle ic
        JOIN phase ph ON ic.phase_id = ph.id
        JOIN project p ON ph.project_id = p.id
        WHERE ic.id = ? AND ic.tenant_id = ?
    """, [cycle_id, tenant_id], one=True)

    if not cycle:
        abort(404)

    range_filter = ""
    params = [cycle_id, cycle['phase_id']]
    if cycle['unit_start'] and cycle['unit_end']:
        range_filter = "AND u.unit_number >= ? AND u.unit_number <= ?"
        params.extend([cycle['unit_start'], cycle['unit_end']])

    units = query_db("""
        SELECT u.unit_number, u.status as unit_status, u.id as unit_id,
            i.id as inspection_id, i.status as inspection_status,
            i.inspector_name
        FROM unit u
        LEFT JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = ?
        WHERE u.phase_id = ? {}
        ORDER BY u.unit_number
    """.format(range_filter), params)

    inspectors = query_db("""
        SELECT id, name FROM inspector
        WHERE tenant_id = ? AND role IN ('inspector', 'team_lead') AND active = 1
        ORDER BY name
    """, [tenant_id])

    assignments = query_db(
        "SELECT unit_id, inspector_id FROM cycle_unit_assignment WHERE cycle_id = ?",
        [cycle_id]
    )
    assignment_map = {a['unit_id']: a['inspector_id'] for a in assignments}

    excluded_units = query_db(
        "SELECT unit_id FROM cycle_excluded_unit WHERE cycle_id = ?",
        [cycle_id]
    )
    excluded_unit_ids = set(eu['unit_id'] for eu in excluded_units)

    unit_defaults_row = query_db("""
        SELECT block, floor, unit_type, COUNT(*) as cnt
        FROM unit WHERE phase_id = ?
            AND (? IS NULL OR unit_number >= ?)
            AND (? IS NULL OR unit_number <= ?)
        GROUP BY block, floor, unit_type
        ORDER BY cnt DESC LIMIT 1
    """, [cycle['phase_id'], cycle['unit_start'], cycle['unit_start'],
         cycle['unit_end'], cycle['unit_end']], one=True)
    unit_defaults = {
        'block': unit_defaults_row['block'] if unit_defaults_row else '',
        'floor': unit_defaults_row['floor'] if unit_defaults_row else 0,
        'unit_type': unit_defaults_row['unit_type'] if unit_defaults_row else '4-Bed'
    }

    return render_template('cycles/manage.html', cycle=cycle, units=units,
                          inspectors=inspectors, assignment_map=assignment_map,
                          excluded_unit_ids=excluded_unit_ids, unit_defaults=unit_defaults)

@cycles_bp.route('/<cycle_id>/edit', methods=['GET', 'POST'])
@require_team_lead
def edit_cycle(cycle_id):
    """Edit cycle - set exclusions and notes."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    cycle = query_db("""
        SELECT ic.*, ph.phase_name, p.project_name
        FROM inspection_cycle ic
        JOIN phase ph ON ic.phase_id = ph.id
        JOIN project p ON ph.project_id = p.id
        WHERE ic.id = ? AND ic.tenant_id = ?
    """, [cycle_id, tenant_id], one=True)
    
    if not cycle:
        abort(404)
    
    if request.method == 'POST':
        general_notes = clean_notes(request.form.get('general_notes', ''))
        exclusion_notes = clean_notes(request.form.get('exclusion_notes', ''))
        unit_start = request.form.get('unit_start', '').strip() or None
        unit_end = request.form.get('unit_end', '').strip() or None
        request_received_date = request.form.get('request_received_date', '').strip() or None
        started_at = request.form.get('started_at', '').strip() or None
        if started_at:
            started_at = started_at + 'T00:00:00+00:00'
        
        db.execute("""
            UPDATE inspection_cycle 
            SET general_notes = ?, exclusion_notes = ?, unit_start = ?, unit_end = ?,
                request_received_date = ?, started_at = COALESCE(?, started_at)
            WHERE id = ?
        """, [general_notes, exclusion_notes, unit_start, unit_end, request_received_date, started_at, cycle_id])
        
        # Save area notes
        unit = query_db(
            "SELECT unit_type FROM unit WHERE phase_id = ? LIMIT 1",
            [cycle['phase_id']], one=True
        )
        if unit:
            areas = query_db("""
                SELECT id FROM area_template
                WHERE tenant_id = ? AND unit_type = ?
            """, [tenant_id, unit['unit_type']])
            
            for area in areas:
                area_note = request.form.get('area_note_{}'.format(area['id']), '').strip()
                
                db.execute("""
                    DELETE FROM cycle_area_note WHERE cycle_id = ? AND area_template_id = ?
                """, [cycle_id, area['id']])
                
                if area_note:
                    note_id = generate_id()
                    db.execute("""
                        INSERT INTO cycle_area_note (id, tenant_id, cycle_id, area_template_id, note)
                        VALUES (?, ?, ?, ?, ?)
                    """, [note_id, tenant_id, cycle_id, area['id'], area_note])
        
        db.commit()
        
        return redirect(url_for('cycles.view_cycle', cycle_id=cycle_id))
    
    # GET - show edit form with item tree for exclusions
    unit = query_db(
        "SELECT unit_type FROM unit WHERE phase_id = ? LIMIT 1",
        [cycle['phase_id']], one=True
    )
    
    if not unit:
        abort(404)
    
    areas = query_db("""
        SELECT * FROM area_template
        WHERE tenant_id = ? AND unit_type = ?
        ORDER BY area_order
    """, [tenant_id, unit['unit_type']])
    
    area_notes = query_db("""
        SELECT area_template_id, note FROM cycle_area_note
        WHERE cycle_id = ?
    """, [cycle_id])
    area_notes_dict = {n['area_template_id']: n['note'] for n in area_notes}
    
    template_tree = []
    for area in areas:
        categories = query_db("""
            SELECT * FROM category_template
            WHERE area_id = ?
            ORDER BY category_order
        """, [area['id']])
        
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
            
            cat_list.append({
                'id': cat['id'],
                'name': cat['category_name'],
                'checklist': items
            })
        
        template_tree.append({
            'id': area['id'],
            'name': area['area_name'],
            'categories': cat_list,
            'note': area_notes_dict.get(area['id'], '')
        })
    
    units = query_db("""
        SELECT unit_number FROM unit 
        WHERE phase_id = ? 
        ORDER BY unit_number
    """, [cycle['phase_id']])
    
    return render_template('cycles/edit.html', cycle=cycle, template_tree=template_tree, units=units)


@cycles_bp.route('/<cycle_id>/exclude', methods=['POST'])
@require_team_lead
def toggle_exclusion(cycle_id):
    """Toggle item exclusion (HTMX)."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    item_id = request.form.get('item_id')
    reason = request.form.get('reason', '').strip()
    
    existing = query_db(
        "SELECT id FROM cycle_excluded_item WHERE cycle_id = ? AND item_template_id = ?",
        [cycle_id, item_id], one=True
    )
    
    if existing:
        db.execute("DELETE FROM cycle_excluded_item WHERE id = ?", [existing['id']])
        is_excluded = False
    else:
        exc_id = generate_id()
        db.execute("""
            INSERT INTO cycle_excluded_item (id, tenant_id, cycle_id, item_template_id, reason)
            VALUES (?, ?, ?, ?, ?)
        """, [exc_id, tenant_id, cycle_id, item_id, reason or None])
        is_excluded = True
    
    db.commit()
    
    item = query_db("SELECT item_description FROM item_template WHERE id = ?", [item_id], one=True)
    
    return render_template('cycles/_exclusion_row.html', 
                          item_id=item_id, 
                          item_description=item['item_description'],
                          is_excluded=is_excluded,
                          reason=reason,
                          cycle_id=cycle_id)


@cycles_bp.route('/<cycle_id>/assign', methods=['POST'])
@require_team_lead
def assign_inspector(cycle_id):
    """Assign inspector to unit for this cycle (HTMX)."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    unit_id = request.form.get('unit_id')
    inspector_id = request.form.get('inspector_id')
    
    if not unit_id:
        return '', 400
    
    if not inspector_id:
        # Remove assignment
        db.execute("""
            DELETE FROM cycle_unit_assignment 
            WHERE cycle_id = ? AND unit_id = ?
        """, [cycle_id, unit_id])
        db.commit()
        return '<span class="text-xs text-gray-400">Removed</span>'
    
    # Get inspector name
    inspector = query_db("SELECT name FROM inspector WHERE id = ?", [inspector_id], one=True)
    if not inspector:
        return '', 404
    
    # Upsert assignment
    existing = query_db(
        "SELECT id FROM cycle_unit_assignment WHERE cycle_id = ? AND unit_id = ?",
        [cycle_id, unit_id], one=True
    )
    
    if existing:
        db.execute("""
            UPDATE cycle_unit_assignment SET inspector_id = ? WHERE id = ?
        """, [inspector_id, existing['id']])
    else:
        assign_id = generate_id()
        db.execute("""
            INSERT INTO cycle_unit_assignment (id, tenant_id, cycle_id, unit_id, inspector_id)
            VALUES (?, ?, ?, ?, ?)
        """, [assign_id, tenant_id, cycle_id, unit_id, inspector_id])
    
    # Auto-set cycle.started_at on first assignment (if not already set)
    cycle = query_db("SELECT started_at FROM inspection_cycle WHERE id = ?", [cycle_id], one=True)
    if cycle and not cycle['started_at']:
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        db.execute("UPDATE inspection_cycle SET started_at = ? WHERE id = ?", [now, cycle_id])
        log_audit(db, tenant_id, 'cycle', cycle_id, 'cycle_started',
                  new_value='first_assignment',
                  user_id=session['user_id'], user_name=session['user_name'])
    
    log_audit(db, tenant_id, 'assignment', cycle_id, 'inspector_assigned',
              new_value=inspector_id,
              user_id=session['user_id'], user_name=session['user_name'],
              metadata=f'{{"unit_id": "{unit_id}", "inspector": "{inspector["name"]}"}}')
    
    db.commit()
    
    return '<span class="text-xs text-green-600">{}</span>'.format(inspector['name'])



@cycles_bp.route('/<cycle_id>/approve', methods=['POST'])
@require_manager
def approve_cycle(cycle_id):
    """Bulk sign off all units in a cycle - confirms defect lists are accurate."""
    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    cycle = query_db(
        "SELECT * FROM inspection_cycle WHERE id = ? AND tenant_id = ?",
        [cycle_id, tenant_id], one=True
    )

    if not cycle:
        abort(404)

    if cycle['approved_at']:
        flash('This cycle has already been signed off.', 'error')
        return redirect(url_for('cycles.list_cycles'))

    # Bulk move all reviewed inspections to pending_followup
    db.execute("""
        UPDATE inspection SET status = 'pending_followup', updated_at = ?
        WHERE cycle_id = ? AND tenant_id = ? AND status = 'reviewed'
    """, [now, cycle_id, tenant_id])
    updated = db.execute("SELECT changes()").fetchone()[0]

    # Set cycle approval timestamp
    db.execute("""
        UPDATE inspection_cycle SET approved_at = ?, approved_by = ?
        WHERE id = ?
    """, [now, session['user_name'], cycle_id])

    log_audit(db, tenant_id, 'cycle', cycle_id, 'approved',
              new_value='signed_off',
              user_id=session['user_id'], user_name=session['user_name'])

    db.commit()

    block = cycle['block'] or 'Cycle'
    flash(f'Defect lists signed off for {block}. {updated} units moved to pending contractor rectification.', 'success')
    return redirect(url_for('cycles.list_cycles'))


@cycles_bp.route('/<cycle_id>/push-pdfs', methods=['POST'])
@require_manager
def push_pdfs(cycle_id):
    """Generate PDFs for all units in a cycle and push to SharePoint via Make webhook."""
    import os
    import base64
    import json
    import urllib.request
    import urllib.error
    from app.services.pdf_generator import generate_defects_pdf, generate_pdf_filename

    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    cycle = query_db(
        "SELECT * FROM inspection_cycle WHERE id = ? AND tenant_id = ?",
        [cycle_id, tenant_id], one=True
    )

    if not cycle:
        abort(404)

    if not cycle['approved_at']:
        flash('Cycle must be signed off before pushing PDFs.', 'error')
        return redirect(url_for('cycles.list_cycles'))

    if cycle['pdfs_pushed_at']:
        flash('PDFs have already been pushed for this cycle.', 'error')
        return redirect(url_for('cycles.list_cycles'))

    webhook_url = os.environ.get('MAKE_WEBHOOK_URL', '')
    if not webhook_url:
        flash('Make webhook URL not configured. Set MAKE_WEBHOOK_URL environment variable in Render.', 'error')
        return redirect(url_for('cycles.list_cycles'))

    # Get all units in this cycle
    units = [dict(r) for r in query_db("""
        SELECT u.id, u.unit_number, u.block, u.floor,
               i.inspection_date, i.id AS inspection_id
        FROM inspection i
        JOIN unit u ON i.unit_id = u.id
        WHERE i.cycle_id = ? AND i.tenant_id = ?
        ORDER BY u.unit_number
    """, [cycle_id, tenant_id])]

    if not units:
        flash('No units found in this cycle.', 'error')
        return redirect(url_for('cycles.list_cycles'))

    floor_names = {0: 'Ground Floor', 1: '1st Floor', 2: '2nd Floor', 3: '3rd Floor'}
    success_count = 0
    fail_count = 0
    errors = []

    for unit in units:
        try:
            # Generate PDF
            pdf_bytes = generate_defects_pdf(tenant_id, unit['id'], cycle_id)
            if not pdf_bytes:
                errors.append(f"Unit {unit['unit_number']}: PDF generation failed")
                fail_count += 1
                continue

            # Generate filename
            filename = generate_pdf_filename(
                unit, cycle,
                inspection_date=unit.get('inspection_date')
            )

            # Build payload for Make
            payload = json.dumps({
                'filename': filename,
                'unit_number': unit['unit_number'],
                'block': unit.get('block', ''),
                'floor': floor_names.get(unit.get('floor'), ''),
                'cycle_number': cycle['cycle_number'],
                'cycle_id': cycle_id,
                'pdf_base64': base64.b64encode(pdf_bytes).decode('ascii')
            }).encode('utf-8')

            # POST to Make webhook
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status in (200, 201, 202):
                    success_count += 1
                else:
                    errors.append(f"Unit {unit['unit_number']}: HTTP {resp.status}")
                    fail_count += 1

        except urllib.error.URLError as e:
            errors.append(f"Unit {unit['unit_number']}: {str(e)[:100]}")
            fail_count += 1
        except Exception as e:
            errors.append(f"Unit {unit['unit_number']}: {str(e)[:100]}")
            fail_count += 1

    # Update cycle status
    if success_count > 0:
        push_status = 'complete' if fail_count == 0 else 'partial'
        db.execute("""
            UPDATE inspection_cycle
            SET pdfs_pushed_at = ?, pdfs_push_status = ?
            WHERE id = ?
        """, [now, push_status, cycle_id])

        log_audit(db, tenant_id, 'cycle', cycle_id, 'pdfs_pushed',
                  new_value=f'{success_count}/{success_count + fail_count} PDFs pushed',
                  user_id=session['user_id'], user_name=session['user_name'])

        db.commit()

    block = cycle['block'] or 'Cycle'
    if fail_count == 0:
        flash(f'{success_count} PDFs pushed to SharePoint for {block}.', 'success')
    elif success_count > 0:
        flash(f'{success_count} PDFs pushed, {fail_count} failed for {block}. Errors: {"; ".join(errors[:3])}', 'error')
    else:
        flash(f'All {fail_count} PDFs failed for {block}. First error: {errors[0] if errors else "Unknown"}', 'error')

    return redirect(url_for('cycles.list_cycles'))


@cycles_bp.route('/<cycle_id>/close', methods=['POST'])
@require_manager
def close_cycle(cycle_id):
    """Close a cycle (no more inspections allowed)."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    cycle = query_db(
        "SELECT * FROM inspection_cycle WHERE id = ? AND tenant_id = ?",
        [cycle_id, tenant_id], one=True
    )
    
    if not cycle:
        abort(404)
    
    db.execute("UPDATE inspection_cycle SET status = 'closed' WHERE id = ?", [cycle_id])
    
    log_audit(db, tenant_id, 'cycle', cycle_id, 'status_change',
              old_value='active', new_value='closed',
              user_id=session['user_id'], user_name=session['user_name'])
    
    db.commit()
    
    return redirect(url_for('cycles.view_cycle', cycle_id=cycle_id))


@cycles_bp.route('/<cycle_id>/reopen', methods=['POST'])
@require_manager
def reopen_cycle(cycle_id):
    """Reopen a closed cycle."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    cycle = query_db(
        "SELECT * FROM inspection_cycle WHERE id = ? AND tenant_id = ?",
        [cycle_id, tenant_id], one=True
    )
    
    if not cycle:
        abort(404)
    
    db.execute("UPDATE inspection_cycle SET status = 'active' WHERE id = ?", [cycle_id])
    
    log_audit(db, tenant_id, 'cycle', cycle_id, 'status_change',
              old_value='closed', new_value='active',
              user_id=session['user_id'], user_name=session['user_name'])
    
    db.commit()
    
    return redirect(url_for('cycles.view_cycle', cycle_id=cycle_id))


@cycles_bp.route('/<cycle_id>/delete', methods=['POST'])
@require_manager
def delete_cycle(cycle_id):
    """Delete a cycle (only if no inspections started)."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    cycle = query_db(
        "SELECT * FROM inspection_cycle WHERE id = ? AND tenant_id = ?",
        [cycle_id, tenant_id], one=True
    )
    
    if not cycle:
        abort(404)
    
    inspections = query_db(
        "SELECT COUNT(*) as count FROM inspection WHERE cycle_id = ?",
        [cycle_id], one=True
    )
    
    if inspections['count'] > 0:
        flash('Cannot delete: {} inspection(s) exist for this cycle'.format(inspections['count']), 'error')
        return redirect(url_for('cycles.view_cycle', cycle_id=cycle_id))
    
    # Delete in order: area notes, excluded items, excluded units, assignments, then cycle
    db.execute("DELETE FROM cycle_area_note WHERE cycle_id = ?", [cycle_id])
    db.execute("DELETE FROM cycle_excluded_item WHERE cycle_id = ?", [cycle_id])
    db.execute("DELETE FROM cycle_excluded_unit WHERE cycle_id = ?", [cycle_id])
    db.execute("DELETE FROM cycle_unit_assignment WHERE cycle_id = ?", [cycle_id])
    db.execute("DELETE FROM inspection_cycle WHERE id = ?", [cycle_id])
    db.commit()
    
    flash('Cycle {} deleted'.format(cycle['cycle_number']), 'success')
    return redirect(url_for('cycles.list_cycles'))


@cycles_bp.route('/<cycle_id>/exclude-unit', methods=['POST'])
@require_team_lead
def toggle_unit_exclusion(cycle_id):
    """Toggle unit exclusion from this cycle."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    unit_id = request.form.get('unit_id')
    
    if not unit_id:
        abort(400)
    
    existing = query_db(
        "SELECT id FROM cycle_excluded_unit WHERE cycle_id = ? AND unit_id = ?",
        [cycle_id, unit_id], one=True
    )
    
    if existing:
        db.execute("DELETE FROM cycle_excluded_unit WHERE id = ?", [existing['id']])
        flash('Unit included back in cycle', 'success')
    else:
        exc_id = generate_id()
        db.execute("""
            INSERT INTO cycle_excluded_unit (id, tenant_id, cycle_id, unit_id)
            VALUES (?, ?, ?, ?)
        """, [exc_id, tenant_id, cycle_id, unit_id])
        flash('Unit excluded from cycle', 'success')
    
    db.commit()
    
    return redirect(url_for('cycles.manage_units', cycle_id=cycle_id))


@cycles_bp.route('/<cycle_id>/add-unit', methods=['POST'])
@require_team_lead
def add_unit(cycle_id):
    """Add a new unit to this cycle."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    cycle = query_db(
        "SELECT * FROM inspection_cycle WHERE id = ? AND tenant_id = ?",
        [cycle_id, tenant_id], one=True
    )
    
    if not cycle or cycle['status'] != 'active':
        abort(404)
    
    unit_number = request.form.get('unit_number', '').strip().zfill(3)
    block = request.form.get('block', '').strip() or None
    floor_val = request.form.get('floor', '0')
    floor = int(floor_val) if floor_val.strip() != '' else 0
    unit_type = request.form.get('unit_type', '4-Bed').strip()
    
    # Check if unit already exists
    existing = query_db(
        "SELECT id, unit_number FROM unit WHERE unit_number = ? AND phase_id = ?",
        [unit_number, cycle['phase_id']], one=True
    )
    
    if existing:
        flash('Unit {} already exists'.format(unit_number), 'error')
        return redirect(url_for('cycles.manage_units', cycle_id=cycle_id))
    
    # Create unit
    unit_id = generate_id()
    db.execute("""
        INSERT INTO unit (id, tenant_id, phase_id, unit_number, unit_type, block, floor, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'not_started')
    """, [unit_id, tenant_id, cycle['phase_id'], unit_number, unit_type, block, floor])
    
    # Expand cycle range if needed
    new_start = cycle['unit_start']
    new_end = cycle['unit_end']
    if new_start is None or unit_number < new_start:
        new_start = unit_number
    if new_end is None or unit_number > new_end:
        new_end = unit_number
    
    if new_start != cycle['unit_start'] or new_end != cycle['unit_end']:
        db.execute("""
            UPDATE inspection_cycle SET unit_start = ?, unit_end = ? WHERE id = ?
        """, [new_start, new_end, cycle_id])
    
    db.commit()
    
    flash('Unit {} added'.format(unit_number), 'success')
    return redirect(url_for('cycles.manage_units', cycle_id=cycle_id))
