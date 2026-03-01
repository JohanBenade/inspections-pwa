import sys

def replace_in_file(filepath, old, new, label):
    with open(filepath, 'r') as f:
        content = f.read()
    count = content.count(old)
    if count == 0:
        print(f"  FAIL: [{label}] old string not found in {filepath}")
        sys.exit(1)
    if count > 1:
        print(f"  FAIL: [{label}] old string found {count} times (expected 1)")
        sys.exit(1)
    content = content.replace(old, new)
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  OK: [{label}] {filepath}")

def write_file(filepath, content, label):
    import os
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  OK: [{label}] wrote {filepath}")

print("=== Applying Batch Edit redesign ===\n")

# EDIT 1: Route - replace entire edit_batch function
replace_in_file(
    'app/routes/batches.py',
    '''def edit_batch(batch_id):
    """Edit batch name, notes, exclusion notes."""
    tenant_id = session['tenant_id']

    batch = query_db(
        'SELECT * FROM inspection_batch WHERE id = ? AND tenant_id = ?',
        [batch_id, tenant_id], one=True)
    if not batch:
        abort(404)
    batch = dict(batch)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        notes_raw = request.form.get('notes', '').strip()
        notes = bleach.clean(notes_raw, tags=ALLOWED_TAGS, strip=True) if notes_raw else None
        exclusion_notes_raw = request.form.get('exclusion_notes', '').strip()
        exclusion_notes = bleach.clean(exclusion_notes_raw, tags=ALLOWED_TAGS, strip=True) if exclusion_notes_raw else None

        if not name:
            flash('Batch name is required.', 'error')
            return render_template('batches/edit.html', batch=batch)

        now = datetime.now(timezone.utc).isoformat()
        get_db().execute(
            'UPDATE inspection_batch SET name = ?, notes = ?, exclusion_notes = ?, updated_at = ? WHERE id = ? AND tenant_id = ?',
            [name, notes, exclusion_notes, now, batch_id, tenant_id])
        get_db().commit()
        flash('Batch updated.', 'success')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    return render_template('batches/edit.html', batch=batch)''',
    '''def edit_batch(batch_id):
    """Edit batch name, received_date, notes. Show audit trail."""
    tenant_id = session['tenant_id']

    batch = query_db(
        'SELECT * FROM inspection_batch WHERE id = ? AND tenant_id = ?',
        [batch_id, tenant_id], one=True)
    if not batch:
        abort(404)
    batch = dict(batch)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        received_date = request.form.get('received_date', '').strip() or None
        notes_raw = request.form.get('notes', '').strip()
        notes = bleach.clean(notes_raw, tags=ALLOWED_TAGS, strip=True) if notes_raw else None

        if not name:
            flash('Batch name is required.', 'error')
            return render_template('batches/edit.html', batch=batch, milestones={})

        now = datetime.now(timezone.utc).isoformat()
        get_db().execute(
            'UPDATE inspection_batch SET name = ?, received_date = ?, notes = ?, updated_at = ? WHERE id = ? AND tenant_id = ?',
            [name, received_date, notes, now, batch_id, tenant_id])
        get_db().commit()
        flash('Batch updated.', 'success')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    # Build audit trail milestones
    batch_started_row = query_db("""
        SELECT MIN(ii.marked_at) AS first_mark
        FROM inspection_item ii
        JOIN inspection i ON ii.inspection_id = i.id
        JOIN batch_unit bu ON bu.unit_id = i.unit_id AND bu.cycle_id = i.cycle_id
        WHERE bu.batch_id = ? AND bu.tenant_id = ?
        AND ii.marked_at IS NOT NULL AND ii.status NOT IN ('pending', 'skipped')
    """, [batch_id, tenant_id], one=True)
    batch_started = batch_started_row['first_mark'] if batch_started_row else None

    # Compute duration
    batch_duration = None
    if batch_started and batch.get('submitted_at'):
        try:
            from datetime import datetime as dt2
            s = batch_started.replace('Z', '+00:00')
            e = batch['submitted_at'].replace('Z', '+00:00')
            start_dt = dt2.fromisoformat(s)
            end_dt = dt2.fromisoformat(e)
            diff_secs = (end_dt - start_dt).total_seconds()
            if diff_secs > 0:
                h = int(diff_secs // 3600)
                m = int((diff_secs % 3600) // 60)
                batch_duration = '{}h {:02d}m'.format(h, m)
        except (ValueError, TypeError):
            pass

    milestones = {
        'received': batch.get('received_date'),
        'created': batch.get('created_at', '')[:10] if batch.get('created_at') else None,
        'first_inspection': _format_local_hhmm(batch_started) + ' ' + batch_started[:10] if batch_started else None,
        'submitted': batch.get('submitted_at', '')[:10] if batch.get('submitted_at') else None,
        'reviewed': batch.get('reviewed_at', '')[:10] if batch.get('reviewed_at') else None,
        'approved': batch.get('approved_at', '')[:10] if batch.get('approved_at') else None,
        'signed_off': batch.get('signed_off_at', '')[:10] if batch.get('signed_off_at') else None,
        'pushed': batch.get('pushed_at', '')[:10] if batch.get('pushed_at') else None,
        'closed': batch.get('closed_at', '')[:10] if batch.get('closed_at') else None,
        'duration': batch_duration,
    }

    return render_template('batches/edit.html', batch=batch, milestones=milestones)''',
    'edit-route'
)

# EDIT 2: Replace entire edit.html template
EDIT_TEMPLATE = r'''{% extends "base.html" %}
{% block title %}Edit {{ batch.name }}{% endblock %}

{% block breadcrumb %}
<div class="max-w-7xl mx-auto px-4 pt-3">
    <a href="{{ url_for('batches.detail', batch_id=batch.id) }}" class="text-sm text-gray-500 hover:text-gray-700">&larr; Back to Batch</a>
</div>
{% endblock %}

{% block content %}
<h1 class="text-2xl font-bold text-gray-800 mb-6">Edit Batch</h1>

<link href="https://cdn.quilljs.com/1.3.7/quill.snow.css" rel="stylesheet">

<form method="POST" id="edit-form" class="space-y-6 max-w-2xl">
    <div>
        <label for="name" class="block text-sm font-medium text-gray-700 mb-1">Batch Name</label>
        <input type="text" id="name" name="name" value="{{ batch.name }}"
               class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
               required>
    </div>

    <div>
        <label for="received_date" class="block text-sm font-medium text-gray-700 mb-1">Received Date</label>
        <input type="date" id="received_date" name="received_date" value="{{ batch.received_date or '' }}"
               class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
    </div>

    <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">General Notes</label>
        <div id="notes-editor" class="bg-white rounded-lg" style="min-height:120px;">{{ (batch.notes or '')|safe }}</div>
        <input type="hidden" id="notes-hidden" name="notes">
    </div>

    <div class="flex items-center gap-3 pt-2">
        <button type="submit"
                class="px-4 py-2 text-sm font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-700">
            Save Changes
        </button>
        <a href="{{ url_for('batches.detail', batch_id=batch.id) }}"
           class="px-4 py-2 text-sm font-semibold rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200">
            Cancel
        </a>
    </div>
</form>

<!-- Batch Timeline -->
{% if milestones %}
<div class="mt-8 max-w-2xl">
    <h2 class="text-lg font-semibold text-gray-800 mb-4">Batch Timeline</h2>

    {% if milestones.duration %}
    <div class="mb-4 px-4 py-3 bg-gray-800 rounded-lg">
        <span class="text-sm text-gray-400">Batch Duration</span>
        <span class="ml-2 text-lg font-bold text-white font-mono">{{ milestones.duration }}</span>
    </div>
    {% endif %}

    <div class="bg-white rounded-lg border border-gray-200 divide-y divide-gray-100">
        {% set steps = [
            ('Received', milestones.received),
            ('Created', milestones.created),
            ('First Inspection', milestones.first_inspection),
            ('All Submitted', milestones.submitted),
            ('All Reviewed', milestones.reviewed),
            ('All Approved', milestones.approved),
            ('Signed Off', milestones.signed_off),
            ('PDFs Pushed', milestones.pushed),
            ('Closed', milestones.closed),
        ] %}
        {% for label, value in steps %}
        <div class="flex items-center justify-between px-4 py-2.5">
            <span class="text-sm text-gray-600">{{ label }}</span>
            {% if value %}
            <span class="text-sm font-medium text-gray-800">{{ value }}</span>
            {% else %}
            <span class="text-sm text-gray-300">&mdash;</span>
            {% endif %}
        </div>
        {% endfor %}
    </div>
</div>
{% endif %}

<script src="https://cdn.quilljs.com/1.3.7/quill.min.js"></script>
<script>
var toolbarOpts = [
    ['bold', 'italic'],
    [{ 'list': 'ordered'}, { 'list': 'bullet' }]
];

var notesQuill = new Quill('#notes-editor', {
    theme: 'snow',
    modules: { toolbar: toolbarOpts },
    placeholder: 'Optional notes about this batch...'
});

document.getElementById('edit-form').addEventListener('submit', function() {
    var notesHtml = notesQuill.root.innerHTML;
    document.getElementById('notes-hidden').value = (notesHtml === '<p><br></p>') ? '' : notesHtml;
});
</script>

<style>
.ql-toolbar.ql-snow { border-radius: 0.5rem 0.5rem 0 0; border-color: #d1d5db; }
.ql-container.ql-snow { border-radius: 0 0 0.5rem 0.5rem; border-color: #d1d5db; font-size: 0.875rem; }
.ql-editor { min-height: 100px; }
</style>
{% endblock %}
'''

write_file('app/templates/batches/edit.html', EDIT_TEMPLATE, 'edit-template')

print("\n=== ALL EDITS APPLIED ===")
print("Next: git add -A && git commit -m 'Batch edit: received_date picker, audit timeline, cleanup orphaned exclusion JS' && git push")
