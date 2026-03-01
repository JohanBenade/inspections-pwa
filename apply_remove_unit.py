"""
Apply all edits for "Remove Unit from Batch" feature.
Run from project root on MacBook: python3 apply_remove_unit.py
"""
import os
import sys

def replace_in_file(filepath, old, new, label):
    """Replace exact string in file. Abort if not found or found multiple times."""
    with open(filepath, 'r') as f:
        content = f.read()
    count = content.count(old)
    if count == 0:
        print(f"  FAIL: [{label}] old string not found in {filepath}")
        sys.exit(1)
    if count > 1:
        print(f"  FAIL: [{label}] old string found {count} times in {filepath} (expected 1)")
        sys.exit(1)
    content = content.replace(old, new)
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  OK: [{label}] {filepath}")

def create_file(filepath, content, label):
    """Create a new file."""
    if os.path.exists(filepath):
        print(f"  WARN: [{label}] {filepath} already exists, overwriting")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  OK: [{label}] created {filepath}")

print("=== Applying Remove Unit from Batch edits ===\n")

# EDIT 1: batches.py - Filter removed units from detail query
replace_in_file(
    'app/routes/batches.py',
    '        WHERE bu.batch_id = ? AND bu.tenant_id = ?\n        ORDER BY u.block, u.floor, u.unit_number\n    """, [batch_id, tenant_id])\n    units = [dict(r) for r in units_raw]',
    '        WHERE bu.batch_id = ? AND bu.tenant_id = ?\n        AND bu.status != \'removed\'\n        ORDER BY u.block, u.floor, u.unit_number\n    """, [batch_id, tenant_id])\n    units = [dict(r) for r in units_raw]\n\n    # Removed units (separate section)\n    removed_raw = query_db("""\n        SELECT bu.id AS bu_id, bu.removed_at, bu.removed_by, bu.removed_reason,\n               u.unit_number, u.block, u.floor,\n               ic.cycle_number,\n               COALESCE(insp.name, bu.removed_by) AS removed_by_name\n        FROM batch_unit bu\n        JOIN unit u ON bu.unit_id = u.id\n        JOIN inspection_cycle ic ON bu.cycle_id = ic.id\n        LEFT JOIN inspector insp ON bu.removed_by = insp.id\n        WHERE bu.batch_id = ? AND bu.tenant_id = ?\n        AND bu.status = \'removed\'\n        ORDER BY bu.removed_at DESC\n    """, [batch_id, tenant_id])\n    removed_units = [dict(r) for r in removed_raw]',
    'detail-filter-removed'
)

# EDIT 2: batches.py - Pass removed_units to detail template
replace_in_file(
    'app/routes/batches.py',
    "    return render_template('batches/detail.html',\n                           batch=batch, units=units, inspectors=inspectors,\n                           floor_labels=FLOOR_LABELS, cycle_ids=cycle_ids)",
    "    return render_template('batches/detail.html',\n                           batch=batch, units=units, inspectors=inspectors,\n                           floor_labels=FLOOR_LABELS, cycle_ids=cycle_ids,\n                           removed_units=removed_units)",
    'detail-pass-removed'
)

# EDIT 3: batches.py - Filter removed from live monitor query
replace_in_file(
    'app/routes/batches.py',
    "        WHERE bu.batch_id = ? AND bu.tenant_id = ?\n        ORDER BY u.unit_number",
    "        WHERE bu.batch_id = ? AND bu.tenant_id = ?\n        AND bu.status != 'removed'\n        ORDER BY u.unit_number",
    'live-monitor-filter-removed'
)

# EDIT 4: batches.py - Add remove_confirm + remove_unit routes before LIVE MONITOR
ROUTES = '''
@batches_bp.route('/<batch_id>/remove-confirm/<bu_id>')
@require_team_lead
def remove_confirm(batch_id, bu_id):
    """HTMX partial: inline confirmation strip for removing a unit."""
    tenant_id = session['tenant_id']
    bu = query_db("""
        SELECT bu.id AS bu_id, u.unit_number
        FROM batch_unit bu
        JOIN unit u ON bu.unit_id = u.id
        WHERE bu.id = ? AND bu.batch_id = ? AND bu.tenant_id = ?
    """, [bu_id, batch_id, tenant_id], one=True)
    if not bu:
        abort(404)
    return render_template('batches/_remove_confirm.html',
                           batch_id=batch_id, bu=dict(bu))


@batches_bp.route('/<batch_id>/remove-unit', methods=['POST'])
@require_team_lead
def remove_unit(batch_id):
    """Remove a unit from this batch (not_started/pending/assigned only)."""
    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    bu_id = request.form.get('bu_id')
    reason = request.form.get('reason', '').strip() or None

    if not bu_id:
        return '', 400

    bu = query_db(
        "SELECT * FROM batch_unit WHERE id = ? AND batch_id = ? AND tenant_id = ?",
        [bu_id, batch_id, tenant_id], one=True)
    if not bu:
        abort(404)
    bu = dict(bu)

    # Only allow removal for not-yet-started units
    allowed = ('not_started', 'pending', 'assigned')
    insp = query_db(
        "SELECT id, status FROM inspection WHERE unit_id = ? AND cycle_id = ? AND tenant_id = ?",
        [bu['unit_id'], bu['cycle_id'], tenant_id], one=True)
    insp_status = insp['status'] if insp else 'not_started'

    if bu['status'] not in allowed and insp_status not in ('not_started',):
        flash('Cannot remove a unit that is already in progress.', 'error')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    if bu['status'] == 'removed':
        flash('Unit already removed.', 'error')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    # Get unit number for flash message
    unit = query_db("SELECT unit_number FROM unit WHERE id = ?", [bu['unit_id']], one=True)
    unit_number = unit['unit_number'] if unit else bu['unit_id']

    # Clean up not_started inspection + CUA
    if insp and insp['status'] == 'not_started':
        db.execute("DELETE FROM inspection_item WHERE inspection_id = ?", [insp['id']])
        db.execute("DELETE FROM inspection WHERE id = ?", [insp['id']])
        db.execute(
            "DELETE FROM cycle_unit_assignment WHERE cycle_id = ? AND unit_id = ?",
            [bu['cycle_id'], bu['unit_id']])

    # Mark batch_unit as removed
    db.execute("""
        UPDATE batch_unit
        SET status = 'removed', removed_at = ?, removed_by = ?, removed_reason = ?
        WHERE id = ?
    """, [now, session['user_id'], reason, bu_id])

    log_audit(db, tenant_id, 'batch', batch_id, 'unit_removed',
              new_value=unit_number,
              user_id=session['user_id'], user_name=session['user_name'],
              metadata='{{"unit": "{}", "reason": "{}"}}'.format(
                  unit_number, reason or ''))

    db.commit()

    flash('Unit {} removed from batch.'.format(unit_number), 'success')
    return redirect(url_for('batches.detail', batch_id=batch_id))


'''

replace_in_file(
    'app/routes/batches.py',
    '# ============================================================\n# LIVE MONITOR V2\n# ============================================================',
    ROUTES + '# ============================================================\n# LIVE MONITOR V2\n# ============================================================',
    'add-remove-routes'
)

# EDIT 5: detail.html - Add id to tr for HTMX target
replace_in_file(
    'app/templates/batches/detail.html',
    '            {% for u in units %}\n            <tr class="hover:bg-gray-50">',
    '            {% for u in units %}\n            <tr id="row-{{ u.bu_id }}" class="hover:bg-gray-50">',
    'detail-row-id'
)

# EDIT 6: detail.html - Add remove column header
replace_in_file(
    'app/templates/batches/detail.html',
    '                <th class="px-4 py-3 text-left font-medium text-gray-600">Inspector</th>\n            </tr>',
    '                <th class="px-4 py-3 text-left font-medium text-gray-600">Inspector</th>\n                <th class="px-4 py-3 w-8"></th>\n            </tr>',
    'detail-header-col'
)

# EDIT 7: detail.html - Add remove button after inspector cell
replace_in_file(
    'app/templates/batches/detail.html',
    """                    </span>
                </td>
            </tr>
            {% endfor %}""",
    """                    </span>
                </td>
                <td class="px-4 py-2 text-center">
                    {% if batch.status in ('open', 'in_progress') and u.bu_status in ('not_started', 'pending', 'assigned') %}
                    <button type="button"
                            class="text-red-400 hover:text-red-600 text-lg leading-none px-2 py-1"
                            title="Remove from batch"
                            hx-get="{{ url_for('batches.remove_confirm', batch_id=batch.id, bu_id=u.bu_id) }}"
                            hx-target="#row-{{ u.bu_id }}"
                            hx-swap="outerHTML">&times;</button>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}""",
    'detail-remove-btn'
)

# EDIT 8: detail.html - Add removed section at bottom
replace_in_file(
    'app/templates/batches/detail.html',
    """    <a href="{{ url_for('batches.list_batches') }}"
{% endblock %}""",
    """{% if removed_units %}
<div class="mt-6 bg-gray-50 rounded-lg border border-gray-200 p-4">
    <h3 class="text-sm font-semibold text-gray-500 mb-3">Removed ({{ removed_units|length }})</h3>
    {% for ru in removed_units %}
    <div class="flex items-center justify-between py-2 {% if not loop.last %}border-b border-gray-100{% endif %}">
        <div>
            <span class="text-sm text-gray-400 line-through">Unit {{ ru.unit_number }}</span>
            <span class="text-xs text-gray-400 ml-2">{{ ru.block }} {{ floor_labels.get(ru.floor, ru.floor) }} C{{ ru.cycle_number }}</span>
        </div>
        <div class="text-xs text-gray-400 text-right">
            {% if ru.removed_reason %}{{ ru.removed_reason }} &middot; {% endif %}
            {{ ru.removed_by_name or 'Unknown' }} &middot; {{ ru.removed_at[:10] if ru.removed_at else '' }}
        </div>
    </div>
    {% endfor %}
</div>
{% endif %}

    <a href="{{ url_for('batches.list_batches') }}"
{% endblock %}""",
    'detail-removed-section'
)

# CREATE: _remove_confirm.html partial
CONFIRM_TEMPLATE = '''<tr id="row-{{ bu.bu_id }}" class="bg-red-50">
    <td colspan="6" class="px-4 py-3">
        <form method="POST" action="{{ url_for('batches.remove_unit', batch_id=batch_id) }}">
            <input type="hidden" name="bu_id" value="{{ bu.bu_id }}">
            <div class="flex items-center gap-3 flex-wrap">
                <span class="text-sm font-medium text-red-700">Remove Unit {{ bu.unit_number }}?</span>
                <input type="text" name="reason" placeholder="Reason (optional)"
                       class="text-sm border border-gray-300 rounded px-2 py-1.5 flex-1 min-w-[140px]">
                <button type="submit"
                        class="px-3 py-1.5 text-xs font-semibold rounded bg-red-600 text-white hover:bg-red-700">Remove</button>
                <a href="{{ url_for('batches.detail', batch_id=batch_id) }}"
                   class="text-xs text-gray-500 hover:text-gray-700">Cancel</a>
            </div>
        </form>
    </td>
</tr>
'''

create_file(
    'app/templates/batches/_remove_confirm.html',
    CONFIRM_TEMPLATE,
    'remove-confirm-partial'
)

print("\n=== ALL EDITS APPLIED ===")
print("Next: git add -A && git commit -m 'Remove unit from batch: route, HTMX confirm, audit trail' && git push")
