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
    """Start an inspection for a unit within a cycle."""
    tenant_id = session['tenant_id']
    db = get_db()
    cycle_id = request.args.get('cycle_id')
    
    if not cycle_id:
        # Find active cycle
        cycle = query_db("""
            SELECT ic.* FROM inspection_cycle ic
            JOIN unit u ON ic.phase_id = u.phase_id
            WHERE u.id = ? AND ic.status = 'active'
            ORDER BY ic.cycle_number DESC LIMIT 1
        """, [unit_id], one=True)
        if not cycle:
            abort(400, "No active inspection cycle")
        cycle_id = cycle['id']
    
    # Validate cycle exists and is active
    cycle = query_db(
        "SELECT * FROM inspection_cycle WHERE id = ? AND tenant_id = ? AND status = 'active'",
        [cycle_id, tenant_id], one=True
    )
    if not cycle:
        abort(400, "Cycle not active or not found")
    
    # Get unit details
    unit = query_db("""
        SELECT u.*, ph.phase_name, p.project_name
        FROM unit u
        JOIN phase ph ON u.phase_id = ph.id
        JOIN project p ON ph.project_id = p.id
        WHERE u.id = ? AND u.tenant_id = ?
    """, [unit_id, tenant_id], one=True)
    
    if not unit:
        abort(404)
    
    # Check for existing inspection in this cycle
    existing = query_db(
        "SELECT * FROM inspection WHERE unit_id = ? AND cycle_id = ?",
        [unit_id, cycle_id], one=True
    )
    
    if existing:
        return redirect(url_for('inspection.inspect', inspection_id=existing['id']))
    
    # Create new inspection
    inspection_id = generate_id()
    db.execute("""
        INSERT INTO inspection (id, tenant_id, unit_id, cycle_id,
                               inspection_date, inspector_id, inspector_name, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'in_progress')
    """, [inspection_id, tenant_id, unit_id, cycle_id,
          date.today().isoformat(), session['user_id'], session['user_name']])
    
    # Get excluded items for this cycle
    excluded_items = query_db(
        "SELECT item_template_id FROM cycle_excluded_item WHERE cycle_id = ?",
        [cycle_id]
    )
    excluded_ids = set(e['item_template_id'] for e in excluded_items)
    
    # For follow-up cycles, get previous inspection statuses
    previous_statuses = {}
    if cycle['cycle_number'] > 1:
        # Find previous cycle's inspection for this unit
        prev_inspection = query_db("""
            SELECT ii.item_template_id, ii.status, ii.comment
            FROM inspection_item ii
            JOIN inspection i ON ii.inspection_id = i.id
            JOIN inspection_cycle ic ON i.cycle_id = ic.id
            WHERE i.unit_id = ? AND ic.cycle_number = ?
        """, [unit_id, cycle['cycle_number'] - 1])
        previous_statuses = {p['item_template_id']: {'status': p['status'], 'comment': p['comment']} for p in prev_inspection}
    
    # Create inspection_item records for all items
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
            # Excluded this cycle
            status = 'skipped'
            comment = None
        elif item['id'] in previous_statuses:
            # Copy from previous cycle
            prev = previous_statuses[item['id']]
            status = prev['status']
            comment = prev['comment']
        else:
            # New item or first cycle
            status = 'pending'
            comment = None
        
        db.execute("""
            INSERT INTO inspection_item (id, tenant_id, inspection_id, item_template_id, status, comment)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [item_id, tenant_id, inspection_id, item['id'], status, comment])
    
    # Update unit status
    db.execute("UPDATE unit SET status = 'in_progress' WHERE id = ?", [unit_id])
    
    db.commit()
    
    return redirect(url_for('inspection.inspect', inspection_id=inspection_id))


@inspection_bp.route('/<inspection_id>')
@require_auth
def inspect(inspection_id):
    """Main inspection page."""
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
    
    # Determine inspection type based on cycle number
    is_initial = inspection['cycle_number'] == 1
    
    # Get template for areas
    template = get_inspection_template(tenant_id, inspection['unit_type'])
    
    # Progress stats - count only PARENT items (children follow parent status)
    progress_raw = query_db("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN ii.status NOT IN ('pending', 'skipped') THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN ii.status = 'skipped' THEN 1 ELSE 0 END) as skipped
        FROM inspection_item ii
        JOIN item_template it ON ii.item_template_id = it.id
        WHERE ii.inspection_id = ?
        AND it.parent_item_id IS NULL
    """, [inspection_id], one=True)
    
    # Defect count - ALL items (parent + sub-items)
    defect_count = query_db("""
        SELECT COUNT(*) as defects
        FROM inspection_item ii
        WHERE ii.inspection_id = ?
        AND ii.status IN ('not_to_standard', 'not_installed')
    """, [inspection_id], one=True)
    
    # Calculate derived values in Python (Jinja2 math can be unreliable)
    progress = {
        'total': progress_raw['total'] or 0,
        'completed': progress_raw['completed'] or 0,
        'defects': defect_count['defects'] or 0,
        'skipped': progress_raw['skipped'] or 0,
    }
    progress['active'] = progress['total'] - progress['skipped']
    
    # Get open defects from previous cycles (for follow-up display)
    open_defects = []
    if not is_initial:
        open_defects = query_db("""
            SELECT d.*, it.item_description, ct.category_name, at.area_name,
                   ic.cycle_number as raised_cycle,
                   dh.comment as latest_comment
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at ON ct.area_id = at.id
            JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id
            LEFT JOIN (
                SELECT defect_id, comment FROM defect_history 
                WHERE id IN (SELECT MAX(id) FROM defect_history GROUP BY defect_id)
            ) dh ON dh.defect_id = d.id
            WHERE d.unit_id = ? AND d.status = 'open'
            ORDER BY at.area_order, ct.category_order, it.item_order
        """, [inspection['unit_id']])
    
    # Get category comments for this unit (existing)
    category_comments = query_db("""
        SELECT cc.*, ct.category_name, at.area_name
        FROM category_comment cc
        JOIN category_template ct ON cc.category_template_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        WHERE cc.unit_id = ? AND cc.status = 'open'
    """, [inspection['unit_id']])
    
    # Area defect counts for tab badges
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
    
    # Area notes for this cycle
    area_notes = query_db("""
        SELECT area_template_id, note FROM cycle_area_note
        WHERE cycle_id = ?
    """, [inspection['cycle_id']])
    area_notes_map = {n['area_template_id']: n['note'] for n in area_notes}
    
    # Check if PDF generation is available
    try:
        from flask import current_app
        pdf_available = 'pdf' in [bp.name for bp in current_app.blueprints.values()]
    except:
        pdf_available = False
    
    return render_template('inspection/inspect.html',
                          inspection=inspection,
                          template=template,
                          progress=progress,
                          is_initial=is_initial,
                          open_defects=open_defects,
                          category_comments=category_comments,
                          area_defect_map=area_defect_map,
                          area_notes_map=area_notes_map,
                          pdf_available=pdf_available)


@inspection_bp.route('/<inspection_id>/area/<area_id>')
@require_auth
def inspect_area(inspection_id, area_id):
    """Load area checklist (HTMX partial)."""
    tenant_id = session['tenant_id']
    
    inspection = query_db("""
        SELECT i.*, ic.cycle_number, ic.id as cycle_id, i.unit_id
        FROM inspection i 
        JOIN inspection_cycle ic ON i.cycle_id = ic.id 
        WHERE i.id = ? AND i.tenant_id = ?
    """, [inspection_id, tenant_id], one=True)
    if not inspection:
        abort(404)
    
    area = query_db("SELECT * FROM area_template WHERE id = ?", [area_id], one=True)
    if not area:
        abort(404)
    
    is_followup = inspection['cycle_number'] > 1
    
    # Get open defects for this unit, keyed by item_template_id
    open_defects_map = {}
    if is_followup:
        open_defects = query_db("""
            SELECT d.*, it.item_description, ic.cycle_number as raised_cycle,
                   dh.comment as latest_comment
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id
            JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id
            LEFT JOIN (
                SELECT defect_id, comment FROM defect_history 
                WHERE id IN (SELECT MAX(id) FROM defect_history GROUP BY defect_id)
            ) dh ON dh.defect_id = d.id
            WHERE d.unit_id = ? AND d.status = 'open'
        """, [inspection['unit_id']])
        open_defects_map = {d['item_template_id']: d for d in open_defects}
    
    # Get area-specific note for this cycle
    area_note = query_db("""
        SELECT note FROM cycle_area_note
        WHERE cycle_id = ? AND area_template_id = ?
    """, [inspection['cycle_id'], area_id], one=True)
    
    # Get categories with items and statuses
    categories = query_db("""
        SELECT * FROM category_template
        WHERE area_id = ?
        ORDER BY category_order
    """, [area_id])
    
    categories_data = []
    for cat in categories:
        # Get existing category comment for this unit
        cat_comment = query_db("""
            SELECT cc.*, cch.comment as latest_comment
            FROM category_comment cc
            LEFT JOIN category_comment_history cch ON cch.category_comment_id = cc.id
            WHERE cc.unit_id = (SELECT unit_id FROM inspection WHERE id = ?)
            AND cc.category_template_id = ?
            ORDER BY cch.created_at DESC LIMIT 1
        """, [inspection_id, cat['id']], one=True)
        
        items = query_db("""
            SELECT it.*, ii.status, ii.comment,
                   parent.item_description as parent_description,
                   parent_ii.status as parent_status,
                   (SELECT COUNT(*) FROM item_template child WHERE child.parent_item_id = it.id) as child_count
            FROM item_template it
            JOIN inspection_item ii ON ii.item_template_id = it.id AND ii.inspection_id = ?
            LEFT JOIN item_template parent ON it.parent_item_id = parent.id
            LEFT JOIN inspection_item parent_ii ON parent_ii.item_template_id = parent.id AND parent_ii.inspection_id = ?
            WHERE it.category_id = ?
            ORDER BY it.item_order
        """, [inspection_id, inspection_id, cat['id']])
        
        # Enrich items with defect info
        items_with_defects = []
        for item in items:
            item_dict = dict(item)
            defect = open_defects_map.get(item['id'])
            if defect:
                item_dict['has_open_defect'] = True
                item_dict['defect_comment'] = defect['latest_comment'] or defect['original_comment']
                item_dict['defect_cycle'] = defect['raised_cycle']
                item_dict['defect_type'] = defect['defect_type']
            else:
                item_dict['has_open_defect'] = False
            items_with_defects.append(item_dict)
        
        # Check if all items in this category are skipped
        all_skipped = all(item['status'] == 'skipped' for item in items) if items else False
        
        categories_data.append({
            'id': cat['id'],
            'name': cat['category_name'],
            'checklist': items_with_defects,
            'comment': cat_comment,
            'all_skipped': all_skipped
        })
    
    return render_template('inspection/area.html',
                          inspection=inspection,
                          area=area,
                          area_note=area_note['note'] if area_note else None,
                          categories=categories_data,
                          is_followup=is_followup)


@inspection_bp.route('/<inspection_id>/item/<item_id>', methods=['POST'])
@require_auth
def update_item(inspection_id, item_id):
    """Update item status (HTMX)."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    status = request.form.get('status', 'pending')
    comment = request.form.get('comment', '').strip()
    area_id = request.form.get('area_id')
    
    db.execute("""
        UPDATE inspection_item 
        SET status = ?, comment = ?, updated_at = CURRENT_TIMESTAMP
        WHERE inspection_id = ? AND item_template_id = ? AND tenant_id = ?
    """, [status, comment if comment else None, inspection_id, item_id, tenant_id])
    db.commit()
    
    # Return updated area
    if area_id:
        return redirect(url_for('inspection.inspect_area', inspection_id=inspection_id, area_id=area_id))
    
    return '<div class="text-green-600 text-sm">Updated</div>'


@inspection_bp.route('/<inspection_id>/category-comment/<category_id>', methods=['POST'])
@require_auth
def update_category_comment(inspection_id, category_id):
    """Add/update category-level comment (HTMX)."""
    tenant_id = session['tenant_id']
    db = get_db()
    
    comment = request.form.get('comment', '').strip()
    area_id = request.form.get('area_id')
    
    inspection = query_db(
        "SELECT * FROM inspection WHERE id = ? AND tenant_id = ?",
        [inspection_id, tenant_id], one=True
    )
    if not inspection:
        abort(404)
    
    if comment:
        # Check if category comment exists for this unit
        existing = query_db("""
            SELECT * FROM category_comment
            WHERE unit_id = ? AND category_template_id = ?
        """, [inspection['unit_id'], category_id], one=True)
        
        if existing:
            # Add history entry
            history_id = generate_id()
            db.execute("""
                INSERT INTO category_comment_history 
                (id, tenant_id, category_comment_id, cycle_id, comment, status)
                VALUES (?, ?, ?, ?, ?, 'open')
            """, [history_id, tenant_id, existing['id'], inspection['cycle_id'], comment])
        else:
            # Create new category comment
            cc_id = generate_id()
            db.execute("""
                INSERT INTO category_comment 
                (id, tenant_id, unit_id, category_template_id, raised_cycle_id, status)
                VALUES (?, ?, ?, ?, ?, 'open')
            """, [cc_id, tenant_id, inspection['unit_id'], category_id, inspection['cycle_id']])
            
            # Add history entry
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
    """Submit inspection - create defects and defect history."""
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
    
    # Validation for initial inspection
    if is_initial:
        # Check all non-skipped parent items inspected
        pending = query_db("""
            SELECT COUNT(*) as count 
            FROM inspection_item ii
            JOIN item_template it ON ii.item_template_id = it.id
            WHERE ii.inspection_id = ? 
            AND ii.status = 'pending'
            AND it.parent_item_id IS NULL
        """, [inspection_id], one=True)
        
        if pending['count'] > 0:
            from flask import flash
            flash(f"{pending['count']} main items not yet inspected", 'error')
            return redirect(url_for('inspection.inspect', inspection_id=inspection_id))
        
        # Check defects have comments
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
    
    # Process defects
    defect_items = query_db("""
        SELECT ii.*, it.id as template_id
        FROM inspection_item ii
        JOIN item_template it ON ii.item_template_id = it.id
        WHERE ii.inspection_id = ?
        AND ii.status IN ('not_to_standard', 'not_installed')
    """, [inspection_id])
    
    for item in defect_items:
        # Check if open defect exists for this item
        existing = query_db("""
            SELECT * FROM defect 
            WHERE unit_id = ? AND item_template_id = ? AND status = 'open'
        """, [inspection['unit_id'], item['template_id']], one=True)
        
        if existing:
            # Add history entry for existing defect
            history_id = generate_id()
            db.execute("""
                INSERT INTO defect_history (id, tenant_id, defect_id, cycle_id, comment, status)
                VALUES (?, ?, ?, ?, ?, 'open')
            """, [history_id, tenant_id, existing['id'], inspection['cycle_id'], 
                  item['comment'] or 'Not rectified'])
        else:
            # Create new defect
            defect_id = generate_id()
            db.execute("""
                INSERT INTO defect (id, tenant_id, unit_id, item_template_id,
                                   raised_cycle_id, defect_type, status, original_comment)
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?)
            """, [defect_id, tenant_id, inspection['unit_id'], item['template_id'],
                  inspection['cycle_id'], item['status'], item['comment']])
            
            # Add first history entry
            history_id = generate_id()
            db.execute("""
                INSERT INTO defect_history (id, tenant_id, defect_id, cycle_id, comment, status)
                VALUES (?, ?, ?, ?, ?, 'open')
            """, [history_id, tenant_id, defect_id, inspection['cycle_id'], item['comment']])
    
    # Mark cleared defects (items that were OK this cycle but had open defects)
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
            # Clear the defect
            db.execute("""
                UPDATE defect
                SET status = 'cleared', cleared_cycle_id = ?, cleared_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, [inspection['cycle_id'], defect['id']])
            
            # Add cleared history entry
            history_id = generate_id()
            db.execute("""
                INSERT INTO defect_history (id, tenant_id, defect_id, cycle_id, comment, status)
                VALUES (?, ?, ?, ?, ?, 'cleared')
            """, [history_id, tenant_id, defect['id'], inspection['cycle_id'], 'Rectified'])
    
    # Update inspection status
    db.execute("""
        UPDATE inspection 
        SET status = 'submitted', submitted_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, [inspection_id])
    
    # Update unit status
    open_defects = query_db(
        "SELECT COUNT(*) as count FROM defect WHERE unit_id = ? AND status = 'open'",
        [inspection['unit_id']], one=True
    )
    
    unit_status = 'defects_open' if open_defects['count'] > 0 else 'cleared'
    db.execute("UPDATE unit SET status = ? WHERE id = ?", [unit_status, inspection['unit_id']])
    
    db.commit()
    
    # Redirect based on role
    role = session.get('role', 'student')
    if role == 'architect':
        return redirect(url_for('certification.dashboard'))
    else:
        return redirect(url_for('projects.view_unit', unit_id=inspection['unit_id']))


@inspection_bp.route('/<inspection_id>/progress')
@require_auth
def get_progress(inspection_id):
    """Get progress stats (HTMX partial)."""
    progress_raw = query_db("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN ii.status NOT IN ('pending', 'skipped') THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN ii.status = 'skipped' THEN 1 ELSE 0 END) as skipped
        FROM inspection_item ii
        JOIN item_template it ON ii.item_template_id = it.id
        WHERE ii.inspection_id = ?
        AND it.parent_item_id IS NULL
    """, [inspection_id], one=True)
    
    # Defect count - ALL items (parent + sub-items)
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
    
    return render_template('inspection/_progress.html', progress=progress)
