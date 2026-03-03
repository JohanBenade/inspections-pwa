"""
Form Restructure - Apply all changes.
Run from project root on MacBook:
  python3 apply_form_restructure.py

Changes:
1. _single_item.html - FULL REPLACE (copy separately)
2. area.html - Add category N/I button
3. inspect.html - Update readonly enforcement + afterSettle pill loading
4. inspection.py - Placeholder blocking + submit fix + category cascade NI route
"""
import sys, os

def replace_in_file(path, old, new, label):
    with open(path, 'r') as f:
        content = f.read()
    if old not in content:
        print(f"  FAILED: '{label}' - old string not found in {path}")
        print(f"  First 80 chars of old: {repr(old[:80])}")
        sys.exit(1)
    if content.count(old) > 1:
        print(f"  FAILED: '{label}' - old string found {content.count(old)} times (expected 1) in {path}")
        sys.exit(1)
    content = content.replace(old, new)
    with open(path, 'w') as f:
        f.write(content)
    print(f"  OK: {label}")


# ============================================================
# 1. area.html - Add category N/I button to header
# ============================================================
print("\n=== area.html ===")

replace_in_file(
    'app/templates/inspection/area.html',
    """            <span class="flex items-center gap-2 ml-2 flex-shrink-0">
                {% if ns.active > 0 %}
                <span class="text-xs {% if ns.marked == ns.active %}text-green-600 font-medium{% else %}text-gray-500{% endif %}">
                    {{ ns.marked }}/{{ ns.active }}{% if ns.marked == ns.active %} &#10003;{% endif %}
                </span>
                {% endif %}

            </span>""",
    """            <span class="flex items-center gap-2 ml-2 flex-shrink-0">
                {% if ns.active > 0 %}
                <span class="text-xs {% if ns.marked == ns.active %}text-green-600 font-medium{% else %}text-gray-500{% endif %}">
                    {{ ns.marked }}/{{ ns.active }}{% if ns.marked == ns.active %} &#10003;{% endif %}
                </span>
                {% endif %}
                {% if ns.marked < ns.active %}
                <button type="button"
                    hx-post="{{ url_for('inspection.category_cascade_ni', inspection_id=inspection.id, category_id=category.id) }}"
                    hx-vals='{"area_id": "{{ area.id }}"}'
                    hx-target="#area-content"
                    hx-swap="innerHTML"
                    hx-confirm="Mark all items in {{ category.name }} as N/I?"
                    onclick="event.stopPropagation()"
                    class="px-2 py-1 rounded text-xs font-medium bg-yellow-100 text-yellow-700 hover:bg-yellow-200 transition-colors"
                    style="min-height:32px">N/I</button>
                {% endif %}
            </span>""",
    'Category N/I button'
)


# ============================================================
# 2. inspect.html - Update readonly enforcement + pill loading
# ============================================================
print("\n=== inspect.html ===")

replace_in_file(
    'app/templates/inspection/inspect.html',
    'a[onclick*="inspect-panel"],a[onclick*="defect-expand"],a[onclick*="defect-addmore"],input.auto-caps',
    'a[onclick*="inspect-panel"],a[onclick*="inst-panel"],a[onclick*="nts-input"],a[onclick*="defect-expand"],a[onclick*="defect-addmore"],input.auto-caps',
    'Readonly enforcement update'
)

replace_in_file(
    'app/templates/inspection/inspect.html',
    """            if (target.id && target.id.indexOf('item-') === 0) {
                target.querySelectorAll('[hx-trigger="load"]').forEach(function(el) {
                    if (!el.dataset.pillsLoaded) {
                        el.dataset.pillsLoaded = '1';
                        var url = el.getAttribute('hx-get');
                        if (url) htmx.ajax('GET', url, {target: el, swap: 'innerHTML'});
                    }
                });
            }""",
    """            if (target.id && target.id.indexOf('item-') === 0) {
                target.querySelectorAll('[hx-trigger="load"]').forEach(function(el) {
                    if (!el.dataset.pillsLoaded) {
                        el.dataset.pillsLoaded = '1';
                        var url = el.getAttribute('hx-get');
                        if (url) htmx.ajax('GET', url, {target: el, swap: 'innerHTML'});
                    }
                });
                target.querySelectorAll('[hx-trigger="loadPills once"]').forEach(function(el) {
                    if (!el.dataset.loaded) {
                        el.dataset.loaded = '1';
                        htmx.trigger(el, 'loadPills');
                    }
                });
            }""",
    'afterSettle pill loading for inst-panel'
)


# ============================================================
# 3. inspection.py - All backend changes
# ============================================================
print("\n=== inspection.py ===")

# 3a. Add BLOCKED_DESCRIPTIONS constant after blueprint line
replace_in_file(
    'app/routes/inspection.py',
    "inspection_bp = Blueprint('inspection', __name__, url_prefix='/inspection')",
    """BLOCKED_DESCRIPTIONS = {
    'defect noted', 'n/a', 'na', 'not applicable',
    'not tested', 'to be tested', 'to be inspected',
    'as indicated', 'not applicable yet', ''
}

inspection_bp = Blueprint('inspection', __name__, url_prefix='/inspection')""",
    'Add BLOCKED_DESCRIPTIONS constant'
)

# 3b. Block placeholders in add_defect
replace_in_file(
    'app/routes/inspection.py',
    """        description = description[0].upper() + description[1:]

        # Lock: no edits after sign-off
    if inspection['status'] in ('pending_followup', 'approved', 'certified'):""",
    """        description = description[0].upper() + description[1:]

    # Block placeholder descriptions
    if description.lower().strip() in BLOCKED_DESCRIPTIONS:
        if area_id:
            html = _render_single_item(inspection_id, item_id, tenant_id, area_id, force_expanded=True)
            response = make_response(html)
            response.headers['HX-Trigger'] = 'areaUpdated'
            return response
        return '', 204

    # Lock: no edits after sign-off
    if inspection['status'] in ('pending_followup', 'approved', 'certified'):""",
    'Block placeholders in add_defect'
)

# 3c. Fix submit fallback
replace_in_file(
    'app/routes/inspection.py',
    """        elif not item_defects:
            item_defects = [{'description': 'Defect noted', 'defect_type': item['status']}]""",
    """        elif not item_defects:
            if item['status'] == 'not_installed':
                item_defects = [{'description': 'Not installed', 'defect_type': item['status']}]
            else:
                item_defects = [{'description': 'Defect noted - needs review', 'defect_type': item['status']}]""",
    'Fix submit fallback for NI items'
)

# 3d. Block placeholder suggestions from defect library
replace_in_file(
    'app/routes/inspection.py',
    """    if not suggestions:
        return ''

    # Filter out open prior defect descriptions""",
    """    if not suggestions:
        return ''

    # Filter out blocked placeholder descriptions
    suggestions = [s for s in suggestions if s['description'].lower() not in BLOCKED_DESCRIPTIONS]
    if not suggestions:
        return ''

    # Filter out open prior defect descriptions""",
    'Block placeholder suggestions from pills'
)

# 3e. Add category cascade NI route before suggestions route
replace_in_file(
    'app/routes/inspection.py',
    """@inspection_bp.route('/suggestions/<item_template_id>')
@require_auth
def get_defect_suggestions(item_template_id):""",
    """@inspection_bp.route('/<inspection_id>/category/<category_id>/cascade-ni', methods=['POST'])
@require_auth
def category_cascade_ni(inspection_id, category_id):
    \"\"\"Mark all items in a category as N/I. HTMX endpoint.\"\"\"
    tenant_id = session['tenant_id']
    db = get_db()
    area_id = request.form.get('area_id')

    inspection = query_db(
        "SELECT * FROM inspection WHERE id = ? AND tenant_id = ?",
        [inspection_id, tenant_id], one=True
    )
    if not inspection:
        abort(404)

    # Lock: no edits after sign-off
    if inspection['status'] in ('pending_followup', 'approved', 'certified'):
        abort(403)

    now = datetime.now(timezone.utc).isoformat()

    # Get all non-skipped items in this category for this inspection
    items = query_db(\"\"\"
        SELECT ii.id, ii.status, it.id as template_id
        FROM inspection_item ii
        JOIN item_template it ON ii.item_template_id = it.id
        WHERE it.category_id = ? AND ii.inspection_id = ? AND ii.status != 'skipped'
    \"\"\", [category_id, inspection_id])

    count = 0
    for item in (items or []):
        db.execute(\"\"\"
            UPDATE inspection_item SET status = 'not_installed', marked_at = ?
            WHERE id = ?
        \"\"\", [now, item['id']])
        # Delete any existing inspection_defect chips for this item
        db.execute("DELETE FROM inspection_defect WHERE inspection_item_id = ?", [item['id']])
        count += 1

    # Auto-transition inspection from not_started to in_progress
    if inspection['status'] == 'not_started':
        db.execute(\"\"\"
            UPDATE inspection SET status = 'in_progress', started_at = ?, updated_at = ?
            WHERE id = ?
        \"\"\", [now, now, inspection_id])

    db.commit()

    if area_id:
        return redirect(url_for('inspection.inspect_area',
                                inspection_id=inspection_id, area_id=area_id))
    return '', 204


@inspection_bp.route('/suggestions/<item_template_id>')
@require_auth
def get_defect_suggestions(item_template_id):""",
    'Add category cascade NI route'
)


print("\n=== ALL CHANGES APPLIED SUCCESSFULLY ===")
print()
print("Verify with:")
print("  grep -n 'BLOCKED_DESCRIPTIONS' app/routes/inspection.py | head -5")
print("  grep -n 'category_cascade_ni' app/routes/inspection.py | head -5")
print("  grep -n 'inst-panel' app/templates/inspection/_single_item.html | head -5")
print("  grep -n 'cascade-ni' app/templates/inspection/area.html | head -5")
