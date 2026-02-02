"""
Defects routes - Defects register views.
Project-level view of all defects across units.
"""
from datetime import date
from collections import OrderedDict
from flask import Blueprint, render_template, session, request, abort
from app.auth import require_team_lead
from app.services.db import query_db

defects_bp = Blueprint('defects', __name__, url_prefix='/defects')


@defects_bp.route('/')
@require_team_lead
def register():
    """Defects register - filterable list of all defects."""
    tenant_id = session['tenant_id']
    
    # Get filter parameters
    project_id = request.args.get('project')
    phase_id = request.args.get('phase')
    status_filter = request.args.get('status', 'open')
    block_filter = request.args.get('block')
    
    # Build query
    query = """
        SELECT d.*, 
               u.unit_number as unit_code,
               u.block, u.floor, u.unit_number,
               it.item_description, ct.category_name, at.area_name,
               i.inspection_date, i.inspector_name,
               p.project_name, ph.phase_name,
               ic.cycle_number as raised_cycle,
               parent.item_description as parent_description,
               dh.comment as defect_comment
        FROM defect d
        JOIN unit u ON d.unit_id = u.id
        JOIN phase ph ON u.phase_id = ph.id
        JOIN project p ON ph.project_id = p.id
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id
        LEFT JOIN inspection i ON d.unit_id = i.unit_id AND d.raised_cycle_id = i.cycle_id
        LEFT JOIN item_template parent ON it.parent_item_id = parent.id
        LEFT JOIN (
            SELECT defect_id, comment FROM defect_history 
            WHERE id IN (SELECT MIN(id) FROM defect_history GROUP BY defect_id)
        ) dh ON dh.defect_id = d.id
        WHERE d.tenant_id = ?
    """
    params = [tenant_id]
    
    if project_id:
        query += " AND p.id = ?"
        params.append(project_id)
    
    if phase_id:
        query += " AND ph.id = ?"
        params.append(phase_id)
    
    if status_filter and status_filter != 'all':
        query += " AND d.status = ?"
        params.append(status_filter)
    
    if block_filter:
        query += " AND u.block = ?"
        params.append(block_filter)
    
    query += " ORDER BY u.unit_number, at.area_order, ct.category_order, it.item_order"
    
    defects = query_db(query, params)
    
    # Get category comments for all units with defects
    unit_ids = list(set(d['unit_id'] for d in defects))
    category_comments = {}
    if unit_ids:
        placeholders = ','.join('?' * len(unit_ids))
        comments = query_db(f"""
            SELECT cc.unit_id, cc.category_template_id, cch.comment as latest_comment,
                   ct.category_name, at.area_name
            FROM category_comment cc
            LEFT JOIN category_comment_history cch ON cch.category_comment_id = cc.id
            JOIN category_template ct ON cc.category_template_id = ct.id
            JOIN area_template at ON ct.area_id = at.id
            WHERE cc.unit_id IN ({placeholders})
            ORDER BY cch.created_at DESC
        """, unit_ids)
        for c in comments:
            key = (c['unit_id'], c['area_name'], c['category_name'])
            if key not in category_comments:
                category_comments[key] = c['latest_comment']
    
    # Group defects by unit -> area -> category
    grouped_defects = OrderedDict()
    for d in defects:
        unit_key = d['unit_code']
        area_name = d['area_name']
        cat_name = d['category_name']
        
        if unit_key not in grouped_defects:
            grouped_defects[unit_key] = {
                'unit_code': d['unit_code'],
                'unit_id': d['unit_id'],
                'raised_cycle': d['raised_cycle'],
                'areas': OrderedDict()
            }
        
        if area_name not in grouped_defects[unit_key]['areas']:
            grouped_defects[unit_key]['areas'][area_name] = {
                'name': area_name,
                'categories': OrderedDict()
            }
        
        if cat_name not in grouped_defects[unit_key]['areas'][area_name]['categories']:
            cat_note_key = (d['unit_id'], area_name, cat_name)
            grouped_defects[unit_key]['areas'][area_name]['categories'][cat_name] = {
                'name': cat_name,
                'note': category_comments.get(cat_note_key),
                'defects': []
            }
        
        grouped_defects[unit_key]['areas'][area_name]['categories'][cat_name]['defects'].append(d)
    
    # Count total defects per unit
    for unit_key, unit_data in grouped_defects.items():
        total = 0
        for area in unit_data['areas'].values():
            for cat in area['categories'].values():
                total += len(cat['defects'])
        unit_data['defect_count'] = total
    
    # Summary stats
    stats = query_db("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN d.status = 'open' THEN 1 ELSE 0 END) as open_count,
            SUM(CASE WHEN d.status = 'cleared' THEN 1 ELSE 0 END) as cleared_count,
            COUNT(DISTINCT d.unit_id) as units_with_defects
        FROM defect d
        WHERE d.tenant_id = ?
    """, [tenant_id], one=True)
    
    # Filter options
    projects = query_db(
        "SELECT * FROM project WHERE tenant_id = ? ORDER BY project_name",
        [tenant_id]
    )
    
    phases = []
    blocks = []
    if project_id:
        phases = query_db(
            "SELECT * FROM phase WHERE project_id = ? ORDER BY phase_name",
            [project_id]
        )
    
    if phase_id:
        blocks = query_db(
            "SELECT DISTINCT block FROM unit WHERE phase_id = ? ORDER BY block",
            [phase_id]
        )
    
    return render_template('defects/register.html',
                          grouped_defects=grouped_defects, stats=stats,
                          projects=projects, phases=phases, blocks=blocks,
                          filters={
                              'project': project_id,
                              'phase': phase_id,
                              'status': status_filter,
                              'block': block_filter
                          })


@defects_bp.route('/phase/<phase_id>')
@require_team_lead
def phase_register(phase_id):
    """Phase-level defects register with grouping by unit."""
    tenant_id = session['tenant_id']
    
    status_filter = request.args.get('status', 'open')
    block_filter = request.args.get('block')
    
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
    
    # Build query with filters
    query = """
        SELECT d.*, d.status as defect_status,
               u.unit_number as unit_code,
               u.block, u.floor, u.unit_number,
               it.item_description, ct.category_name, at.area_name,
               i.inspection_date, i.inspector_name,
               parent.item_description as parent_description,
               ic.cycle_number as raised_cycle,
               dh.comment as defect_comment
        FROM defect d
        JOIN unit u ON d.unit_id = u.id
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id
        LEFT JOIN inspection i ON d.unit_id = i.unit_id AND d.raised_cycle_id = i.cycle_id
        LEFT JOIN item_template parent ON it.parent_item_id = parent.id
        LEFT JOIN (
            SELECT defect_id, comment FROM defect_history 
            WHERE id IN (SELECT MIN(id) FROM defect_history GROUP BY defect_id)
        ) dh ON dh.defect_id = d.id
        WHERE u.phase_id = ?
    """
    params = [phase_id]
    
    if status_filter and status_filter != 'all':
        query += " AND d.status = ?"
        params.append(status_filter)
    
    if block_filter:
        query += " AND u.block = ?"
        params.append(block_filter)
    
    query += " ORDER BY u.block, u.floor, u.unit_number, at.area_order, ct.category_order"
    
    defects = query_db(query, params)
    
    # Group by unit
    grouped_defects = OrderedDict()
    for d in defects:
        unit_code = d['unit_code']
        if unit_code not in grouped_defects:
            grouped_defects[unit_code] = {'defects': []}
        grouped_defects[unit_code]['defects'].append(d)
    
    # Stats
    stats = query_db("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN d.status = 'open' THEN 1 ELSE 0 END) as open_count,
            SUM(CASE WHEN d.status = 'cleared' THEN 1 ELSE 0 END) as cleared_count,
            COUNT(DISTINCT d.unit_id) as units_with_defects
        FROM defect d
        JOIN unit u ON d.unit_id = u.id
        WHERE u.phase_id = ?
    """, [phase_id], one=True)
    
    # Block filter options
    blocks = query_db(
        "SELECT DISTINCT block FROM unit WHERE phase_id = ? ORDER BY block",
        [phase_id]
    )
    
    return render_template('defects/register.html',
                          project=project, phase=phase,
                          grouped_defects=grouped_defects, stats=stats,
                          blocks=blocks,
                          today=date.today().strftime('%d %B %Y'),
                          filters={
                              'status': status_filter,
                              'block': block_filter
                          })
