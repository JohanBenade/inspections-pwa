"""
Certification routes - Architect's management dashboard.
View units by status, review, approve, certify, and close.
"""
from flask import Blueprint, render_template, session, redirect, url_for, abort, request, flash
from app.auth import require_team_lead, require_manager, get_role_level
from app.services.db import get_db, query_db

certification_bp = Blueprint('certification', __name__, url_prefix='/certification')


STATUS_INFO = {
    'certified': {
        'title': 'Certified',
        'description': 'Units signed off by architect',
        'color': 'green',
        'icon': 'check'
    },
    'approved': {
        'title': 'Approved',
        'description': 'Ready for PDF and close',
        'color': 'emerald',
        'icon': 'thumb-up'
    },
    'awaiting_approval': {
        'title': 'Awaiting Approval',
        'description': 'Reviewed by Team Lead - needs Manager approval',
        'color': 'indigo',
        'icon': 'stamp'
    },
    'awaiting_review': {
        'title': 'Awaiting Review',
        'description': 'Submitted - needs Team Lead review',
        'color': 'purple',
        'icon': 'eye'
    },
    'defects_open': {
        'title': 'Defects Open',
        'description': 'Has outstanding defects',
        'color': 'red',
        'icon': '!'
    },
    'in_progress': {
        'title': 'In Progress',
        'description': 'Inspection underway',
        'color': 'yellow',
        'icon': '...'
    },
    'not_started': {
        'title': 'Not Started',
        'description': 'No inspection yet',
        'color': 'gray',
        'icon': '-'
    }
}


def get_unit_workflow_status(unit):
    """
    Determine the workflow status for a unit based on inspection status and defects.
    Returns one of: certified, approved, awaiting_approval, awaiting_review, 
                    defects_open, in_progress, not_started
    """
    # No inspection yet
    if unit['inspection_id'] is None:
        return 'not_started'
    
    inspection_status = unit['inspection_status'] or 'in_progress'
    unit_status = unit['unit_status']
    open_defects = unit['open_defects'] or 0
    
    # Already certified at unit level
    if unit_status == 'certified':
        return 'certified'
    
    # Map inspection status to workflow status
    if inspection_status == 'closed':
        return 'certified'
    elif inspection_status == 'approved':
        return 'approved'
    elif inspection_status == 'reviewed':
        return 'awaiting_approval'
    elif inspection_status == 'submitted':
        return 'awaiting_review'
    elif inspection_status == 'in_progress':
        return 'in_progress'
    else:
        return 'not_started'


@certification_bp.route('/')
@require_team_lead
def dashboard():
    """Certification Dashboard - units grouped by workflow status."""
    tenant_id = session['tenant_id']
    user_role = session.get('role', 'inspector')
    
    cycle_filter = request.args.get('cycle')
    
    active_cycles = query_db("""
        SELECT ic.*, ph.phase_name
        FROM inspection_cycle ic
        JOIN phase ph ON ic.phase_id = ph.id
        WHERE ic.tenant_id = ? AND ic.status = 'active'
        ORDER BY ic.cycle_number
    """, [tenant_id])
    
    if cycle_filter:
        filter_cycle = query_db("SELECT * FROM inspection_cycle WHERE id = ?", [cycle_filter], one=True)
        filter_cycle_num = filter_cycle['cycle_number'] if filter_cycle else 1
        
        units = query_db("""
            SELECT 
                u.id,
                u.unit_number,
                u.unit_number AS unit_code,
                u.status AS unit_status,
                ? AS current_cycle,
                ? AS cycle_id,
                i.id AS inspection_id,
                i.status AS inspection_status,
                i.inspector_name AS last_inspector,
                i.inspection_date AS last_inspection_date,
                i.submitted_at,
                (SELECT COUNT(*) FROM defect d 
                 JOIN inspection_cycle ic_r ON d.raised_cycle_id = ic_r.id
                 LEFT JOIN inspection_cycle ic_c ON d.cleared_cycle_id = ic_c.id
                 WHERE d.unit_id = u.id 
                 AND ic_r.cycle_number <= ?
                 AND (d.cleared_cycle_id IS NULL OR ic_c.cycle_number > ?)
                ) AS open_defects,
                (SELECT COUNT(*) FROM defect d 
                 JOIN inspection_cycle ic_c ON d.cleared_cycle_id = ic_c.id
                 WHERE d.unit_id = u.id 
                 AND ic_c.cycle_number = ?
                ) AS cleared_defects
            FROM unit u
            JOIN inspection_cycle ic ON ic.id = ?
            LEFT JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = ?
            WHERE u.tenant_id = ? 
            AND (ic.unit_start IS NULL OR (u.unit_number >= ic.unit_start AND u.unit_number <= ic.unit_end))
            ORDER BY u.unit_number
        """, [filter_cycle_num, cycle_filter, filter_cycle_num, filter_cycle_num, filter_cycle_num, cycle_filter, cycle_filter, tenant_id])
    else:
        units = query_db("""
            SELECT 
                u.id,
                u.unit_number,
                u.unit_number AS unit_code,
                u.status AS unit_status,
                latest.cycle_number AS current_cycle,
                latest.cycle_id,
                latest.inspection_id,
                latest.inspection_status,
                latest.inspector_name AS last_inspector,
                latest.inspection_date AS last_inspection_date,
                latest.submitted_at,
                (SELECT COUNT(*) FROM defect d WHERE d.unit_id = u.id AND d.status = 'open') AS open_defects,
                (SELECT COUNT(*) FROM defect d WHERE d.unit_id = u.id AND d.status = 'cleared') AS cleared_defects
            FROM unit u
            LEFT JOIN (
                SELECT 
                    i.unit_id,
                    i.id AS inspection_id,
                    i.status AS inspection_status,
                    i.inspector_name,
                    i.inspection_date,
                    i.submitted_at,
                    ic.cycle_number,
                    ic.id AS cycle_id,
                    ROW_NUMBER() OVER (PARTITION BY i.unit_id ORDER BY ic.cycle_number DESC) as rn
                FROM inspection i
                JOIN inspection_cycle ic ON i.cycle_id = ic.id
            ) latest ON latest.unit_id = u.id AND latest.rn = 1
            WHERE u.tenant_id = ?
            ORDER BY u.unit_number
        """, [tenant_id])
    
    # Group by workflow status
    grouped = {
        'certified': [],
        'approved': [],
        'awaiting_approval': [],
        'awaiting_review': [],
        'defects_open': [],
        'in_progress': [],
        'not_started': []
    }
    
    for unit in units:
        status = get_unit_workflow_status(unit)
        # Override with defects_open if has open defects and not in workflow
        if unit['open_defects'] and unit['open_defects'] > 0 and status in ('approved', 'awaiting_approval', 'awaiting_review'):
            # Keep workflow status but note defects
            pass
        grouped[status].append(unit)
    
    summary = {
        'total': len(units),
        'certified': len(grouped['certified']),
        'approved': len(grouped['approved']),
        'awaiting_approval': len(grouped['awaiting_approval']),
        'awaiting_review': len(grouped['awaiting_review']),
        'defects': len(grouped['defects_open']),
        'in_progress': len(grouped['in_progress']),
        'not_started': len(grouped['not_started'])
    }
    
    return render_template('certification/dashboard.html',
                          grouped=grouped, 
                          status_info=STATUS_INFO, 
                          summary=summary,
                          active_cycles=active_cycles, 
                          cycle_filter=cycle_filter,
                          user_role=user_role)


@certification_bp.route('/unit/<unit_id>')
@require_team_lead
def view_unit(unit_id):
    """Redirect to inspection page for this unit."""
    tenant_id = session['tenant_id']
    cycle_id = request.args.get('cycle')
    
    unit = query_db(
        "SELECT * FROM unit WHERE id = ? AND tenant_id = ?",
        [unit_id, tenant_id], one=True
    )
    
    if not unit:
        abort(404)
    
    if cycle_id:
        inspection = query_db(
            "SELECT id FROM inspection WHERE unit_id = ? AND cycle_id = ?",
            [unit_id, cycle_id], one=True
        )
    else:
        inspection = query_db("""
            SELECT i.id FROM inspection i
            JOIN inspection_cycle ic ON i.cycle_id = ic.id
            WHERE i.unit_id = ?
            ORDER BY ic.cycle_number DESC LIMIT 1
        """, [unit_id], one=True)
    
    if inspection:
        return redirect(url_for('inspection.inspect', inspection_id=inspection['id']))
    else:
        return redirect(url_for('inspection.start_inspection', unit_id=unit_id))


@certification_bp.route('/unit/<unit_id>/review', methods=['POST'])
@require_team_lead
def review_unit(unit_id):
    """Team Lead marks inspection as reviewed."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    # Get latest inspection for this unit
    inspection = query_db("""
        SELECT i.* FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.unit_id = ? AND i.tenant_id = ?
        ORDER BY ic.cycle_number DESC LIMIT 1
    """, [unit_id, tenant_id], one=True)
    
    if not inspection:
        flash('No inspection found for this unit', 'error')
        return redirect(url_for('certification.dashboard'))
    
    if inspection['status'] != 'submitted':
        flash(f"Cannot review: inspection is '{inspection['status']}', expected 'submitted'", 'error')
        return redirect(url_for('certification.dashboard'))
    
    db.execute("""
        UPDATE inspection 
        SET status = 'reviewed', updated_at = CURRENT_TIMESTAMP 
        WHERE id = ?
    """, [inspection['id']])
    db.commit()
    
    flash(f"Unit {query_db('SELECT unit_number FROM unit WHERE id = ?', [unit_id], one=True)['unit_number']} marked as reviewed", 'success')
    return redirect(url_for('certification.dashboard'))


@certification_bp.route('/unit/<unit_id>/approve', methods=['POST'])
@require_manager
def approve_unit(unit_id):
    """Manager approves inspection."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    # Get latest inspection for this unit
    inspection = query_db("""
        SELECT i.* FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.unit_id = ? AND i.tenant_id = ?
        ORDER BY ic.cycle_number DESC LIMIT 1
    """, [unit_id, tenant_id], one=True)
    
    if not inspection:
        flash('No inspection found for this unit', 'error')
        return redirect(url_for('certification.dashboard'))
    
    # Manager can approve from submitted OR reviewed
    if inspection['status'] not in ('submitted', 'reviewed'):
        flash(f"Cannot approve: inspection is '{inspection['status']}'", 'error')
        return redirect(url_for('certification.dashboard'))
    
    db.execute("""
        UPDATE inspection 
        SET status = 'approved', updated_at = CURRENT_TIMESTAMP 
        WHERE id = ?
    """, [inspection['id']])
    db.commit()
    
    flash(f"Unit {query_db('SELECT unit_number FROM unit WHERE id = ?', [unit_id], one=True)['unit_number']} approved", 'success')
    return redirect(url_for('certification.dashboard'))


@certification_bp.route('/unit/<unit_id>/certify', methods=['POST'])
@require_manager
def certify_unit(unit_id):
    """Manager certifies unit (final sign-off, 0 defects)."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    unit = query_db(
        "SELECT * FROM unit WHERE id = ? AND tenant_id = ?",
        [unit_id, tenant_id], one=True
    )
    
    if not unit:
        abort(404)
    
    # Check no open defects
    open_defects = query_db(
        "SELECT COUNT(*) as count FROM defect WHERE unit_id = ? AND status = 'open'",
        [unit_id], one=True
    )['count']
    
    if open_defects > 0:
        flash(f'Cannot certify: {open_defects} open defects remain', 'error')
        return redirect(url_for('certification.dashboard'))
    
    # Update unit status to certified
    db.execute("UPDATE unit SET status = 'certified' WHERE id = ?", [unit_id])
    
    # Also close the inspection
    inspection = query_db("""
        SELECT i.id FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.unit_id = ? ORDER BY ic.cycle_number DESC LIMIT 1
    """, [unit_id], one=True)
    
    if inspection:
        db.execute("""
            UPDATE inspection 
            SET status = 'closed', updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, [inspection['id']])
    
    db.commit()
    
    flash(f"Unit {unit['unit_number']} certified", 'success')
    return redirect(url_for('certification.dashboard'))


@certification_bp.route('/unit/<unit_id>/reopen', methods=['POST'])
@require_manager
def reopen_unit(unit_id):
    """Manager reopens a certified unit."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    unit = query_db(
        "SELECT * FROM unit WHERE id = ? AND tenant_id = ?",
        [unit_id, tenant_id], one=True
    )
    
    if not unit:
        abort(404)
    
    if unit['status'] != 'certified':
        flash('Only certified units can be reopened', 'error')
        return redirect(url_for('certification.dashboard'))
    
    db.execute("UPDATE unit SET status = 'in_progress' WHERE id = ?", [unit_id])
    
    # Reopen the inspection too
    inspection = query_db("""
        SELECT i.id FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.unit_id = ? ORDER BY ic.cycle_number DESC LIMIT 1
    """, [unit_id], one=True)
    
    if inspection:
        db.execute("""
            UPDATE inspection 
            SET status = 'approved', updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, [inspection['id']])
    
    db.commit()
    
    flash(f"Unit {unit['unit_number']} reopened", 'success')
    return redirect(url_for('certification.view_unit', unit_id=unit_id))


@certification_bp.route('/unit/<unit_id>/defect/<defect_id>/update', methods=['POST'])
@require_team_lead
def update_defect(unit_id, defect_id):
    """Update defect comment or status."""
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
            SET status = 'cleared', clearance_note = ?, cleared_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, [new_comment, defect_id])
    else:
        db.execute("""
            UPDATE defect SET original_comment = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        """, [new_comment, defect_id])
    
    db.commit()
    
    open_count = query_db(
        "SELECT COUNT(*) as count FROM defect WHERE unit_id = ? AND status = 'open'",
        [unit_id], one=True
    )['count']
    
    if open_count == 0:
        db.execute("UPDATE unit SET status = 'cleared' WHERE id = ?", [unit_id])
        db.commit()
    
    return redirect(url_for('certification.view_unit', unit_id=unit_id))


@certification_bp.route('/unit/<unit_id>/category-note', methods=['POST'])
@require_team_lead
def update_category_note(unit_id):
    """Add or update a category-level note."""
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
    
    latest_cycle = query_db("""
        SELECT id FROM inspection_cycle 
        WHERE phase_id = ? AND status = 'active'
        ORDER BY cycle_number DESC LIMIT 1
    """, [unit['phase_id']], one=True)
    
    cycle_id = latest_cycle['id'] if latest_cycle else None
    
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
    
    from app.utils import generate_id
    db.execute("""
        INSERT INTO category_comment_history 
        (id, tenant_id, category_comment_id, cycle_id, comment, status, updated_by, created_at)
        VALUES (?, ?, ?, ?, ?, 'open', ?, CURRENT_TIMESTAMP)
    """, [generate_id('cch'), tenant_id, cc_id, cycle_id, note, session['user_id']])
    
    db.commit()
    
    return redirect(url_for('certification.view_unit', unit_id=unit_id))
