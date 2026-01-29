"""
Projects routes - Project, Phase, Unit navigation for students.
"""
from flask import Blueprint, render_template, abort
from app.auth import require_auth
from app.services.db import query_db

projects_bp = Blueprint('projects', __name__, url_prefix='/projects')


@projects_bp.route('/')
@require_auth
def list_projects():
    """List all projects for current tenant."""
    from flask import session
    tenant_id = session['tenant_id']
    
    projects = query_db("""
        SELECT p.*, 
            (SELECT COUNT(*) FROM phase ph WHERE ph.project_id = p.id) as phase_count,
            (SELECT GROUP_CONCAT(ph.phase_name, ', ') FROM phase ph WHERE ph.project_id = p.id) as phase_names
        FROM project p
        WHERE p.tenant_id = ?
        ORDER BY p.project_name
    """, [tenant_id])
    
    return render_template('projects/list.html', projects=projects)


@projects_bp.route('/<project_id>')
@require_auth
def view_project(project_id):
    """View project with phases."""
    from flask import session
    tenant_id = session['tenant_id']
    
    project = query_db(
        "SELECT * FROM project WHERE id = ? AND tenant_id = ?",
        [project_id, tenant_id], one=True
    )
    if not project:
        abort(404)
    
    phases = query_db("""
        SELECT ph.*,
            (SELECT COUNT(*) FROM unit u WHERE u.phase_id = ph.id) as unit_count,
            (SELECT COUNT(*) FROM unit u WHERE u.phase_id = ph.id AND u.status = 'cleared') as cleared_count,
            (SELECT COUNT(*) FROM defect d 
             JOIN unit u ON d.unit_id = u.id 
             WHERE u.phase_id = ph.id AND d.status = 'open') as open_defects
        FROM phase ph
        WHERE ph.project_id = ? AND ph.tenant_id = ?
        ORDER BY ph.phase_name
    """, [project_id, tenant_id])
    
    return render_template('projects/project.html', project=project, phases=phases)


@projects_bp.route('/phase/<phase_id>')
@require_auth
def view_phase(phase_id):
    """View phase with units - filtered by active cycles."""
    from flask import session, request
    tenant_id = session['tenant_id']
    
    phase = query_db(
        "SELECT * FROM phase WHERE id = ? AND tenant_id = ?",
        [phase_id, tenant_id], one=True
    )
    if not phase:
        abort(404)
    
    project = query_db(
        "SELECT * FROM project WHERE id = ?",
        [phase['project_id']], one=True
    )
    
    # Get active cycles for filter dropdown with stats
    active_cycles = query_db("""
        SELECT ic.*,
            (SELECT COUNT(DISTINCT i.unit_id) FROM inspection i 
             WHERE i.cycle_id = ic.id AND i.status = 'submitted') as submitted_count,
            (SELECT COUNT(*) FROM unit u 
             WHERE u.phase_id = ic.phase_id 
             AND (ic.unit_start IS NULL OR (u.unit_number >= ic.unit_start AND u.unit_number <= ic.unit_end))) as total_units
        FROM inspection_cycle ic
        WHERE ic.phase_id = ? AND ic.status = 'active'
        ORDER BY ic.cycle_number
    """, [phase_id])
    
    # Get cycle filter from query param
    cycle_filter = request.args.get('cycle')
    
    # Build units query based on active cycles
    if cycle_filter:
        # Filter to specific cycle
        cycle = query_db("SELECT * FROM inspection_cycle WHERE id = ?", [cycle_filter], one=True)
        if cycle and cycle['unit_start'] and cycle['unit_end']:
            units = query_db("""
                SELECT u.*,
                    u.unit_number,
                    ? as cycle_number,
                    ? as cycle_id,
                    (SELECT i.status FROM inspection i WHERE i.unit_id = u.id AND i.cycle_id = ?) as inspection_status,
                    (SELECT i.id FROM inspection i WHERE i.unit_id = u.id AND i.cycle_id = ?) as inspection_id,
                    (SELECT COUNT(*) FROM defect d WHERE d.unit_id = u.id AND d.status = 'open') as open_defects
                FROM unit u
                WHERE u.phase_id = ? AND u.tenant_id = ?
                AND u.unit_number >= ? AND u.unit_number <= ?
                ORDER BY u.unit_number
            """, [cycle['cycle_number'], cycle['id'], cycle['id'], cycle['id'], 
                  phase_id, tenant_id, cycle['unit_start'], cycle['unit_end']])
        else:
            # Cycle has no range - show all units
            units = query_db("""
                SELECT u.*,
                    u.unit_number,
                    ? as cycle_number,
                    ? as cycle_id,
                    (SELECT i.status FROM inspection i WHERE i.unit_id = u.id AND i.cycle_id = ?) as inspection_status,
                    (SELECT i.id FROM inspection i WHERE i.unit_id = u.id AND i.cycle_id = ?) as inspection_id,
                    (SELECT COUNT(*) FROM defect d WHERE d.unit_id = u.id AND d.status = 'open') as open_defects
                FROM unit u
                WHERE u.phase_id = ? AND u.tenant_id = ?
                ORDER BY u.unit_number
            """, [cycle['cycle_number'], cycle['id'], cycle['id'], cycle['id'], phase_id, tenant_id])
    elif active_cycles:
        # No filter - show all units in any active cycle with their cycle info
        # Build a union of units across all active cycles
        units = query_db("""
            SELECT DISTINCT u.*,
                u.unit_number,
                (SELECT ic.cycle_number FROM inspection_cycle ic 
                 WHERE ic.phase_id = u.phase_id AND ic.status = 'active'
                 AND (ic.unit_start IS NULL OR (u.unit_number >= ic.unit_start AND u.unit_number <= ic.unit_end))
                 ORDER BY ic.cycle_number DESC LIMIT 1) as cycle_number,
                (SELECT ic.id FROM inspection_cycle ic 
                 WHERE ic.phase_id = u.phase_id AND ic.status = 'active'
                 AND (ic.unit_start IS NULL OR (u.unit_number >= ic.unit_start AND u.unit_number <= ic.unit_end))
                 ORDER BY ic.cycle_number DESC LIMIT 1) as cycle_id,
                (SELECT i.status FROM inspection i 
                 JOIN inspection_cycle ic ON i.cycle_id = ic.id
                 WHERE i.unit_id = u.id AND ic.status = 'active'
                 ORDER BY ic.cycle_number DESC LIMIT 1) as inspection_status,
                (SELECT i.id FROM inspection i 
                 JOIN inspection_cycle ic ON i.cycle_id = ic.id
                 WHERE i.unit_id = u.id AND ic.status = 'active'
                 ORDER BY ic.cycle_number DESC LIMIT 1) as inspection_id,
                (SELECT COUNT(*) FROM defect d WHERE d.unit_id = u.id AND d.status = 'open') as open_defects
            FROM unit u
            WHERE u.phase_id = ? AND u.tenant_id = ?
            AND EXISTS (
                SELECT 1 FROM inspection_cycle ic 
                WHERE ic.phase_id = u.phase_id AND ic.status = 'active'
                AND (ic.unit_start IS NULL OR (u.unit_number >= ic.unit_start AND u.unit_number <= ic.unit_end))
            )
            ORDER BY u.unit_number
        """, [phase_id, tenant_id])
    else:
        # No active cycles - show all units
        units = query_db("""
            SELECT u.*,
                u.unit_number,
                NULL as cycle_number,
                NULL as cycle_id,
                NULL as inspection_status,
                NULL as inspection_id,
                (SELECT COUNT(*) FROM defect d WHERE d.unit_id = u.id AND d.status = 'open') as open_defects
            FROM unit u
            WHERE u.phase_id = ? AND u.tenant_id = ?
            ORDER BY u.unit_number
        """, [phase_id, tenant_id])
    
    # Stats
    stats = {
        'total': len(units),
        'certified': sum(1 for u in units if u['status'] == 'certified'),
        'cleared': sum(1 for u in units if u['status'] == 'cleared'),
        'open_defects': sum(u['open_defects'] or 0 for u in units)
    }
    
    return render_template('projects/phase.html', project=project, phase=phase, units=units, 
                          active_cycles=active_cycles, cycle_filter=cycle_filter, stats=stats)


@projects_bp.route('/unit/<unit_id>')
@require_auth
def view_unit(unit_id):
    """View unit details and inspection history."""
    from flask import session
    tenant_id = session['tenant_id']
    
    unit = query_db("""
        SELECT u.*, 
            u.unit_number as unit_code,
            ph.phase_name, p.project_name
        FROM unit u
        JOIN phase ph ON u.phase_id = ph.id
        JOIN project p ON ph.project_id = p.id
        WHERE u.id = ? AND u.tenant_id = ?
    """, [unit_id, tenant_id], one=True)
    
    if not unit:
        abort(404)
    
    inspections = query_db("""
        SELECT i.*, ic.cycle_number,
            (SELECT COUNT(*) FROM defect d WHERE d.raised_cycle_id = i.cycle_id AND d.unit_id = i.unit_id) as defects_raised,
            (SELECT COUNT(*) FROM defect d WHERE d.cleared_cycle_id = i.cycle_id AND d.unit_id = i.unit_id) as defects_cleared
        FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.unit_id = ?
        ORDER BY ic.cycle_number DESC
    """, [unit_id])
    
    # Get active cycles for this phase that include this unit
    active_cycles = query_db("""
        SELECT ic.*, 
            (SELECT COUNT(*) FROM cycle_excluded_item cei WHERE cei.cycle_id = ic.id) as excluded_count,
            (SELECT i.id FROM inspection i WHERE i.unit_id = ? AND i.cycle_id = ic.id) as has_inspection
        FROM inspection_cycle ic
        WHERE ic.phase_id = ? AND ic.status = 'active'
        AND (ic.unit_start IS NULL OR (? >= ic.unit_start AND ? <= ic.unit_end))
        ORDER BY ic.cycle_number DESC
    """, [unit_id, unit['phase_id'], unit['unit_code'], unit['unit_code']])
    
    open_defects = query_db("""
        SELECT d.*, it.item_description, ct.category_name, at.area_name
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        WHERE d.unit_id = ? AND d.status = 'open'
        ORDER BY at.area_order, ct.category_order, it.item_order
    """, [unit_id])
    
    return render_template('projects/unit.html', unit=unit, inspections=inspections, 
                          open_defects=open_defects, active_cycles=active_cycles)
