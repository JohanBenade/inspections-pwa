"""
Form Restructure v3 - Apply Script
Run from project root: python3 apply_form_restructure.py

Changes:
1. area.html - INST + N/I buttons on categories (equal size grid)
2. inspect.html - Readonly selectors + pill loading
3. inspection.py - Blocked descriptions + submit fix + category cascade NI
"""
import sys

def replace_in_file(path, old, new, label):
    with open(path, 'r') as f:
        content = f.read()
    if old not in content:
        print(f"  FAILED: '{label}' - string not found in {path}")
        print(f"  First 80 chars: {repr(old[:80])}")
        sys.exit(1)
    if content.count(old) > 1:
        print(f"  FAILED: '{label}' - found {content.count(old)} times (need 1)")
        sys.exit(1)
    content = content.replace(old, new)
    with open(path, 'w') as f:
        f.write(content)
    print(f"  OK: {label}")


# ============================================================
# 1. area.html - Category INST + N/I buttons
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
                    onclick="event.stopPropagation();var h=this.closest('.bg-gray-100');var c=h.nextElementSibling;var ch=h.querySelector('.cat-chevron');if(c)c.classList.remove('hidden');if(ch)ch.classList.add('rotate-90')"
                    class="h-8 px-3 rounded-lg text-xs font-bold bg-blue-500 text-white"
                    style="min-width:44px">INST</button>
                <button type="button"
                    hx-post="{{ url_for('inspection.category_cascade_ni', inspection_id=inspection.id, category_id=category.id) }}"
                    hx-vals='{"area_id": "{{ area.id }}"}'
                    hx-target="#area-content"
                    hx-swap="innerHTML"
                    hx-confirm="Mark all items in {{ category.name }} as N/I?"
                    onclick="event.stopPropagation()"
                    class="h-8 px-3 rounded-lg text-xs font-bold bg-amber-500 text-white"
                    style="min-width:44px">N/I</button>
                {% endif %}
            </span>""",
    'Category INST + N/I buttons'
)


# ============================================================
# 2. inspect.html - Readonly + pill loading
# ============================================================
print("\n=== inspect.html ===")

replace_in_file(
    'app/templates/inspection/inspect.html',
    'a[onclick*="inspect-panel"],a[onclick*="defect-expand"],a[onclick*="defect-addmore"],input.auto-caps',
    'a[onclick*="step1"],a[onclick*="step2"],a[onclick*="nts-input"],a[onclick*="nts-area"],a[onclick*="child-btns"],a[onclick*="defect-expand"],a[onclick*="defect-addmore"],a[onclick*="r2-expand"],input.auto-caps',
    'Readonly selectors'
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
    'Pill loading for loadPills triggers'
)


# ============================================================
# 3. inspection.py - Backend changes
# ============================================================
print("\n=== inspection.py ===")

# 3a. BLOCKED_DESCRIPTIONS constant
replace_in_file(
    'app/routes/inspection.py',
    "inspection_bp = Blueprint('inspection', __name__, url_prefix='/inspection')",
    """BLOCKED_DESCRIPTIONS = {
    'defect noted', 'n/a', 'na', 'not applicable',
    'not tested', 'to be tested', 'to be inspected',
    'as indicated', 'not applicable yet', ''
}

inspection_bp = Blueprint('inspection', __name__, url_prefix='/inspection')""",
    'BLOCKED_DESCRIPTIONS constant'
)

# 3b. Block placeholders in add_defect (server-side backup)
replace_in_file(
    'app/routes/inspection.py',
    """        description = description[0].upper() + description[1:]

        # Lock: no edits after sign-off
    if inspection['status'] in ('pending_followup', 'approved', 'certified'):""",
    """        description = description[0].upper() + description[1:]

    # Block placeholder descriptions (server-side backup for client validation)
    if description.lower().strip() in BLOCKED_DESCRIPTIONS:
        if area_id:
            html = _render_single_item(inspection_id, item_id, tenant_id, area_id, force_expanded=True)
            return make_response(html)
        return '', 204

    # Lock: no edits after sign-off
    if inspection['status'] in ('pending_followup', 'approved', 'certified'):""",
    'Block placeholders in add_defect'
)

# 3c. Fix submit fallback for NI items
replace_in_file(
    'app/routes/inspection.py',
    """        elif not item_defects:
            item_defects = [{'description': 'Defect noted', 'defect_type': item['status']}]""",
    """        elif not item_defects:
            if item['status'] == 'not_installed':
                item_defects = [{'description': 'Not installed', 'defect_type': item['status']}]
            else:
                item_defects = [{'description': 'Defect noted - needs review', 'defect_type': item['status']}]""",
    'Submit fallback NI fix'
)

# 3d. Filter blocked descriptions from pill suggestions
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
    'Filter blocked pills'
)

# 3e. Category cascade NI route
replace_in_file(
    'app/routes/inspection.py',
    """@inspection_bp.route('/suggestions/<item_template_id>')
@require_auth
def get_defect_suggestions(item_template_id):""",
    """@inspection_bp.route('/<inspection_id>/category/<category_id>/cascade-ni', methods=['POST'])
@require_auth
def category_cascade_ni(inspection_id, category_id):
    \"\"\"Mark all items in a category as N/I.\"\"\"
    tenant_id = session['tenant_id']
    db = get_db()
    area_id = request.form.get('area_id')

    inspection = query_db(
        "SELECT * FROM inspection WHERE id = ? AND tenant_id = ?",
        [inspection_id, tenant_id], one=True)
    if not inspection:
        abort(404)
    if inspection['status'] in ('pending_followup', 'approved', 'certified'):
        abort(403)

    now = datetime.now(timezone.utc).isoformat()

    items = query_db(\"\"\"
        SELECT ii.id FROM inspection_item ii
        JOIN item_template it ON ii.item_template_id = it.id
        WHERE it.category_id = ? AND ii.inspection_id = ? AND ii.status != 'skipped'
    \"\"\", [category_id, inspection_id])

    for item in (items or []):
        db.execute("UPDATE inspection_item SET status='not_installed', marked_at=? WHERE id=?",
                   [now, item['id']])
        db.execute("DELETE FROM inspection_defect WHERE inspection_item_id=?", [item['id']])

    if inspection['status'] == 'not_started':
        db.execute("UPDATE inspection SET status='in_progress', started_at=?, updated_at=? WHERE id=?",
                   [now, now, inspection_id])

    db.commit()

    if area_id:
        return redirect(url_for('inspection.inspect_area',
                                inspection_id=inspection_id, area_id=area_id))
    return '', 204


@inspection_bp.route('/suggestions/<item_template_id>')
@require_auth
def get_defect_suggestions(item_template_id):""",
    'Category cascade NI route'
)


print("\n=== ALL CHANGES APPLIED ===")
print("\nVerify:")
print("  grep -c 'h-11\\|h-8' app/templates/inspection/_single_item.html")
print("  grep -c 'BLOCKED_DESCRIPTIONS' app/routes/inspection.py")
print("  grep -c 'category_cascade_ni' app/routes/inspection.py")
