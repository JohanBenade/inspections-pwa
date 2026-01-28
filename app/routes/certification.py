"""
Certification routes - Architect's management dashboard.
View units by status, certify cleared units, reopen if needed.
"""
from flask import Blueprint, render_template, session, redirect, url_for, abort, request
from app.auth import require_architect
from app.services.db import get_db, query_db

certification_bp = Blueprint('certification', __name__, url_prefix='/certification')


# Status display configuration
STATUS_INFO = {
    'certified': {
        'title': 'Certified',
        'description': 'Units signed off by architect',
        'color': 'green',
        'icon': '✓'
    },
    'cleared': {
        'title': 'Ready to Certify',
        'description': 'All items OK - awaiting sign-off',
        'color': 'blue',
        'icon': '○'
    },
    'defects_open': {
        'title': 'Defects Open',
        'description': 'Submitted with outstanding defects',
        'color': 'red',
        'icon': '!'
    },
    'in_progress': {
        'title': 'In Progress',
        'description': 'Inspection underway',
        'color': 'yellow',
        'icon': '⋯'
    },
    'not_started': {
        'title': 'Not Started',
        'description': 'No inspection yet',
        'color': 'gray',
        'icon': '−'
    }
}


@certification_bp.route('/')
@require_architect
def dashboard():
    """Certification Dashboard - units grouped by status."""
    tenant_id = session['tenant_id']
    
    # Get cycle filter
    cycle_filter = request.args.get('cycle')
    
    # Get all active cycles for filter dropdown
    active_cycles = query_db("""
        SELECT ic.*, ph.phase_name
        FROM inspection_cycle ic
        JOIN phase ph ON ic.phase_id = ph.id
        WHERE ic.tenant_id = ? AND ic.status = 'active'
        ORDER BY ic.cycle_number
    """, [tenant_id])
    
    # Get all units with inspection summary
    units = query_db("""
        SELECT 
            u.id,
            u.block,
            u.floor,
            u.unit_number,
            u.unit_number AS unit_code,
            u.unit_type,
            u.status,
            ph.phase_name,
            p.project_name,
            (SELECT MAX(ic.cycle_number) FROM inspection i 
             JOIN inspection_cycle ic ON i.cycle_id = ic.id
             WHERE i.unit_id = u.id) AS current_cycle,
            (SELECT COUNT(*) FROM defect WHERE unit_id = u.id AND status = 'open') AS open_defects,
            (SELECT COUNT(*) FROM defect WHERE unit_id = u.id AND status = 'cleared') AS cleared_defects,
            (SELECT i.inspector_name FROM inspection i 
             JOIN inspection_cycle ic ON i.cycle_id = ic.id
             WHERE i.unit_id = u.id 
             ORDER BY ic.cycle_number DESC LIMIT 1) AS last_inspector,
            (SELECT i.inspection_date FROM inspection i 
             JOIN inspection_cycle ic ON i.cycle_id = ic.id
             WHERE i.unit_id = u.id 
             ORDER BY ic.cycle_number DESC LIMIT 1) AS last_inspection_date,
            (SELECT ic.cycle_number FROM inspection_cycle ic
             WHERE ic.phase_id = u.phase_id AND ic.status = 'active'
             AND (ic.unit_start IS NULL OR (u.unit_number >= ic.unit_start AND u.unit_number <= ic.unit_end))
             ORDER BY ic.cycle_number LIMIT 1) AS assigned_cycle
        FROM unit u
        JOIN phase ph ON u.phase_id = ph.id
        JOIN project p ON ph.project_id = p.id
        WHERE u.tenant_id = ?
        ORDER BY u.unit_number
    """, [tenant_id])
    
    # Filter by cycle if specified
    if cycle_filter:
        cycle = query_db("SELECT * FROM inspection_cycle WHERE id = ?", [cycle_filter], one=True)
        if cycle and cycle['unit_start'] and cycle['unit_end']:
            units = [u for u in units if u['unit_number'] >= cycle['unit_start'] and u['unit_number'] <= cycle['unit_end']]
    
    # Group by status
    grouped = {
        'certified': [],
        'cleared': [],
        'defects_open': [],
        'in_progress': [],
        'not_started': []
    }
    
    for unit in units:
        status = unit['status'] or 'not_started'
        if status in grouped:
            grouped[status].append(unit)
        else:
            grouped['not_started'].append(unit)
    
    # Summary counts
    summary = {
        'total': len(units),
        'certified': len(grouped['certified']),
        'ready': len(grouped['cleared']),
        'defects': len(grouped['defects_open']),
        'in_progress': len(grouped['in_progress']),
        'not_started': len(grouped['not_started'])
    }
    
    return render_template('certification/dashboard.html',
                          grouped=grouped, status_info=STATUS_INFO, summary=summary,
                          active_cycles=active_cycles, cycle_filter=cycle_filter)


@certification_bp.route('/unit/<unit_id>')
@require_architect
def view_unit(unit_id):
    """Redirect to inspection page for this unit."""
    tenant_id = session['tenant_id']
    
    unit = query_db(
        "SELECT * FROM unit WHERE id = ? AND tenant_id = ?",
        [unit_id, tenant_id], one=True
    )
    
    if not unit:
        abort(404)
    
    # Find latest inspection for this unit
    inspection = query_db("""
        SELECT i.id FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.unit_id = ?
        ORDER BY ic.cycle_number DESC
        LIMIT 1
    """, [unit_id], one=True)
    
    if inspection:
        # Go to existing inspection
        return redirect(url_for('inspection.inspect', inspection_id=inspection['id']))
    else:
        # Start new inspection
        return redirect(url_for('inspection.start_inspection', unit_id=unit_id))


@certification_bp.route('/unit/<unit_id>/certify', methods=['POST'])
@require_architect
def certify_unit(unit_id):
    """Certify a cleared unit (architect sign-off)."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    unit = query_db(
        "SELECT * FROM unit WHERE id = ? AND tenant_id = ?",
        [unit_id, tenant_id], one=True
    )
    
    if not unit:
        abort(404)
    
    if unit['status'] != 'cleared':
        return "Unit must be in 'cleared' status to certify", 400
    
    db.execute("UPDATE unit SET status = 'certified' WHERE id = ?", [unit_id])
    db.commit()
    
    return redirect(url_for('certification.dashboard'))


@certification_bp.route('/unit/<unit_id>/reopen', methods=['POST'])
@require_architect
def reopen_unit(unit_id):
    """Reopen a certified unit (new defect found)."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    unit = query_db(
        "SELECT * FROM unit WHERE id = ? AND tenant_id = ?",
        [unit_id, tenant_id], one=True
    )
    
    if not unit:
        abort(404)
    
    if unit['status'] != 'certified':
        return "Only certified units can be reopened", 400
    
    db.execute("UPDATE unit SET status = 'defects_open' WHERE id = ?", [unit_id])
    db.commit()
    
    return redirect(url_for('certification.view_unit', unit_id=unit_id))


@certification_bp.route('/unit/<unit_id>/defect/<defect_id>/update', methods=['POST'])
@require_architect
def update_defect(unit_id, defect_id):
    """Update defect comment or status (architect override)."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    defect = query_db(
        "SELECT * FROM defect WHERE id = ? AND tenant_id = ?",
        [defect_id, tenant_id], one=True
    )
    
    if not defect:
        abort(404)
    
    new_comment = request.form.get('comment', '').strip()
    new_status = request.form.get('status')
    
    if new_status == 'cleared':
        db.execute("""
            UPDATE defect
            SET status = 'cleared',
                clearance_note = ?,
                cleared_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, [new_comment, defect_id])
    else:
        db.execute("""
            UPDATE defect
            SET original_comment = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, [new_comment, defect_id])
    
    db.commit()
    
    # Check if all defects cleared - update unit status
    open_count = query_db(
        "SELECT COUNT(*) as count FROM defect WHERE unit_id = ? AND status = 'open'",
        [unit_id], one=True
    )['count']
    
    if open_count == 0:
        db.execute("UPDATE unit SET status = 'cleared' WHERE id = ?", [unit_id])
        db.commit()
    
    return redirect(url_for('certification.view_unit', unit_id=unit_id))


@certification_bp.route('/unit/<unit_id>/category-note', methods=['POST'])
@require_architect
def update_category_note(unit_id):
    """Update a category note for a unit."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    unit = query_db(
        "SELECT * FROM unit WHERE id = ? AND tenant_id = ?",
        [unit_id, tenant_id], one=True
    )
    
    if not unit:
        abort(404)
    
    category_id = request.form.get('category_id')
    note = request.form.get('note', '').strip()
    
    # Get latest active cycle for this phase (needed for raised_cycle_id)
    latest_cycle = query_db("""
        SELECT id FROM inspection_cycle 
        WHERE phase_id = ? AND status = 'active'
        ORDER BY cycle_number DESC LIMIT 1
    """, [unit['phase_id']], one=True)
    
    cycle_id = latest_cycle['id'] if latest_cycle else None
    
    # Get or create category_comment
    existing = query_db("""
        SELECT id FROM category_comment 
        WHERE unit_id = ? AND category_template_id = ?
    """, [unit_id, category_id], one=True)
    
    if existing:
        cc_id = existing['id']
    else:
        from app.utils import generate_id
        cc_id = generate_id('cc')
        db.execute("""
            INSERT INTO category_comment (id, tenant_id, unit_id, category_template_id, raised_cycle_id, status)
            VALUES (?, ?, ?, ?, ?, 'open')
        """, [cc_id, tenant_id, unit_id, category_id, cycle_id])
    
    # Add history entry
    from app.utils import generate_id
    db.execute("""
        INSERT INTO category_comment_history 
        (id, tenant_id, category_comment_id, cycle_id, comment, status, updated_by, created_at)
        VALUES (?, ?, ?, ?, ?, 'open', ?, CURRENT_TIMESTAMP)
    """, [generate_id('cch'), tenant_id, cc_id, cycle_id, note, session['user_id']])
    
    db.commit()
    
    return redirect(url_for('certification.view_unit', unit_id=unit_id))
