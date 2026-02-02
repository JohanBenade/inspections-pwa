"""
Cycle routes - Inspection cycle management for architect.
Create cycles, set exclusions, add general notes.
"""
from datetime import date
from flask import Blueprint, render_template, session, redirect, url_for, abort, request
from app.auth import require_team_lead, require_manager
from app.utils import generate_id
from app.services.db import get_db, query_db

cycles_bp = Blueprint('cycles', __name__, url_prefix='/cycles')


@cycles_bp.route('/')
@require_team_lead
def list_cycles():
    """List all inspection cycles for current phase."""
    tenant_id = session['tenant_id']
    
    # Get first phase for now (single project assumption)
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
        SELECT ic.*,
            insp.name as created_by_name,
            (SELECT COUNT(*) FROM unit u WHERE u.phase_id = ic.phase_id) as total_units,
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
    """Create a new inspection cycle."""
    tenant_id = session['tenant_id']
    user_id = session['user_id']
    db = get_db()
    
    # Get phase
    phase = query_db("""
        SELECT ph.*, p.project_name
        FROM phase ph
        JOIN project p ON ph.project_id = p.id
        WHERE ph.tenant_id = ?
        LIMIT 1
    """, [tenant_id], one=True)
    
    if not phase:
        abort(404)
    
    # Get all units for dropdown
    units = query_db("""
        SELECT unit_number FROM unit 
        WHERE phase_id = ? 
        ORDER BY unit_number
    """, [phase['id']])
    
    if request.method == 'POST':
        general_notes = request.form.get('general_notes', '').strip()
        unit_start = request.form.get('unit_start', '').strip() or None
        unit_end = request.form.get('unit_end', '').strip() or None
        
        # Get next cycle number
        last_cycle = query_db(
            "SELECT MAX(cycle_number) as max_num FROM inspection_cycle WHERE phase_id = ?",
            [phase['id']], one=True
        )
        next_number = (last_cycle['max_num'] or 0) + 1
        
        # Create cycle
        cycle_id = generate_id()
        db.execute("""
            INSERT INTO inspection_cycle (id, tenant_id, phase_id, cycle_number, unit_start, unit_end, general_notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [cycle_id, tenant_id, phase['id'], next_number, unit_start, unit_end, general_notes or None, user_id])
        
        db.commit()
        
        return redirect(url_for('cycles.edit_cycle', cycle_id=cycle_id))
    
    # GET - show form
    last_cycle = query_db(
        "SELECT MAX(cycle_number) as max_num FROM inspection_cycle WHERE phase_id = ?",
        [phase['id']], one=True
    )
    next_number = (last_cycle['max_num'] or 0) + 1
    
    return render_template('cycles/create.html', phase=phase, next_number=next_number, units=units)


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
    
    units = query_db(f"""
        SELECT u.unit_number, u.status as unit_status, u.id as unit_id,
            i.id as inspection_id, i.status as inspection_status,
            i.inspection_date, i.inspector_name,
            (SELECT COUNT(*) FROM defect d WHERE d.unit_id = u.id AND d.status = 'open') as open_defects
        FROM unit u
        LEFT JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = ?
        WHERE u.phase_id = ? {range_filter}
        ORDER BY u.unit_number
    """, params)
    
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
    
    return render_template('cycles/view.html', cycle=cycle, units=units, excluded=excluded, 
                          area_notes=area_notes, has_inspections=has_inspections)


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
        general_notes = request.form.get('general_notes', '').strip()
        unit_start = request.form.get('unit_start', '').strip() or None
        unit_end = request.form.get('unit_end', '').strip() or None
        
        db.execute("""
            UPDATE inspection_cycle SET general_notes = ?, unit_start = ?, unit_end = ? WHERE id = ?
        """, [general_notes or None, unit_start, unit_end, cycle_id])
        
        # Save area notes
        # First get all areas
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
                area_note = request.form.get(f'area_note_{area["id"]}', '').strip()
                
                # Delete existing note
                db.execute("""
                    DELETE FROM cycle_area_note WHERE cycle_id = ? AND area_template_id = ?
                """, [cycle_id, area['id']])
                
                # Insert if not empty
                if area_note:
                    from app.utils import generate_id
                    note_id = generate_id()
                    db.execute("""
                        INSERT INTO cycle_area_note (id, tenant_id, cycle_id, area_template_id, note)
                        VALUES (?, ?, ?, ?, ?)
                    """, [note_id, tenant_id, cycle_id, area['id'], area_note])
        
        db.commit()
        
        return redirect(url_for('cycles.view_cycle', cycle_id=cycle_id))
    
    # GET - show edit form with item tree for exclusions
    # Get unit type from first unit
    unit = query_db(
        "SELECT unit_type FROM unit WHERE phase_id = ? LIMIT 1",
        [cycle['phase_id']], one=True
    )
    
    if not unit:
        abort(404)
    
    # Get all areas with categories and items
    areas = query_db("""
        SELECT * FROM area_template
        WHERE tenant_id = ? AND unit_type = ?
        ORDER BY area_order
    """, [tenant_id, unit['unit_type']])
    
    # Get existing area notes
    area_notes = query_db("""
        SELECT area_template_id, note FROM cycle_area_note
        WHERE cycle_id = ?
    """, [cycle_id])
    area_notes_dict = {n['area_template_id']: n['note'] for n in area_notes}
    
    # Build tree structure
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
    
    # Get all units for range dropdowns
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
    
    # Check if already excluded
    existing = query_db(
        "SELECT id FROM cycle_excluded_item WHERE cycle_id = ? AND item_template_id = ?",
        [cycle_id, item_id], one=True
    )
    
    if existing:
        # Remove exclusion
        db.execute("DELETE FROM cycle_excluded_item WHERE id = ?", [existing['id']])
        is_excluded = False
    else:
        # Add exclusion
        exc_id = generate_id()
        db.execute("""
            INSERT INTO cycle_excluded_item (id, tenant_id, cycle_id, item_template_id, reason)
            VALUES (?, ?, ?, ?, ?)
        """, [exc_id, tenant_id, cycle_id, item_id, reason or None])
        is_excluded = True
    
    db.commit()
    
    # Return updated checkbox state
    item = query_db("SELECT item_description FROM item_template WHERE id = ?", [item_id], one=True)
    
    return render_template('cycles/_exclusion_row.html', 
                          item_id=item_id, 
                          item_description=item['item_description'],
                          is_excluded=is_excluded,
                          reason=reason,
                          cycle_id=cycle_id)


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
    
    # Check if any inspections exist for this cycle
    inspections = query_db(
        "SELECT COUNT(*) as count FROM inspection WHERE cycle_id = ?",
        [cycle_id], one=True
    )
    
    if inspections['count'] > 0:
        from flask import flash
        flash(f"Cannot delete: {inspections['count']} inspection(s) exist for this cycle", 'error')
        return redirect(url_for('cycles.view_cycle', cycle_id=cycle_id))
    
    # Delete in order: area notes, excluded items, then cycle
    db.execute("DELETE FROM cycle_area_note WHERE cycle_id = ?", [cycle_id])
    db.execute("DELETE FROM cycle_excluded_item WHERE cycle_id = ?", [cycle_id])
    db.execute("DELETE FROM inspection_cycle WHERE id = ?", [cycle_id])
    db.commit()
    
    from flask import flash
    flash(f"Cycle {cycle['cycle_number']} deleted", 'success')
    return redirect(url_for('cycles.list_cycles'))
