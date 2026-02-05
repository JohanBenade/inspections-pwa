"""
Cycle routes - Inspection cycle management.
Create cycles, set exclusions, add general notes, assign inspectors.
"""
import re
from datetime import date
from flask import Blueprint, render_template, session, redirect, url_for, abort, request, flash
from app.auth import require_team_lead, require_manager
from app.utils import generate_id
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
            (SELECT COUNT(*) FROM cycle_excluded_item cei WHERE cei.cycle_id = ic.id) as excluded_count
        FROM inspection_cycle ic
        JOIN inspector insp ON ic.created_by = insp.id
        WHERE ic.phase_id = ?
        ORDER BY ic.cycle_number DESC
    """, [phase['id']])
    
    return render_template('cycles/list.html', phase=phase, cycles=cycles)


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
        
        # Create cycle record
        cycle_id = generate_id()
        db.execute("""
            INSERT INTO inspection_cycle 
            (id, tenant_id, phase_id, cycle_number, unit_start, unit_end, block, floor, general_notes, exclusion_notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [cycle_id, tenant_id, phase['id'], cycle_number, unit_start, unit_end, block, floor, general_notes, exclusion_notes, user_id])
        
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
            i.inspection_date, i.inspector_name,
            (SELECT COUNT(*) FROM defect d WHERE d.unit_id = u.id AND d.status = 'open') as open_defects
        FROM unit u
        LEFT JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = ?
        WHERE u.phase_id = ? {}
        ORDER BY u.unit_number
    """.format(range_filter), params)
    
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
        
        db.execute("""
            UPDATE inspection_cycle SET general_notes = ?, exclusion_notes = ?, unit_start = ?, unit_end = ? WHERE id = ?
        """, [general_notes, exclusion_notes, unit_start, unit_end, cycle_id])
        
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
    
    db.commit()
    
    return '<span class="text-xs text-green-600">{}</span>'.format(inspector['name'])


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
