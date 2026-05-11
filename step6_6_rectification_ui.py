"""
Step 6.6: Latent rectification UI

Changes (2 files, 6 logical changes):
  1. Widen unit_latent GET query: inspection_id -> unit_id (cross-cycle visibility)
  2+3. Widen edit_area_note + delete_area_note note lookups (single replace, 2 occurrences)
  4. Add rectify_area_note + reopen_area_note routes
  5. Add fmt_date Jinja macro at top of template content block
  6. Replace note-card rendering: status badge + state-conditional buttons

Idempotent: detects already-migrated state and exits cleanly.
All asserts run before any file is written -- no partial-state risk.

Run from project root:
    python3 step6_6_rectification_ui.py
"""
import sys

approvals_path = 'app/routes/approvals.py'
template_path = 'app/templates/approvals/unit_latent.html'

with open(approvals_path) as f:
    approvals = f.read()
with open(template_path) as f:
    template = f.read()

# === IDEMPOTENCY CHECK ===
already_in_approvals = 'def rectify_area_note(' in approvals
already_in_template = 'rectified_at_cycle_number' in template

if already_in_approvals and already_in_template:
    print('Already migrated. Both files contain Step 6.6 content. Exiting.')
    sys.exit(0)
elif already_in_approvals or already_in_template:
    print('PARTIAL STATE detected -- one file migrated, the other not.')
    print('  approvals.py migrated: {}'.format(already_in_approvals))
    print('  unit_latent.html migrated: {}'.format(already_in_template))
    print('Manual inspection required. Exiting without changes.')
    sys.exit(1)

# === CHANGE 1: Widen unit_latent GET query ===
old_query = '''    latent_notes = query_db("""
        SELECT n.id, n.note_html, n.area_template_id, n.area_name_override,
               n.created_by, n.created_by_role, n.last_edited_by_role,
               n.created_at, at.area_name, at.area_order
        FROM latent_area_note n
        LEFT JOIN area_template at ON n.area_template_id = at.id
        WHERE n.inspection_id = ? AND n.tenant_id = ?
        ORDER BY at.area_order, n.created_at
    """, [inspection['id'], tenant_id])'''

new_query = '''    latent_notes = query_db("""
        SELECT n.id, n.note_html, n.area_template_id, n.area_name_override,
               n.created_by, n.created_by_role, n.last_edited_by_role,
               n.created_at, n.cycle_number,
               n.rectified_at_cycle_number, n.rectified_at,
               at.area_name, at.area_order
        FROM latent_area_note n
        LEFT JOIN area_template at ON n.area_template_id = at.id
        WHERE n.unit_id = ? AND n.tenant_id = ?
        ORDER BY at.area_order, n.created_at
    """, [unit_id, tenant_id])'''

assert old_query in approvals, "CHANGE 1: unit_latent query not found"

# === CHANGES 2 & 3: Widen edit + delete note lookups (same string in both) ===
old_lookup = '''    # Locate the note (scoped to this inspection + tenant)
    note = query_db("""
        SELECT id, note_html FROM latent_area_note
        WHERE id = ? AND inspection_id = ? AND tenant_id = ?
    """, [note_id, inspection['id'], tenant_id], one=True)'''

new_lookup = '''    # Locate the note (unit-scoped to allow cross-cycle edit/delete)
    note = query_db("""
        SELECT id, note_html FROM latent_area_note
        WHERE id = ? AND unit_id = ? AND tenant_id = ?
    """, [note_id, unit_id, tenant_id], one=True)'''

assert old_lookup in approvals, "CHANGE 2/3: edit/delete note lookup not found"
assert approvals.count(old_lookup) == 2, \
    "CHANGE 2/3: expected exactly 2 occurrences of old lookup, found {}".format(approvals.count(old_lookup))

# === CHANGE 4: Add rectify_area_note + reopen_area_note routes ===
new_routes_anchor = '''    flash('Latent defect note deleted.', 'success')
    return redirect(url_for('approvals.unit_latent',
                            cycle_id=cycle_id, unit_id=unit_id))


@approvals_bp.route('/<cycle_id>/edit-defect', methods=['POST'])
@require_manager
def edit_defect(cycle_id):'''

new_routes_block = '''    flash('Latent defect note deleted.', 'success')
    return redirect(url_for('approvals.unit_latent',
                            cycle_id=cycle_id, unit_id=unit_id))


@approvals_bp.route('/<cycle_id>/unit/<unit_id>/latent/<note_id>/rectify', methods=['POST'])
@require_team_lead_only
def rectify_area_note(cycle_id, unit_id, note_id):
    """Mark a latent area note as rectified (TL desktop, C2+ only).

    Records the current cycle as the rectification cycle on the note.
    Reversible via reopen_area_note. Note lookup is unit-scoped so a TL
    in any cycle can rectify outstanding notes from prior cycles.
    """
    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    # Tenant-scoped unit
    unit = query_db("""
        SELECT id FROM unit
        WHERE id = ? AND tenant_id = ?
    """, [unit_id, tenant_id], one=True)
    if not unit:
        abort(404)

    # Current cycle's inspection (rectification attributes to current cycle)
    inspection = query_db("""
        SELECT id, cycle_number FROM inspection
        WHERE unit_id = ? AND cycle_id = ? AND tenant_id = ?
    """, [unit_id, cycle_id, tenant_id], one=True)
    if not inspection:
        abort(404)

    if inspection['cycle_number'] == 1:
        flash('Latent defects do not apply at C1.', 'warning')
        return redirect(url_for('certification.my_reviews'))

    # Locate the note (unit-scoped, may originate from a prior cycle)
    note = query_db("""
        SELECT id, rectified_at_cycle_number FROM latent_area_note
        WHERE id = ? AND unit_id = ? AND tenant_id = ?
    """, [note_id, unit_id, tenant_id], one=True)
    if not note:
        abort(404)

    if note['rectified_at_cycle_number'] is not None:
        flash('Note is already marked rectified.', 'warning')
        return redirect(url_for('approvals.unit_latent',
                                cycle_id=cycle_id, unit_id=unit_id))

    rectified_by_role = session.get('role', 'inspector')

    db.execute("""
        UPDATE latent_area_note
        SET rectified_at_cycle_id = ?,
            rectified_at_cycle_number = ?,
            rectified_at = ?,
            rectified_by = ?,
            rectified_by_role = ?
        WHERE id = ? AND tenant_id = ?
    """, [cycle_id, inspection['cycle_number'], now,
          session['user_id'], rectified_by_role, note_id, tenant_id])

    log_audit(db, tenant_id, 'latent_area_note', note_id, 'rectified',
              new_value='cycle_number={}; rectified_at={}'.format(
                  inspection['cycle_number'], now),
              user_id=session['user_id'], user_name=session['user_name'])

    db.commit()
    flash('Latent defect marked rectified.', 'success')
    return redirect(url_for('approvals.unit_latent',
                            cycle_id=cycle_id, unit_id=unit_id))


@approvals_bp.route('/<cycle_id>/unit/<unit_id>/latent/<note_id>/reopen', methods=['POST'])
@require_team_lead_only
def reopen_area_note(cycle_id, unit_id, note_id):
    """Re-open a rectified latent area note (TL desktop, C2+ only).

    Clears all 5 rectification columns back to NULL. Reverses rectify_area_note.
    """
    tenant_id = session['tenant_id']
    db = get_db()

    # Tenant-scoped unit
    unit = query_db("""
        SELECT id FROM unit
        WHERE id = ? AND tenant_id = ?
    """, [unit_id, tenant_id], one=True)
    if not unit:
        abort(404)

    # Current cycle's inspection (for C1 guard)
    inspection = query_db("""
        SELECT id, cycle_number FROM inspection
        WHERE unit_id = ? AND cycle_id = ? AND tenant_id = ?
    """, [unit_id, cycle_id, tenant_id], one=True)
    if not inspection:
        abort(404)

    if inspection['cycle_number'] == 1:
        flash('Latent defects do not apply at C1.', 'warning')
        return redirect(url_for('certification.my_reviews'))

    # Locate the note (unit-scoped)
    note = query_db("""
        SELECT id, rectified_at_cycle_number FROM latent_area_note
        WHERE id = ? AND unit_id = ? AND tenant_id = ?
    """, [note_id, unit_id, tenant_id], one=True)
    if not note:
        abort(404)

    if note['rectified_at_cycle_number'] is None:
        flash('Note is not currently rectified.', 'warning')
        return redirect(url_for('approvals.unit_latent',
                                cycle_id=cycle_id, unit_id=unit_id))

    old_cycle_number = note['rectified_at_cycle_number']

    db.execute("""
        UPDATE latent_area_note
        SET rectified_at_cycle_id = NULL,
            rectified_at_cycle_number = NULL,
            rectified_at = NULL,
            rectified_by = NULL,
            rectified_by_role = NULL
        WHERE id = ? AND tenant_id = ?
    """, [note_id, tenant_id])

    log_audit(db, tenant_id, 'latent_area_note', note_id, 'reopened',
              old_value='cycle_number={}'.format(old_cycle_number),
              user_id=session['user_id'], user_name=session['user_name'])

    db.commit()
    flash('Latent defect re-opened.', 'success')
    return redirect(url_for('approvals.unit_latent',
                            cycle_id=cycle_id, unit_id=unit_id))


@approvals_bp.route('/<cycle_id>/edit-defect', methods=['POST'])
@require_manager
def edit_defect(cycle_id):'''

assert new_routes_anchor in approvals, "CHANGE 4: anchor (delete -> edit_defect boundary) not found"

# === CHANGE 5: Add fmt_date Jinja macro at top of content block ===
old_macro_anchor = '''{% block content %}
<!-- Quill rich-text editor styles -->'''

new_macro_anchor = '''{% block content %}
{# Date format helper: ISO timestamp string -> DD.MM.YYYY #}
{% macro fmt_date(iso) %}{{ iso[8:10] }}.{{ iso[5:7] }}.{{ iso[:4] }}{% endmacro %}

<!-- Quill rich-text editor styles -->'''

assert old_macro_anchor in template, "CHANGE 5: content block anchor not found"

# === CHANGE 6: Rewrite note card with badge + state-conditional buttons ===
old_card = '''                <div class="text-sm text-gray-700 latent-note-content">{{ n.note_html|safe }}</div>
                <div class="mt-2 flex justify-end gap-3">
                    <button type="button"
                            class="js-edit-note text-xs text-blue-600 hover:text-blue-800"
                            data-edit-url="{{ url_for('approvals.edit_area_note', cycle_id=cycle_id, unit_id=unit.id, note_id=n.id) }}"
                            data-note-html="{{ n.note_html|e }}">
                        Edit
                    </button>
                    <button type="button"
                            class="js-delete-note text-xs text-red-600 hover:text-red-800"
                            data-delete-url="{{ url_for('approvals.delete_area_note', cycle_id=cycle_id, unit_id=unit.id, note_id=n.id) }}"
                            data-area-name="{{ n.area_name or n.area_name_override }}">
                        Delete
                    </button>
                </div>'''

new_card = '''                <div class="text-sm text-gray-700 latent-note-content">{{ n.note_html|safe }}</div>

                {# Status badge #}
                <div class="mt-2">
                    {% if n.rectified_at_cycle_number %}
                    <span class="inline-block px-2 py-0.5 text-xs rounded bg-green-100 text-green-800">
                        Identified at C{{ n.cycle_number }} ({{ fmt_date(n.created_at) }}) &mdash; Rectified at C{{ n.rectified_at_cycle_number }} ({{ fmt_date(n.rectified_at) }})
                    </span>
                    {% else %}
                    <span class="inline-block px-2 py-0.5 text-xs rounded bg-amber-100 text-amber-800">
                        Identified at C{{ n.cycle_number }} ({{ fmt_date(n.created_at) }}) &mdash; Outstanding
                    </span>
                    {% endif %}
                </div>

                <div class="mt-2 flex justify-end gap-3 items-center">
                    {% if n.rectified_at_cycle_number %}
                    {# Rectified state: Re-open + Delete #}
                    <form method="POST" action="{{ url_for('approvals.reopen_area_note', cycle_id=cycle_id, unit_id=unit.id, note_id=n.id) }}" class="inline">
                        <button type="submit" class="text-xs text-amber-600 hover:text-amber-800">Re-open</button>
                    </form>
                    <button type="button"
                            class="js-delete-note text-xs text-red-600 hover:text-red-800"
                            data-delete-url="{{ url_for('approvals.delete_area_note', cycle_id=cycle_id, unit_id=unit.id, note_id=n.id) }}"
                            data-area-name="{{ n.area_name or n.area_name_override }}">
                        Delete
                    </button>
                    {% else %}
                    {# Outstanding state: Edit + Delete + Mark Rectified #}
                    <button type="button"
                            class="js-edit-note text-xs text-blue-600 hover:text-blue-800"
                            data-edit-url="{{ url_for('approvals.edit_area_note', cycle_id=cycle_id, unit_id=unit.id, note_id=n.id) }}"
                            data-note-html="{{ n.note_html|e }}">
                        Edit
                    </button>
                    <button type="button"
                            class="js-delete-note text-xs text-red-600 hover:text-red-800"
                            data-delete-url="{{ url_for('approvals.delete_area_note', cycle_id=cycle_id, unit_id=unit.id, note_id=n.id) }}"
                            data-area-name="{{ n.area_name or n.area_name_override }}">
                        Delete
                    </button>
                    <form method="POST" action="{{ url_for('approvals.rectify_area_note', cycle_id=cycle_id, unit_id=unit.id, note_id=n.id) }}" class="inline">
                        <button type="submit" class="text-xs text-green-600 hover:text-green-800">Mark Rectified</button>
                    </form>
                    {% endif %}
                </div>'''

assert old_card in template, "CHANGE 6: note card block not found"

# === ALL ASSERTS PASSED -- APPLY ALL CHANGES IN MEMORY ===
approvals = approvals.replace(old_query, new_query)
print('CHANGE 1 applied: unit_latent query widened (inspection_id -> unit_id)')

approvals = approvals.replace(old_lookup, new_lookup)
print('CHANGES 2 & 3 applied: edit + delete note lookups widened (2 occurrences)')

approvals = approvals.replace(new_routes_anchor, new_routes_block)
print('CHANGE 4 applied: rectify_area_note + reopen_area_note routes added')

template = template.replace(old_macro_anchor, new_macro_anchor)
print('CHANGE 5 applied: fmt_date Jinja macro added')

template = template.replace(old_card, new_card)
print('CHANGE 6 applied: note card rewritten with badge + state-conditional buttons')

# === FINAL WRITE ===
with open(approvals_path, 'w') as f:
    f.write(approvals)
with open(template_path, 'w') as f:
    f.write(template)

print()
print('=== STEP 6.6 COMPLETE ===')
print('Files modified:')
print('  ', approvals_path)
print('  ', template_path)
