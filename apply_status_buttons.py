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

print("=== Applying status-aware buttons ===\n")

OLD = """    {% if batch.status == 'open' %}
    <a href="{{ url_for('batches.edit_batch', batch_id=batch.id) }}" class="px-3 py-1.5 text-xs font-semibold rounded bg-blue-50 text-blue-600 border border-blue-200 hover:bg-blue-100 mr-2">Edit</a>
    <a href="{{ url_for('batches.exclusions', batch_id=batch.id) }}" class="px-3 py-1.5 text-xs font-semibold rounded bg-orange-50 text-orange-600 border border-orange-200 hover:bg-orange-100 mr-2">Manage Exclusions</a>
    <a href="{{ url_for('batches.live_monitor', batch_id=batch.id) }}" class="px-3 py-1.5 text-xs font-semibold rounded bg-gray-800 text-amber-400 hover:bg-gray-700 mr-2">Live Monitor</a>
    <form method="POST" action="{{ url_for('batches.toggle_lock', batch_id=batch.id) }}" class="inline mr-2">
        {% if batch.locked %}
        <button type="submit" class="px-3 py-1.5 text-xs font-semibold rounded bg-red-50 text-red-600 border border-red-200 hover:bg-red-100">Unlock Batch</button>
        {% else %}
        <button type="submit" class="px-3 py-1.5 text-xs font-semibold rounded bg-gray-50 text-gray-600 border border-gray-200 hover:bg-gray-100">Lock Batch</button>
        {% endif %}
    </form>
    <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-600">Open</span>
    {% elif batch.status == 'in_progress' %}
    <a href="{{ url_for('batches.edit_batch', batch_id=batch.id) }}" class="px-3 py-1.5 text-xs font-semibold rounded bg-blue-50 text-blue-600 border border-blue-200 hover:bg-blue-100 mr-2">Edit</a>
    <a href="{{ url_for('batches.exclusions', batch_id=batch.id) }}" class="px-3 py-1.5 text-xs font-semibold rounded bg-orange-50 text-orange-600 border border-orange-200 hover:bg-orange-100 mr-2">Manage Exclusions</a>
    <a href="{{ url_for('batches.live_monitor', batch_id=batch.id) }}" class="px-3 py-1.5 text-xs font-semibold rounded bg-gray-800 text-amber-400 hover:bg-gray-700 mr-2">Live Monitor</a>
    <form method="POST" action="{{ url_for('batches.toggle_lock', batch_id=batch.id) }}" class="inline mr-2">
        {% if batch.locked %}
        <button type="submit" class="px-3 py-1.5 text-xs font-semibold rounded bg-red-50 text-red-600 border border-red-200 hover:bg-red-100">Unlock Batch</button>
        {% else %}
        <button type="submit" class="px-3 py-1.5 text-xs font-semibold rounded bg-gray-50 text-gray-600 border border-gray-200 hover:bg-gray-100">Lock Batch</button>
        {% endif %}
    </form>
    <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-700">In Progress</span>
    {% elif batch.status == 'review' %}
    <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-purple-100 text-purple-700">Review</span>
    {% elif batch.status == 'complete' %}
    <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-700">Complete</span>
    {% endif %}"""

NEW = """    {%- set s = batch.status -%}

    {%- if s not in ('complete',) %}
    <a href="{{ url_for('batches.edit_batch', batch_id=batch.id) }}" class="px-3 py-1.5 text-xs font-semibold rounded bg-blue-50 text-blue-600 border border-blue-200 hover:bg-blue-100 mr-2">Edit</a>
    {%- endif %}

    {%- if s in ('open', 'in_progress') %}
    <a href="{{ url_for('batches.exclusions', batch_id=batch.id) }}" class="px-3 py-1.5 text-xs font-semibold rounded bg-orange-50 text-orange-600 border border-orange-200 hover:bg-orange-100 mr-2">Manage Exclusions</a>
    {%- endif %}

    {%- if s in ('open', 'in_progress', 'submitted', 'review', 'approved') %}
    <a href="{{ url_for('batches.live_monitor', batch_id=batch.id) }}" class="px-3 py-1.5 text-xs font-semibold rounded bg-gray-800 text-amber-400 hover:bg-gray-700 mr-2">Live Monitor</a>
    {%- endif %}

    {%- if s in ('open', 'in_progress') %}
    <form method="POST" action="{{ url_for('batches.toggle_lock', batch_id=batch.id) }}" class="inline mr-2">
        {% if batch.locked %}
        <button type="submit" class="px-3 py-1.5 text-xs font-semibold rounded bg-red-50 text-red-600 border border-red-200 hover:bg-red-100">Unlock Batch</button>
        {% else %}
        <button type="submit" class="px-3 py-1.5 text-xs font-semibold rounded bg-gray-50 text-gray-600 border border-gray-200 hover:bg-gray-100">Lock Batch</button>
        {% endif %}
    </form>
    {%- endif %}

    {%- if s == 'open' %}
    <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-600">Open</span>
    {%- elif s == 'in_progress' %}
    <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-700">In Progress</span>
    {%- elif s == 'submitted' %}
    <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-purple-100 text-purple-700">Submitted</span>
    {%- elif s == 'review' %}
    <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-purple-100 text-purple-700">Review</span>
    {%- elif s == 'approved' %}
    <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-indigo-100 text-indigo-700">Approved</span>
    {%- elif s == 'signed_off' %}
    <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-teal-100 text-teal-700">Signed Off</span>
    {%- elif s == 'pushed' %}
    <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-700">Pushed</span>
    {%- elif s == 'complete' %}
    <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-700">Complete</span>
    {%- endif %}"""

replace_in_file('app/templates/batches/detail.html', OLD, NEW, 'status-buttons')

print("\n=== DONE ===")
print("Next: git add -A && git commit -m 'Batch detail: status-aware buttons for all 8 statuses' && git push")
