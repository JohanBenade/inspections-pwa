"""
Inspection routes - Main inspection workflow.
Inspections are conducted within a cycle created by the architect.
"""
from datetime import date
from flask import Blueprint, render_template, session, redirect, url_for, abort, request
from app.auth import require_auth
from app.utils import generate_id
from app.services.db import get_db, query_db
from app.services.template_loader import get_inspection_template

inspection_bp = Blueprint('inspection', __name__, url_prefix='/inspection')


@inspection_bp.route('/start/<unit_id>')
@require_auth
def start_inspection(unit_id):
    tenant_id = session['tenant_id']
    db = get_db()
    cycle_id = request.args.get('cycle_id')
    
    if not cycle_id:
        cycle = query_db("""
            SELECT ic.* FROM inspection_cycle ic
            JOIN unit u ON ic.phase_id = u.phase_id
            WHERE u.id = ? AND ic.status = 'active'
            ORDER BY ic.cycle_number DESC LIMIT 1
        """, [unit_id], one=True)
        if not cycle:
            abort(400, "No active inspection cycle")
        cycle_id = cycle['id']
    
    cycle = query_db(
        "SELECT * FROM inspection_cycle WHERE id = ? AND tenant_id = ? AND status = 'active'",
        [cycle_id, tenant_id], one=True
    )
    if not cycle:
        abort(400, "Cycle not active or not found")
    
    unit = query_db("""
        SELECT u.*, ph.phase_name, p.project_name
        FROM unit u
        JOIN phase ph ON u.phase_id = ph.id
        JOIN project p ON ph.project_id = p.id
        WHERE u.id = ? AND u.tenant_id = ?
    """, [unit_id, tenant_id], one=True)
    
    if not unit:
        abort(404)
    
    existing = query_db(
        "SELECT * FROM inspection WHERE unit_id = ? AND cycle_id = ?",
        [unit_id, cycle_id], one=True
    )
    
    if existing:
        return redirect(url_for('inspection.inspect', inspection_id=existing['id']))
    
    inspection_id = generate_id()
    db.execute("""
        INSERT INTO inspection (id, tenant_id, unit_id, cycle_id,
                               inspection_date, inspector_id, inspector_name, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'in_progress')
    """, [inspection_id, tenant_id, unit_id, cycle_id,
          date.today().isoformat(), session['user_id'], session['user_name']])
    
    excluded_items = query_db(
        "SELECT item_template_id FROM cycle_excluded_item WHERE cycle_id = ?",
        [cycle_id]
    )
    excluded_ids = set(e['item_template_id'] for e in excluded_items)
    
    previous_statuses = {}
    if cycle['cycle_number'] > 1:
        prev_inspection = query_db("""
            SELECT ii.item_template_id, ii.status, ii.comment
            FROM inspection_item ii
            JOIN inspection i ON ii.inspection_id = i.id
            JOIN inspection_cycle ic ON i.cycle_id = ic.id
            WHERE i.unit_id = ? AND ic.cycle_number = ?
        """, [unit_id, cycle['cycle_number'] - 1])
        previous_statuses = {p['item_template_id']: {'status': p['status'], 'comment': p['comment']} for p in prev_inspection}
    
    items = query_db("""
        SELECT it.id
        FROM item_template it
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        WHERE at.tenant_id = ? AND at.unit_type = ?
    """, [tenant_id, unit['unit_type']])
    
    for item in items:
        item_id = generate_id()
        
        if item['id'] in excluded_ids:
            status = 'skipped'
            comment = None
        elif item['id'] in previous_statuses:
            prev = previous_statuses[item['id']]
            if prev['status'] == 'skipped':
                status = 'pending'
                comment = None
            else:
                status = prev['status']
                comment = prev['comment']
        else:
            status = 'pending'
            comment = None
        
        db.execute("""
            INSERT INTO inspection_item (id, tenant_id, inspection_id, item_template_id, status, comment)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [item_id, tenant_id, inspection_id, item['id'], status, comment])
    
    db.execute("UPDATE unit SET status = 'in_progress' WHERE id = ?", [unit_id])
    db.commit()
    
    return redirect(url_for('inspection.inspect', inspection_id=inspection_id))


@inspection_bp.route('/<inspection_id>')
@require_auth
def inspect(inspection_id):
    tenant_id = session['tenant_id']
    
    inspection = query_db("""
        SELECT i.*, u.unit_type, u.unit_number,
               ph.phase_name, p.project_name,
               ic.cycle_number, ic.general_notes as cycle_notes
        FROM inspection i
        JOIN unit u ON i.unit_id = u.id
        JOIN phase ph ON u.phase_id = ph.id
        JOIN project p ON ph.project_id = p.id
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.id = ? AND i.tenant_id = ?
    """, [inspection_id, tenant_id], one=True)
    
    if not inspection:
        abort(404)
    
    is_initial = inspection['cycle_number'] == 1
    template = get_inspection_template(tenant_id, inspection['unit_type'])
    
    progress_raw = query_db("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN ii.status NOT IN ('pending', 'skipped') THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN ii.status = 'skipped' THEN 1 ELSE 0 END) as skipped
        FROM inspection_item ii
        JOIN item_template it ON ii.item_template_id = it.id
        WHERE ii.inspection_id = ?
        
    """, [inspection_id], one=True)
    
    defect_count = query_db("""
        SELECT COUNT(*) as defects
        FROM inspection_item ii
        WHERE ii.inspection_id = ?
        AND ii.status IN ('not_to_standard', 'not_installed')
    """, [inspection_id], one=True)
    
    progress = {
        'total': progress_raw['total'] or 0,
        'completed': progress_raw['completed'] or 0,
        'defects': defect_count['defects'] or 0,
        'skipped': progress_raw['skipped'] or 0,
    }
    progress['active'] = progress['total'] - progress['skipped']
    
    open_defects = []
    if not is_initial:
        ok_items = query_db("""
            SELECT item_template_id FROM inspection_item
            WHERE inspection_id = ? AND status = 'ok'
        """, [inspection_id])
        ok_template_ids = set(item['item_template_id'] for item in ok_items)
        
        all_open_defects = query_db("""
            SELECT d.*, it.item_description, ct.category_name, at.area_name,
                   ic.cycle_number as raised_cycle, d.item_template_id
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at ON ct.area_id = at.id
            JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id
            WHERE d.unit_id = ? AND d.status = 'open'
            ORDER BY at.area_order, ct.category_order, it.item_order
        """, [inspection['unit_id']])
        
        open_defects = [d for d in all_open_defects if d['item_template_id'] not in ok_template_ids]
    
    category_comments = query_db("""
        SELECT cc.*, ct.category_name, at.area_name
        FROM category_comment cc
        JOIN category_template ct ON cc.category_template_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        WHERE cc.unit_id = ? AND cc.status = 'open'
    """, [inspection['unit_id']])
    
    area_defects = query_db("""
        SELECT at.id as area_id, COUNT(*) as defect_count
        FROM inspection_item ii
        JOIN item_template it ON ii.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        WHERE ii.inspection_id = ?
        AND ii.status IN ('not_to_standard', 'not_installed')
        GROUP BY at.id
    """, [inspection_id])
    area_defect_map = {d['area_id']: d['defect_count'] for d in area_defects}
    
    area_notes = query_db("""
        SELECT area_template_id, note FROM cycle_area_note
        WHERE cycle_id = (SELECT cycle_id FROM inspection WHERE id = ?)
    """, [inspection_id])
    area_notes_map = {n['area_template_id']: n['note'] for n in area_notes}
    
    pdf_available = query_db(
        "SELECT COUNT(*) as count FROM defect WHERE unit_id = ?",
        [inspection['unit_id']], one=True
    )['count'] > 0
    
    current_user = {'role': session.get('role', 'inspector')}
    
    return render_template('inspection/inspect.html',
                         inspection=inspection,
                         template=template,
                         progress=progress,
                         is_initial=is_initial,
                         open_defects=open_defects,
                         category_comments=category_comments,
                         area_defect_map=area_defect_map,
                         area_notes_map=area_notes_map,
                         pdf_available=pdf_available,
                         current_user=current_user)


@inspection_bp.route('/<inspection_id>/area/<area_id>')
@require_auth
def inspect_area(inspection_id, area_id):
    tenant_id = session['tenant_id']
    filter_mode = request.args.get('filter', 'all')
    
    inspection = query_db("""
        SELECT i.*, u.unit_type, u.unit_number, ic.cycle_number, ic.id as cycle_id
        FROM inspection i
        JOIN unit u ON i.unit_id = u.id
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.id = ? AND i.tenant_id = ?
    """, [inspection_id, tenant_id], one=True)
    
    if not inspection:
        abort(404)
    
    is_initial = inspection['cycle_number'] == 1
    is_followup = not is_initial
    
    # Show filter for all users
    user_role = session.get('role', 'inspector')
    show_filter = True  # Show filter for all users
    
    area = query_db(
        "SELECT * FROM area_template WHERE id = ? AND tenant_id = ?",
        [area_id, tenant_id], one=True
    )
    
    if not area:
        abort(404)
    
    # Get open defects for this unit
    open_defects_map = {}
    if is_followup:
        open_defects = query_db("""
            SELECT d.item_template_id, d.original_comment, ic.cycle_number as raised_cycle
            FROM defect d
            JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id
            WHERE d.unit_id = ? AND d.status = 'open'
        """, [inspection['unit_id']])
        open_defects_map = {d['item_template_id']: d for d in open_defects}
    
    # Get category comments
    cat_comments = query_db("""
        SELECT cc.category_template_id, cc.id as comment_id,
               (SELECT comment FROM category_comment_history 
                WHERE category_comment_id = cc.id 
                ORDER BY created_at DESC LIMIT 1) as latest_comment
        FROM category_comment cc
        WHERE cc.unit_id = ?
    """, [inspection['unit_id']])
    cat_comment_map = {c['category_template_id']: c for c in cat_comments}
    
    categories = query_db("""
        SELECT ct.*
        FROM category_template ct
        WHERE ct.area_id = ?
        ORDER BY ct.category_order
    """, [area_id])
    
    category_data = []
    for cat in categories:
        # Get all items for this category
        items_raw = query_db("""
            SELECT it.id as template_id, it.item_description, it.parent_item_id, it.item_order,
                   ii.id, ii.status, ii.comment,
                   (SELECT COUNT(*) FROM item_template WHERE parent_item_id = it.id) as child_count
            FROM item_template it
            JOIN inspection_item ii ON it.id = ii.item_template_id
            WHERE it.category_id = ? AND ii.inspection_id = ?
            ORDER BY it.item_order
        """, [cat['id'], inspection_id])
        
        # Build parent status map
        parent_status_map = {}
        parent_items = {}
        for i in items_raw:
            if i['parent_item_id'] is None:
                parent_status_map[i['template_id']] = i['status']
                parent_items[i['template_id']] = i
        
        # First pass: identify which items have defects
        defective_template_ids = set()
        parent_has_defective_child = set()
        
        for item in items_raw:
            is_defective = item['status'] in ['not_to_standard', 'not_installed']
            has_open_defect = item['template_id'] in open_defects_map
            
            if is_defective or has_open_defect:
                defective_template_ids.add(item['template_id'])
                if item['parent_item_id']:
                    parent_has_defective_child.add(item['parent_item_id'])
        
        # Check if category has any defects
        category_has_defects = len(defective_template_ids) > 0
        
        # Build checklist with filter logic
        checklist = []
        all_skipped = True
        
        for item in items_raw:
            has_open_defect = item['template_id'] in open_defects_map
            defect_info = open_defects_map.get(item['template_id'])
            is_defective = item['status'] in ['not_to_standard', 'not_installed']
            
            is_parent = item['parent_item_id'] is None
            is_child = not is_parent
            
            # Filter logic: show item if...
            if filter_mode == 'defects':
                # Always skip if no defects in category
                if not category_has_defects:
                    continue
                
                # Show parent if it has defective children OR is itself defective
                if is_parent:
                    if item['template_id'] not in parent_has_defective_child and not is_defective and not has_open_defect:
                        continue
                # Show child only if it's defective
                else:
                    if not is_defective and not has_open_defect:
                        continue
            
            if filter_mode == 'excluded':
                # Only show skipped/excluded items
                if item['status'] != 'skipped':
                    continue
            
            parent_status = None
            if is_child:
                parent_status = parent_status_map.get(item['parent_item_id'])
            
            if item['status'] != 'skipped':
                all_skipped = False
            
            checklist.append({
                'id': item['id'],
                'template_id': item['template_id'],
                'item_description': item['item_description'],
                'status': item['status'],
                'comment': item['comment'],
                'parent_item_id': item['parent_item_id'],
                'depth': 0 if is_parent else 1,
                'child_count': item['child_count'],
                'parent_status': parent_status,
                'has_open_defect': has_open_defect,
                'defect_cycle': defect_info['raised_cycle'] if defect_info else None,
                'defect_comment': defect_info['original_comment'] if defect_info else None,
            })
        
        # Skip empty categories in defects filter mode
        if filter_mode == 'defects' and not checklist:
            continue
        
        cat_comment = cat_comment_map.get(cat['id'])
        
        category_data.append({
            'id': cat['id'],
            'name': cat['category_name'],
            'checklist': checklist,
            'all_skipped': all_skipped and len(checklist) > 0,
            'comment': cat_comment,
        })
    
    area_note = query_db("""
        SELECT note FROM cycle_area_note
        WHERE cycle_id = ? AND area_template_id = ?
    """, [inspection['cycle_id'], area_id], one=True)
    
    return render_template('inspection/area.html',
                         inspection=inspection,
                         area=area,
                         categories=category_data,
                         is_initial=is_initial,
                         is_followup=is_followup,
                         show_filter=show_filter,
                         filter_mode=filter_mode,
                         area_note=area_note)


@inspection_bp.route('/<inspection_id>/item/<item_id>', methods=['POST'])
@require_auth
def update_item(inspection_id, item_id):
    tenant_id = session['tenant_id']
    db = get_db()
    
    status = request.form.get('status')
    comment = request.form.get('comment', '').strip() or None
    area_id = request.form.get('area_id')
    
    inspection = query_db(
        "SELECT * FROM inspection WHERE id = ? AND tenant_id = ?",
        [inspection_id, tenant_id], one=True
    )
    
    if not inspection:
        abort(404)
    
    item = query_db("""
        SELECT ii.*, it.parent_item_id, it.category_id
        FROM inspection_item ii
        JOIN item_template it ON ii.item_template_id = it.id
        WHERE ii.id = ? AND ii.inspection_id = ?
    """, [item_id, inspection_id], one=True)
    
    if not item:
        abort(404)
    
    db.execute(
        "UPDATE inspection_item SET status = ?, comment = ? WHERE id = ?",
        [status, comment, item_id]
    )
    
    if item['parent_item_id'] is None and status in ('ok', 'skipped'):
        db.execute("""
            UPDATE inspection_item 
            SET status = ?, comment = NULL
            WHERE inspection_id = ? 
            AND item_template_id IN (
                SELECT id FROM item_template WHERE parent_item_id = ?
            )
        """, [status, inspection_id, item['item_template_id']])
    
    db.commit()
    
    if area_id:
        return redirect(url_for('inspection.inspect_area', inspection_id=inspection_id, area_id=area_id))
    
    from flask import Response
    response = Response('')
    response.headers['HX-Trigger'] = 'areaUpdated'
    return response


@inspection_bp.route('/<inspection_id>/category/<category_id>/comment', methods=['POST'])
@require_auth
def update_category_comment(inspection_id, category_id):
    tenant_id = session['tenant_id']
    db = get_db()
    
    comment = request.form.get('comment', '').strip()
    area_id = request.form.get('area_id')
    
    inspection = query_db("""
        SELECT i.*, ic.cycle_number
        FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.id = ? AND i.tenant_id = ?
    """, [inspection_id, tenant_id], one=True)
    
    if not inspection:
        abort(404)
    
    if comment:
        existing = query_db("""
            SELECT * FROM category_comment
            WHERE unit_id = ? AND category_template_id = ?
        """, [inspection['unit_id'], category_id], one=True)
        
        if existing:
            history_id = generate_id()
            db.execute("""
                INSERT INTO category_comment_history 
                (id, tenant_id, category_comment_id, cycle_id, comment, status)
                VALUES (?, ?, ?, ?, ?, 'open')
            """, [history_id, tenant_id, existing['id'], inspection['cycle_id'], comment])
        else:
            cc_id = generate_id()
            db.execute("""
                INSERT INTO category_comment 
                (id, tenant_id, unit_id, category_template_id, raised_cycle_id, status)
                VALUES (?, ?, ?, ?, ?, 'open')
            """, [cc_id, tenant_id, inspection['unit_id'], category_id, inspection['cycle_id']])
            
            history_id = generate_id()
            db.execute("""
                INSERT INTO category_comment_history 
                (id, tenant_id, category_comment_id, cycle_id, comment, status)
                VALUES (?, ?, ?, ?, ?, 'open')
            """, [history_id, tenant_id, cc_id, inspection['cycle_id'], comment])
        
        db.commit()
    
    if area_id:
        return redirect(url_for('inspection.inspect_area', inspection_id=inspection_id, area_id=area_id))
    
    return '<div class="text-green-600 text-sm">Saved</div>'


@inspection_bp.route('/<inspection_id>/submit', methods=['POST'])
@require_auth
def submit_inspection(inspection_id):
    tenant_id = session['tenant_id']
    db = get_db()
    
    inspection = query_db("""
        SELECT i.*, ic.cycle_number
        FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.id = ? AND i.tenant_id = ?
    """, [inspection_id, tenant_id], one=True)
    
    if not inspection:
        abort(404)
    
    is_initial = inspection['cycle_number'] == 1
    
    if is_initial:
        pending = query_db("""
            SELECT COUNT(*) as count 
            FROM inspection_item ii
            JOIN item_template it ON ii.item_template_id = it.id
            WHERE ii.inspection_id = ? 
            AND ii.status = 'pending'
            
        """, [inspection_id], one=True)
        
        if pending['count'] > 0:
            from flask import flash
            flash(f"{pending['count']} items not yet inspected", 'error')
            return redirect(url_for('inspection.inspect', inspection_id=inspection_id))
        
        missing_comments = query_db("""
            SELECT it.item_description
            FROM inspection_item ii
            JOIN item_template it ON ii.item_template_id = it.id
            WHERE ii.inspection_id = ?
            AND ii.status IN ('not_to_standard', 'not_installed')
            AND (ii.comment IS NULL OR ii.comment = '')
        """, [inspection_id])
        
        if missing_comments:
            from flask import flash
            for item in missing_comments:
                flash(f"Missing comment: {item['item_description']}", 'error')
            return redirect(url_for('inspection.inspect', inspection_id=inspection_id))
    
    defect_items = query_db("""
        SELECT ii.*, it.id as template_id
        FROM inspection_item ii
        JOIN item_template it ON ii.item_template_id = it.id
        WHERE ii.inspection_id = ?
        AND ii.status IN ('not_to_standard', 'not_installed')
    """, [inspection_id])
    
    for item in defect_items:
        existing = query_db("""
            SELECT * FROM defect 
            WHERE unit_id = ? AND item_template_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, [inspection['unit_id'], item['template_id']], one=True)
        
        if existing:
            if existing['status'] == 'cleared':
                db.execute("""
                    UPDATE defect 
                    SET status = 'open', 
                        cleared_cycle_id = NULL, 
                        cleared_at = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, [existing['id']])
            
            history_id = generate_id()
            db.execute("""
                INSERT INTO defect_history (id, tenant_id, defect_id, cycle_id, comment, status)
                VALUES (?, ?, ?, ?, ?, 'open')
            """, [history_id, tenant_id, existing['id'], inspection['cycle_id'], 
                  item['comment'] or 'Not rectified'])
        else:
            defect_id = generate_id()
            db.execute("""
                INSERT INTO defect (id, tenant_id, unit_id, item_template_id,
                                   raised_cycle_id, defect_type, status, original_comment)
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?)
            """, [defect_id, tenant_id, inspection['unit_id'], item['template_id'],
                  inspection['cycle_id'], item['status'], item['comment']])
            
            history_id = generate_id()
            db.execute("""
                INSERT INTO defect_history (id, tenant_id, defect_id, cycle_id, comment, status)
                VALUES (?, ?, ?, ?, ?, 'open')
            """, [history_id, tenant_id, defect_id, inspection['cycle_id'], item['comment']])
    
    ok_items = query_db("""
        SELECT ii.item_template_id
        FROM inspection_item ii
        WHERE ii.inspection_id = ? AND ii.status = 'ok'
    """, [inspection_id])
    
    for item in ok_items:
        defect = query_db("""
            SELECT * FROM defect
            WHERE unit_id = ? AND item_template_id = ? AND status = 'open'
        """, [inspection['unit_id'], item['item_template_id']], one=True)
        
        if defect:
            db.execute("""
                UPDATE defect
                SET status = 'cleared', cleared_cycle_id = ?, cleared_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, [inspection['cycle_id'], defect['id']])
            
            history_id = generate_id()
            db.execute("""
                INSERT INTO defect_history (id, tenant_id, defect_id, cycle_id, comment, status)
                VALUES (?, ?, ?, ?, ?, 'cleared')
            """, [history_id, tenant_id, defect['id'], inspection['cycle_id'], 'Rectified'])
    
    db.execute("""
        UPDATE inspection 
        SET status = 'submitted', submitted_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, [inspection_id])
    
    open_defects = query_db(
        "SELECT COUNT(*) as count FROM defect WHERE unit_id = ? AND status = 'open'",
        [inspection['unit_id']], one=True
    )
    
    # Unit stays in_progress after submit - manager sets certified/pending_followup via Approvals
    # No unit status change needed here
    
    db.commit()
    
    role = session.get('role', 'inspector')
    if role in ('manager', 'admin'):
        return redirect(url_for('certification.dashboard'))
    else:
        return redirect(url_for('projects.view_unit', unit_id=inspection['unit_id']))


@inspection_bp.route('/<inspection_id>/progress')
@require_auth
def get_progress(inspection_id):
    inspection = query_db(
        "SELECT status FROM inspection WHERE id = ?",
        [inspection_id], one=True
    )
    
    progress_raw = query_db("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN ii.status NOT IN ('pending', 'skipped') THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN ii.status = 'skipped' THEN 1 ELSE 0 END) as skipped
        FROM inspection_item ii
        JOIN item_template it ON ii.item_template_id = it.id
        WHERE ii.inspection_id = ?
        
    """, [inspection_id], one=True)
    
    defect_count = query_db("""
        SELECT COUNT(*) as defects
        FROM inspection_item ii
        WHERE ii.inspection_id = ?
        AND ii.status IN ('not_to_standard', 'not_installed')
    """, [inspection_id], one=True)
    
    progress = {
        'total': progress_raw['total'] or 0,
        'completed': progress_raw['completed'] or 0,
        'defects': defect_count['defects'] or 0,
        'skipped': progress_raw['skipped'] or 0,
    }
    progress['active'] = progress['total'] - progress['skipped']
    
    return render_template('inspection/_progress.html', progress=progress,
                          inspection_status=inspection['status'] if inspection else 'unknown')


@inspection_bp.route('/<inspection_id>/open-defects')
@require_auth
def get_open_defects(inspection_id):
    tenant_id = session['tenant_id']
    
    inspection = query_db("""
        SELECT i.*, ic.cycle_number
        FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.id = ? AND i.tenant_id = ?
    """, [inspection_id, tenant_id], one=True)
    
    if not inspection:
        abort(404)
    
    is_initial = inspection['cycle_number'] == 1
    open_defects = []
    
    if not is_initial:
        ok_items = query_db("""
            SELECT item_template_id FROM inspection_item
            WHERE inspection_id = ? AND status = 'ok'
        """, [inspection_id])
        ok_template_ids = set(item['item_template_id'] for item in ok_items)
        
        all_open_defects = query_db("""
            SELECT d.*, it.item_description, ct.category_name, at.area_name,
                   ic.cycle_number as raised_cycle, d.item_template_id
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at ON ct.area_id = at.id
            JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id
            WHERE d.unit_id = ? AND d.status = 'open'
            ORDER BY at.area_order, ct.category_order, it.item_order
        """, [inspection['unit_id']])
        
        open_defects = [d for d in all_open_defects if d['item_template_id'] not in ok_template_ids]
    
    return render_template('inspection/_open_defects.html',
                         inspection_id=inspection_id,
                         is_initial=is_initial,
                         open_defects=open_defects)


@inspection_bp.route('/<inspection_id>/defect-count')
@require_auth
def get_defect_count(inspection_id):
    defect_count = query_db("""
        SELECT COUNT(*) as defects
        FROM inspection_item ii
        WHERE ii.inspection_id = ?
        AND ii.status IN ('not_to_standard', 'not_installed')
    """, [inspection_id], one=True)
    
    count = defect_count['defects'] or 0
    
    if count > 0:
        suffix = 's' if count != 1 else ''
        return f'<span class="text-red-600 font-medium">{count} defect{suffix} will be raised.</span>'
    else:
        return ''
