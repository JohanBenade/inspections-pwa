"""
Inspection routes - Main inspection workflow.
Inspections are conducted within a cycle created by the architect.
"""
from datetime import date, datetime, timezone
from flask import Blueprint, render_template, session, redirect, url_for, abort, request, jsonify, make_response
from app.auth import require_auth
from app.utils import generate_id
from app.utils.wash import wash_description
from app.utils.audit import log_audit
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
            WHERE u.id = ? AND ic.tenant_id = ? AND ic.status = 'active'
            ORDER BY ic.cycle_number DESC LIMIT 1
        """, [unit_id, tenant_id], one=True)
        if not cycle:
            abort(404)
        cycle_id = cycle['id']
    else:
        cycle = query_db(
            "SELECT * FROM inspection_cycle WHERE id = ? AND tenant_id = ?",
            [cycle_id, tenant_id], one=True
        )
        if not cycle:
            abort(404)
    
    unit = query_db(
        "SELECT * FROM unit WHERE id = ? AND tenant_id = ?",
        [unit_id, tenant_id], one=True
    )
    if not unit:
        abort(404)
    
    existing = query_db(
        "SELECT * FROM inspection WHERE unit_id = ? AND cycle_id = ? AND tenant_id = ?",
        [unit_id, cycle_id, tenant_id], one=True
    )
    
    if existing:
        return redirect(url_for('inspection.inspect', inspection_id=existing['id']))
    
    inspection_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()
    user_id = session['user_id']
    user_name = session['user_name']
    
    # Check if this is a followup cycle
    if cycle['cycle_number'] > 1:
        # Get the previous cycle's inspection to carry forward items
        prev_inspection = query_db("""
            SELECT i.id FROM inspection i
            JOIN inspection_cycle ic ON i.cycle_id = ic.id
            WHERE i.unit_id = ? AND ic.cycle_number = ?
            AND i.tenant_id = ?
        """, [unit_id, cycle['cycle_number'] - 1, tenant_id], one=True)
    
    db.execute("""
        INSERT INTO inspection
        (id, tenant_id, unit_id, cycle_id, inspection_date,
         inspector_id, inspector_name, status, started_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'in_progress', ?, ?, ?)
    """, [inspection_id, tenant_id, unit_id, cycle_id,
          date.today().isoformat(), user_id, user_name, now, now, now])
    
    templates = query_db(
        "SELECT id FROM item_template WHERE tenant_id = ?", [tenant_id]
    )
    
    # If followup cycle, carry forward statuses from previous inspection
    prev_item_map = {}
    if cycle['cycle_number'] > 1 and prev_inspection:
        prev_items = query_db("""
            SELECT item_template_id, status, comment
            FROM inspection_item
            WHERE inspection_id = ?
        """, [prev_inspection['id']])
        prev_item_map = {item['item_template_id']: item for item in prev_items}
    
    for t in templates:
        prev = prev_item_map.get(t['id'])
        if prev:
            status = prev['status']
            comment = prev['comment'] if status in ('not_to_standard', 'not_installed') else None
        else:
            status = 'pending'
            comment = None
        
        db.execute("""
            INSERT INTO inspection_item
            (id, tenant_id, inspection_id, item_template_id, status, comment, marked_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL)
        """, [generate_id(), tenant_id, inspection_id, t['id'], status, comment])
    
    db.commit()
    
    log_audit(db, tenant_id, 'inspection', inspection_id, 'inspection_started',
              old_value=None, new_value='in_progress',
              user_id=user_id, user_name=user_name)
    db.commit()
    
    return redirect(url_for('inspection.inspect', inspection_id=inspection_id))


@inspection_bp.route('/<inspection_id>')
@require_auth
def inspect(inspection_id):
    tenant_id = session['tenant_id']
    
    inspection = query_db("""
        SELECT i.*, u.unit_type, u.unit_number, u.block, u.floor,
               ic.cycle_number, ic.general_notes as cycle_notes
        FROM inspection i
        JOIN unit u ON i.unit_id = u.id
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.id = ? AND i.tenant_id = ?
    """, [inspection_id, tenant_id], one=True)
    
    if not inspection:
        abort(404)
    
    is_initial = inspection['cycle_number'] == 1
    is_followup = not is_initial
    template = get_inspection_template(tenant_id, inspection['unit_type'])
    
    # Filter template to only show areas that have inspection items for this unit
    active_area_ids = set(r['area_id'] for r in query_db("""
        SELECT DISTINCT at.id AS area_id
        FROM inspection_item ii
        JOIN item_template it ON ii.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        WHERE ii.inspection_id = ?
        AND ii.status != 'skipped'
    """, [inspection_id]))
    template = [a for a in template if a['id'] in active_area_ids]
    
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
        'is_followup': is_followup,
    }
    progress['active'] = progress['total'] - progress['skipped']
    
    # Followup cycle: calculate defect review progress
    if is_followup:
        followup_raw = query_db("""
            SELECT COUNT(*) as total_to_review,
                   SUM(CASE WHEN ii.marked_at IS NOT NULL THEN 1 ELSE 0 END) as actioned
            FROM inspection_item ii
            JOIN defect d ON d.item_template_id = ii.item_template_id
                AND d.unit_id = ? AND d.status = 'open'
            WHERE ii.inspection_id = ?
        """, [inspection['unit_id'], inspection_id], one=True)
        progress['followup_total'] = followup_raw['total_to_review'] or 0
        progress['followup_actioned'] = followup_raw['actioned'] or 0
    
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
                         is_followup=is_followup,
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
    
    # Peek at cycle number to determine default filter
    insp_peek = query_db("""
        SELECT ic.cycle_number FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.id = ?
    """, [inspection_id], one=True)
    default_filter = 'to_inspect' if (insp_peek and insp_peek['cycle_number'] > 1) else 'all'
    filter_mode = request.args.get('filter', default_filter)
    
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
    all_inspection_defects = query_db("""
        SELECT idf.id, idf.inspection_item_id, idf.description, idf.defect_type
        FROM inspection_defect idf
        WHERE idf.inspection_id = ? AND idf.tenant_id = ?
        ORDER BY idf.created_at
    """, [inspection_id, tenant_id])
    inspection_defects_map = {}
    for idef in (all_inspection_defects or []):
        idef_dict = dict(idef)
        iid = idef_dict['inspection_item_id']
        if iid not in inspection_defects_map:
            inspection_defects_map[iid] = []
        inspection_defects_map[iid].append(idef_dict)
    
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
                   ii.id, ii.status, ii.comment, ii.marked_at,
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
            
            if filter_mode == 'to_inspect':
                # Show only defective items NOT yet actioned this session
                if not has_open_defect:
                    if not is_parent or item['template_id'] not in parent_has_defective_child:
                        continue
                if item['marked_at'] is not None:
                    continue
            
            if filter_mode == 'inspected':
                # Show only defective items already actioned this session
                if not has_open_defect:
                    if not is_parent or item['template_id'] not in parent_has_defective_child:
                        continue
                if item['marked_at'] is None:
                    continue
            
            parent_status = None
            if is_child:
                parent_status = parent_status_map.get(item['parent_item_id'])
            
            if item['status'] != 'skipped':
                all_skipped = False
            
            item_defects = inspection_defects_map.get(item['id'], [])
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
                'inspection_defects': item_defects,
            })
        
        # Skip empty categories in filter modes
        if filter_mode in ('defects', 'to_inspect', 'inspected') and not checklist:
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


def _build_item_for_render(inspection_id, item_id, tenant_id, unit_id=None, cycle_number=None):
    """Build the template context dict for a single inspection item."""
    item_raw = query_db("""
        SELECT it.id as template_id, it.item_description, it.parent_item_id, it.item_order,
               ii.id, ii.status, ii.comment, ii.marked_at,
               (SELECT COUNT(*) FROM item_template WHERE parent_item_id = it.id) as child_count
        FROM item_template it
        JOIN inspection_item ii ON it.id = ii.item_template_id
        WHERE ii.id = ? AND ii.inspection_id = ?
    """, [item_id, inspection_id], one=True)

    if not item_raw:
        return None

    parent_status = None
    if item_raw['parent_item_id']:
        parent_item = query_db("""
            SELECT ii.status FROM inspection_item ii
            JOIN item_template it ON ii.item_template_id = it.id
            WHERE it.id = ? AND ii.inspection_id = ?
        """, [item_raw['parent_item_id'], inspection_id], one=True)
        if parent_item:
            parent_status = parent_item['status']

    has_open_defect = False
    defect_cycle = None
    defect_comment = None
    if unit_id and cycle_number and cycle_number > 1:
        defect_info = query_db("""
            SELECT d.original_comment, ic.cycle_number as raised_cycle
            FROM defect d
            JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id
            WHERE d.unit_id = ? AND d.item_template_id = ? AND d.status = 'open'
        """, [unit_id, item_raw['template_id']], one=True)
        if defect_info:
            has_open_defect = True
            defect_cycle = defect_info['raised_cycle']
            defect_comment = defect_info['original_comment']

    inspection_defects = query_db("""
        SELECT id, description, defect_type FROM inspection_defect
        WHERE inspection_item_id = ? AND tenant_id = ?
        ORDER BY created_at
    """, [item_id, tenant_id])
    inspection_defects = [dict(d) for d in inspection_defects] if inspection_defects else []
    return {
        'id': item_raw['id'],
        'template_id': item_raw['template_id'],
        'item_description': item_raw['item_description'],
        'status': item_raw['status'],
        'comment': item_raw['comment'],
        'parent_item_id': item_raw['parent_item_id'],
        'depth': 0 if item_raw['parent_item_id'] is None else 1,
        'child_count': item_raw['child_count'],
        'parent_status': parent_status,
        'has_open_defect': has_open_defect,
        'defect_cycle': defect_cycle,
        'defect_comment': defect_comment,
        'inspection_defects': inspection_defects,
    }


def _render_single_item(inspection_id, item_id, tenant_id, area_id, swap_oob=False, force_expanded=False):
    """Render a single item partial for HTMX per-item swap.

    Returns content only (no wrapper div). The stable wrapper <div id="item-{id}">
    lives in area.html and never gets replaced (innerHTML swap).
    For OOB children, manually wraps content in <div id="item-{id}" hx-swap-oob="innerHTML">.
    """
    inspection = query_db("""
        SELECT i.*, u.unit_type, u.unit_number, u.id as unit_id,
               ic.cycle_number, ic.id as cycle_id
        FROM inspection i
        JOIN unit u ON i.unit_id = u.id
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.id = ? AND i.tenant_id = ?
    """, [inspection_id, tenant_id], one=True)

    area = query_db(
        "SELECT * FROM area_template WHERE id = ? AND tenant_id = ?",
        [area_id, tenant_id], one=True
    )

    item = _build_item_for_render(
        inspection_id, item_id, tenant_id,
        unit_id=inspection['unit_id'],
        cycle_number=inspection['cycle_number']
    )

    if not item or not inspection or not area:
        return ''

    is_followup = inspection['cycle_number'] > 1

    html = render_template('inspection/_single_item.html',
                           item=item,
                           inspection=inspection,
                           area=area,
                           is_followup=is_followup,
                           force_expanded=force_expanded)

    if swap_oob:
        html = '<div id="item-' + item_id + '" hx-swap-oob="innerHTML">' + html + '</div>'

    return html


@inspection_bp.route('/<inspection_id>/item/<item_id>', methods=['POST'])
@require_auth
def update_item(inspection_id, item_id):
    tenant_id = session['tenant_id']
    db = get_db()
    
    status = request.form.get('status')
    comment = request.form.get('comment', '').strip()
    area_id = request.form.get('area_id')
    
    inspection = query_db(
        "SELECT * FROM inspection WHERE id = ? AND tenant_id = ?",
        [inspection_id, tenant_id], one=True
    )
    if not inspection:
        abort(404)
    
    item = query_db(
        "SELECT * FROM inspection_item WHERE id = ? AND inspection_id = ?",
        [item_id, inspection_id], one=True
    )
    if not item:
        abort(404)
    
    template = query_db(
        "SELECT * FROM item_template WHERE id = ?",
        [item['item_template_id']], one=True
    )
    
    now = datetime.now(timezone.utc).isoformat()
    
    if status:
        old_status = item['status']
        
        if comment:
            db.execute("""
                UPDATE inspection_item SET status = ?, comment = ?, marked_at = ?
                WHERE id = ?
            """, [status, comment, now, item_id])
        else:
            db.execute("""
                UPDATE inspection_item SET status = ?, marked_at = ?
                WHERE id = ?
            """, [status, now, item_id])
        
        # Parent cascade: if parent marked not_installed, cascade to children
        if template and template['parent_item_id'] is None and status == 'not_installed':
            children = query_db("""
                SELECT ii.id FROM inspection_item ii
                JOIN item_template it ON ii.item_template_id = it.id
                WHERE it.parent_item_id = ? AND ii.inspection_id = ?
            """, [item['item_template_id'], inspection_id])
            
            for child in children:
                db.execute("""
                    UPDATE inspection_item SET status = 'not_installed', marked_at = ?
                    WHERE id = ?
                """, [now, child['id']])
        
        # Parent cascade: if parent marked ok/installed, reset children to pending
        if template and template['parent_item_id'] is None and status == 'ok':
            children = query_db("""
                SELECT ii.id, ii.status FROM inspection_item ii
                JOIN item_template it ON ii.item_template_id = it.id
                WHERE it.parent_item_id = ? AND ii.inspection_id = ?
            """, [item['item_template_id'], inspection_id])
            
            for child in children:
                if child['status'] == 'not_installed':
                    db.execute("""
                        UPDATE inspection_item SET status = 'pending', marked_at = NULL
                        WHERE id = ?
                    """, [child['id']])
                    db.execute("""
                        DELETE FROM inspection_defect WHERE inspection_item_id = ?
                    """, [child['id']])
        
        # Clear inspection defects when item transitions to OK
        if status == 'ok':
            db.execute("""
                DELETE FROM inspection_defect WHERE inspection_item_id = ?
            """, [item_id])
        
        # Clear children inspection defects when parent cascades to not_installed
        if template and template['parent_item_id'] is None and status == 'not_installed':
            for child in (query_db("""
                SELECT ii.id FROM inspection_item ii
                JOIN item_template it ON ii.item_template_id = it.id
                WHERE it.parent_item_id = ? AND ii.inspection_id = ?
            """, [item['item_template_id'], inspection_id]) or []):
                db.execute("""
                    DELETE FROM inspection_defect WHERE inspection_item_id = ?
                """, [child['id']])
        
        # Auto-transition inspection from not_started to in_progress
        if inspection['status'] == 'not_started':
            db.execute("""
                UPDATE inspection SET status = 'in_progress', started_at = ?, updated_at = ?
                WHERE id = ?
            """, [now, now, inspection_id])
        
        db.commit()
    
    if area_id:
        tenant_id_for_render = session['tenant_id']
        html = _render_single_item(inspection_id, item_id, tenant_id_for_render, area_id)

        if template and template['parent_item_id'] is None and status in ('ok', 'not_installed'):
            children = query_db("""
                SELECT ii.id FROM inspection_item ii
                JOIN item_template it ON ii.item_template_id = it.id
                WHERE it.parent_item_id = ? AND ii.inspection_id = ?
            """, [item['item_template_id'], inspection_id])
            for child in children:
                child_html = _render_single_item(
                    inspection_id, child['id'], tenant_id_for_render, area_id, swap_oob=True
                )
                html += child_html

        response = make_response(html)
        response.headers['HX-Trigger'] = 'areaUpdated'
        return response
    
    return '', 204


@inspection_bp.route('/<inspection_id>/item/<item_id>/defect', methods=['POST'])
@require_auth
def add_defect(inspection_id, item_id):
    tenant_id = session['tenant_id']
    db = get_db()
    description = request.form.get('description', '').strip()
    area_id = request.form.get('area_id')
    if not description:
        return '', 204
    inspection = query_db("SELECT * FROM inspection WHERE id = ? AND tenant_id = ?", [inspection_id, tenant_id], one=True)
    if not inspection:
        abort(404)
    item = query_db("SELECT * FROM inspection_item WHERE id = ? AND inspection_id = ?", [item_id, inspection_id], one=True)
    if not item:
        abort(404)
    now = datetime.now(timezone.utc).isoformat()
    if len(description) > 0:
        description = description[0].upper() + description[1:]
    if item['status'] not in ('not_to_standard', 'not_installed'):
        db.execute("UPDATE inspection_item SET status = 'not_to_standard', marked_at = ? WHERE id = ?", [now, item_id])
    if inspection['status'] == 'not_started':
        db.execute("UPDATE inspection SET status = 'in_progress', started_at = ?, updated_at = ? WHERE id = ?", [now, now, inspection_id])
    defect_id = generate_id()
    db.execute("INSERT INTO inspection_defect (id, tenant_id, inspection_id, inspection_item_id, item_template_id, description, defect_type, created_at) VALUES (?, ?, ?, ?, ?, ?, 'not_to_standard', ?)", [defect_id, tenant_id, inspection_id, item_id, item['item_template_id'], description, now])
    db.commit()
    if area_id:
        html = _render_single_item(inspection_id, item_id, tenant_id, area_id, force_expanded=True)
        response = make_response(html)
        response.headers['HX-Trigger'] = 'areaUpdated'
        return response
    return '', 204


@inspection_bp.route('/<inspection_id>/item/<item_id>/defect/<defect_id>', methods=['DELETE'])
@require_auth
def remove_defect(inspection_id, item_id, defect_id):
    tenant_id = session['tenant_id']
    db = get_db()
    area_id = request.args.get('area_id')
    inspection = query_db("SELECT * FROM inspection WHERE id = ? AND tenant_id = ?", [inspection_id, tenant_id], one=True)
    if not inspection:
        abort(404)
    db.execute("DELETE FROM inspection_defect WHERE id = ? AND inspection_item_id = ? AND tenant_id = ?", [defect_id, item_id, tenant_id])
    db.commit()
    if area_id:
        html = _render_single_item(inspection_id, item_id, tenant_id, area_id, force_expanded=True)
        response = make_response(html)
        response.headers['HX-Trigger'] = 'areaUpdated'
        return response
    return '', 204


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
    else:
        # Cycle 2+: ensure all carried-forward defects have been actioned
        unactioned = query_db("""
            SELECT COUNT(*) as count
            FROM inspection_item ii
            JOIN defect d ON d.item_template_id = ii.item_template_id
                AND d.unit_id = ? AND d.status = 'open'
            WHERE ii.inspection_id = ?
            AND ii.marked_at IS NULL
        """, [inspection['unit_id'], inspection_id], one=True)
        
        if unactioned['count'] > 0:
            from flask import flash
            flash(f"{unactioned['count']} defects not yet reviewed", 'error')
            return redirect(url_for('inspection.inspect', inspection_id=inspection_id))
    
    defect_items = query_db("""
        SELECT ii.*, it.id as template_id, it.parent_item_id
        FROM inspection_item ii
        JOIN item_template it ON ii.item_template_id = it.id
        WHERE ii.inspection_id = ?
        AND ii.status IN ('not_to_standard', 'not_installed')
        AND NOT (
            it.parent_item_id IS NOT NULL
            AND ii.status = 'not_installed'
            AND EXISTS (
                SELECT 1 FROM inspection_item pi
                JOIN item_template pt ON pi.item_template_id = pt.id
                WHERE pi.inspection_id = ii.inspection_id
                AND pt.id = it.parent_item_id
                AND pi.status = 'not_installed'
            )
        )
    """, [inspection_id])
    
    for item in defect_items:
        item_defects = query_db("SELECT id, description, defect_type FROM inspection_defect WHERE inspection_item_id = ? AND tenant_id = ? ORDER BY created_at", [item['id'], tenant_id])
        item_defects = [dict(d) for d in item_defects] if item_defects else []
        if not item_defects and item['comment']:
            item_defects = [{'description': item['comment'], 'defect_type': item['status']}]
        elif not item_defects:
            item_defects = [{'description': 'Defect noted', 'defect_type': item['status']}]
        existing = query_db("SELECT * FROM defect WHERE unit_id = ? AND item_template_id = ? AND status = 'open' ORDER BY created_at DESC LIMIT 1", [inspection['unit_id'], item['template_id']], one=True)
        for idx, idef in enumerate(item_defects):
            desc_raw = idef['description']
            if idx == 0 and existing:
                if existing['status'] == 'cleared':
                    db.execute("UPDATE defect SET status = 'open', cleared_cycle_id = NULL, cleared_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?", [existing['id']])
                history_id = generate_id()
                db.execute("INSERT INTO defect_history (id, tenant_id, defect_id, cycle_id, comment, status) VALUES (?, ?, ?, ?, ?, 'open')", [history_id, tenant_id, existing['id'], inspection['cycle_id'], desc_raw or 'Not rectified'])
            else:
                defect_id = generate_id()
                washed_comment = wash_description(db, tenant_id, item['template_id'], desc_raw)
                db.execute("INSERT INTO defect (id, tenant_id, unit_id, item_template_id, raised_cycle_id, defect_type, status, original_comment, raw_comment) VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)", [defect_id, tenant_id, inspection['unit_id'], item['template_id'], inspection['cycle_id'], item['status'], washed_comment, desc_raw])
                history_id = generate_id()
                db.execute("INSERT INTO defect_history (id, tenant_id, defect_id, cycle_id, comment, status) VALUES (?, ?, ?, ?, ?, 'open')", [history_id, tenant_id, defect_id, inspection['cycle_id'], washed_comment])
    
    ok_items = query_db("""
        SELECT ii.item_template_id
        FROM inspection_item ii
        WHERE ii.inspection_id = ? AND ii.status = 'ok'
    """, [inspection_id])
    
    for item in ok_items:
        open_defects = query_db("SELECT * FROM defect WHERE unit_id = ? AND item_template_id = ? AND status = 'open'", [inspection['unit_id'], item['item_template_id']])
        for defect in (open_defects or []):
            db.execute("UPDATE defect SET status = 'cleared', cleared_cycle_id = ?, cleared_at = CURRENT_TIMESTAMP WHERE id = ?", [inspection['cycle_id'], defect['id']])
            history_id = generate_id()
            db.execute("INSERT INTO defect_history (id, tenant_id, defect_id, cycle_id, comment, status) VALUES (?, ?, ?, ?, ?, 'cleared')", [history_id, tenant_id, defect['id'], inspection['cycle_id'], 'Rectified'])
    db.execute("DELETE FROM inspection_defect WHERE inspection_id = ? AND tenant_id = ?", [inspection_id, tenant_id])
    
    db.execute("""
        UPDATE inspection 
        SET status = 'submitted', submitted_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, [inspection_id])
    
    log_audit(db, tenant_id, 'inspection', inspection_id, 'inspection_submitted',
              old_value='in_progress', new_value='submitted',
              user_id=session['user_id'], user_name=session['user_name'])
    
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
    inspection = query_db("""
        SELECT i.status, i.unit_id, ic.cycle_number
        FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.id = ?
    """, [inspection_id], one=True)
    
    is_followup = inspection['cycle_number'] > 1 if inspection else False
    
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
        'is_followup': is_followup,
    }
    progress['active'] = progress['total'] - progress['skipped']
    
    if is_followup:
        followup_raw = query_db("""
            SELECT COUNT(*) as total_to_review,
                   SUM(CASE WHEN ii.marked_at IS NOT NULL THEN 1 ELSE 0 END) as actioned
            FROM inspection_item ii
            JOIN defect d ON d.item_template_id = ii.item_template_id
                AND d.unit_id = ? AND d.status = 'open'
            WHERE ii.inspection_id = ?
        """, [inspection['unit_id'], inspection_id], one=True)
        progress['followup_total'] = followup_raw['total_to_review'] or 0
        progress['followup_actioned'] = followup_raw['actioned'] or 0
    
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
    multi_count = query_db("SELECT COUNT(*) as cnt FROM inspection_defect WHERE inspection_id = ? AND tenant_id = ?", [inspection_id, session['tenant_id']], one=True)
    count = multi_count['cnt'] or 0
    if count == 0:
        item_count = query_db("SELECT COUNT(*) as defects FROM inspection_item ii WHERE ii.inspection_id = ? AND ii.status IN ('not_to_standard', 'not_installed')", [inspection_id], one=True)
        count = item_count['defects'] or 0
    if count > 0:
        return f'<span class="text-red-600 font-medium">{count} defect{"s" if count != 1 else ""} will be raised.</span>'
    return ''


@inspection_bp.route('/<inspection_id>/area-badges')
@require_auth
def get_area_badges(inspection_id):
    """Return updated area defect badges for HTMX OOB swap."""
    area_defects = query_db("""
        SELECT at.id as area_id, at.area_name, COUNT(*) as defect_count
        FROM inspection_item ii
        JOIN item_template it ON ii.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        WHERE ii.inspection_id = ?
        AND ii.status IN ('not_to_standard', 'not_installed')
        GROUP BY at.id
    """, [inspection_id])
    badges = {d['area_id']: d['defect_count'] for d in area_defects}
    
    # Get all areas that have items for this inspection
    all_areas = query_db("""
        SELECT DISTINCT at.id
        FROM inspection_item ii
        JOIN item_template it ON ii.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        WHERE ii.inspection_id = ? AND ii.status != 'skipped'
    """, [inspection_id])
    
    html_parts = []
    for area in all_areas:
        aid = area['id']
        count = badges.get(aid, 0)
        if count > 0:
            html_parts.append(f'<span id="area-badge-{aid}" hx-swap-oob="true" class="bg-red-500 text-white text-xs px-1.5 py-0.5 rounded-full">{count}</span>')
        else:
            html_parts.append(f'<span id="area-badge-{aid}" hx-swap-oob="true"></span>')
    
    return '\n'.join(html_parts)


@inspection_bp.route('/suggestions/<item_template_id>')
@require_auth
def get_defect_suggestions(item_template_id):
    tenant_id = session['tenant_id']
    mode = request.args.get('mode', 'active')
    
    # Get item-specific suggestions
    suggestions = query_db("""
        SELECT description, usage_count FROM defect_library
        WHERE tenant_id = ? AND item_template_id = ?
        ORDER BY usage_count DESC
        LIMIT 8
    """, [tenant_id, item_template_id])
    
    if not suggestions:
        # Fallback to category-level suggestions
        cat = query_db("""
            SELECT ct.category_name
            FROM item_template it
            JOIN category_template ct ON it.category_id = ct.id
            WHERE it.id = ?
        """, [item_template_id], one=True)
        
        if cat:
            suggestions = query_db("""
                SELECT description, usage_count FROM defect_library
                WHERE tenant_id = ? AND category_name = ? AND item_template_id IS NULL
                ORDER BY usage_count DESC
                LIMIT 5
            """, [tenant_id, cat['category_name']])
    
    if not suggestions:
        return ''
    
    if mode == 'guide':
        pills_html = '<div class="flex flex-wrap gap-2.5 mt-2">'
        for s in suggestions:
            desc = s['description']
            escaped = desc.replace(chr(39), chr(92)+chr(39))
            pills_html += f'''<button type="button"
                class="px-3 py-2 bg-blue-50 text-blue-700 rounded-lg text-xs hover:bg-blue-100 transition-colors guide-pill"
                onclick="var w=this.closest('.guide-pills');var url=w.dataset.addUrl;var aid=w.dataset.areaId;var tid=w.dataset.itemId;htmx.ajax('POST',url,{{values:{{description:'{escaped}',area_id:aid}},target:'#'+tid,swap:'innerHTML'}})"
                >{desc}</button>'''
        pills_html += '</div>'
        return pills_html
    
    pills_html = '<div class="flex flex-wrap gap-2.5 mt-2">'
    for s in suggestions:
        desc = s['description']
        escaped = desc.replace(chr(39), chr(92)+chr(39))
        pills_html += f'''<button type="button"
            class="px-3 py-2 bg-blue-50 text-blue-700 rounded-lg text-xs hover:bg-blue-100 transition-colors"
            onclick="var w=this.closest('.defect-input-wrapper');htmx.ajax('POST',w.dataset.addUrl,{{target:'#'+w.dataset.itemId,swap:'innerHTML',values:{{description:'{escaped}',area_id:w.dataset.areaId}}}})"
            ontouchend="event.preventDefault();this.click()"
            >{desc}</button>'''
    pills_html += '</div>'
    return pills_html
