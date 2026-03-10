"""
Exclusion List routes - Manage named exclusion lists.
Access: Manager + Admin only.
"""
from datetime import datetime, timezone
from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from app.auth import require_manager
from app.utils import generate_id
from app.services.db import get_db, query_db

exclusion_lists_bp = Blueprint('exclusion_lists', __name__, url_prefix='/exclusion-lists')

TENANT = 'MONOGRAPH'


@exclusion_lists_bp.route('/')
@require_manager
def list_all():
    """All exclusion lists."""
    lists = query_db("""
        SELECT el.id, el.name, el.description, el.item_count,
               el.is_active, el.created_by, el.created_at
        FROM exclusion_list el
        WHERE el.tenant_id = ?
        ORDER BY el.created_at DESC
    """, [TENANT])
    lists = [dict(r) for r in lists]
    return render_template('exclusion_lists/list.html', lists=lists)


@exclusion_lists_bp.route('/<list_id>')
@require_manager
def detail(list_id):
    """View and edit items in an exclusion list."""
    db = get_db()
    excl_list = db.execute(
        "SELECT * FROM exclusion_list WHERE id = ? AND tenant_id = ?",
        [list_id, TENANT]
    ).fetchone()
    if not excl_list:
        flash('Exclusion list not found.', 'error')
        return redirect(url_for('exclusion_lists.list_all'))

    rows = db.execute("""
        SELECT at.area_name, at.area_order,
               ct.category_name, ct.category_order,
               it.id AS template_id, it.item_description, it.item_order,
               CASE WHEN eli.id IS NOT NULL THEN 1 ELSE 0 END AS is_excluded
        FROM item_template it
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        LEFT JOIN exclusion_list_item eli
               ON eli.item_template_id = it.id
              AND eli.exclusion_list_id = ?
        WHERE it.tenant_id = ?
        ORDER BY at.area_order, ct.category_order, it.item_order
    """, [list_id, TENANT]).fetchall()

    # Group by area > category
    areas = {}
    for r in rows:
        an = r['area_name']
        cn = r['category_name']
        if an not in areas:
            areas[an] = {}
        if cn not in areas[an]:
            areas[an][cn] = []
        areas[an][cn].append({
            'template_id': r['template_id'],
            'item_description': r['item_description'],
            'is_excluded': bool(r['is_excluded'])
        })

    return render_template('exclusion_lists/detail.html',
                           excl_list=dict(excl_list),
                           areas=areas)


@exclusion_lists_bp.route('/create', methods=['POST'])
@require_manager
def create():
    """Create a new empty exclusion list."""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('exclusion_lists.list_all'))

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    list_id = generate_id()
    db.execute("""
        INSERT INTO exclusion_list
        (id, tenant_id, name, description, item_count, is_active, created_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, 0, 1, ?, ?, ?)
    """, [list_id, TENANT, name, description, session.get('user_id', 'admin'), now, now])
    db.commit()
    flash('Exclusion list created.', 'success')
    return redirect(url_for('exclusion_lists.detail', list_id=list_id))


@exclusion_lists_bp.route('/<list_id>/clone', methods=['POST'])
@require_manager
def clone(list_id):
    """Clone an existing list with a new name."""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('exclusion_lists.detail', list_id=list_id))

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    new_id = generate_id()

    source = db.execute(
        "SELECT * FROM exclusion_list WHERE id = ? AND tenant_id = ?",
        [list_id, TENANT]
    ).fetchone()
    if not source:
        flash('Source list not found.', 'error')
        return redirect(url_for('exclusion_lists.list_all'))

    db.execute("""
        INSERT INTO exclusion_list
        (id, tenant_id, name, description, item_count, is_active, created_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, 0, 1, ?, ?, ?)
    """, [new_id, TENANT, name, description, session.get('user_id', 'admin'), now, now])

    items = db.execute(
        "SELECT item_template_id, reason FROM exclusion_list_item WHERE exclusion_list_id = ?",
        [list_id]
    ).fetchall()

    for item in items:
        db.execute("""
            INSERT INTO exclusion_list_item
            (id, tenant_id, exclusion_list_id, item_template_id, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [generate_id(), TENANT, new_id, item['item_template_id'], item['reason'], now])

    db.execute(
        "UPDATE exclusion_list SET item_count = ? WHERE id = ?",
        [len(items), new_id]
    )
    db.commit()
    flash(f'List cloned with {len(items)} items.', 'success')
    return redirect(url_for('exclusion_lists.detail', list_id=new_id))


@exclusion_lists_bp.route('/<list_id>/rename', methods=['POST'])
@require_manager
def rename(list_id):
    """Rename an exclusion list."""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('exclusion_lists.detail', list_id=list_id))
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "UPDATE exclusion_list SET name=?, description=?, updated_at=? WHERE id=? AND tenant_id=?",
        [name, description, now, list_id, TENANT]
    )
    db.commit()
    flash('List renamed.', 'success')
    return redirect(url_for('exclusion_lists.detail', list_id=list_id))


@exclusion_lists_bp.route('/<list_id>/toggle-item', methods=['POST'])
@require_manager
def toggle_item(list_id):
    """HTMX: add or remove an item from the list."""
    template_id = request.form.get('template_id')
    action = request.form.get('action')  # 'add' or 'remove'
    if not template_id or action not in ('add', 'remove'):
        return '', 400

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    if action == 'add':
        existing = db.execute(
            "SELECT id FROM exclusion_list_item WHERE exclusion_list_id = ? AND item_template_id = ?",
            [list_id, template_id]
        ).fetchone()
        if not existing:
            db.execute("""
                INSERT INTO exclusion_list_item
                (id, tenant_id, exclusion_list_id, item_template_id, reason, created_at)
                VALUES (?, ?, ?, ?, NULL, ?)
            """, [generate_id(), TENANT, list_id, template_id, now])
    else:
        db.execute(
            "DELETE FROM exclusion_list_item WHERE exclusion_list_id = ? AND item_template_id = ?",
            [list_id, template_id]
        )

    # Update item_count
    count = db.execute(
        "SELECT COUNT(*) FROM exclusion_list_item WHERE exclusion_list_id = ?",
        [list_id]
    ).fetchone()[0]
    db.execute(
        "UPDATE exclusion_list SET item_count = ?, updated_at = ? WHERE id = ?",
        [count, now, list_id]
    )
    db.commit()

    # Return updated checkbox HTML for HTMX swap
    is_excluded = (action == 'add')
    checked = 'checked' if is_excluded else ''
    next_action = 'remove' if is_excluded else 'add'
    return f'''<input type="checkbox" {checked}
        class="h-4 w-4 rounded border-gray-300 text-orange-600 cursor-pointer"
        hx-post="/exclusion-lists/{list_id}/toggle-item"
        hx-vals='{{"template_id": "{template_id}", "action": "{next_action}"}}' 
        hx-target="closest label"
        hx-swap="outerHTML">'''
