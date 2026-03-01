import sys
import os

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
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  OK: [{label}] wrote {filepath}")

print("=== Applying My Reviews Phase 1 ===\n")

# EDIT 1: Replace my_reviews route with batch-grouped version
replace_in_file(
    'app/routes/certification.py',
    '''def my_reviews():
    """Team Lead review queue - submitted inspections awaiting review."""
    tenant_id = session['tenant_id']

    inspections = [dict(r) for r in query_db("""
        SELECT i.id AS inspection_id, i.status AS inspection_status,
               i.submitted_at, i.inspector_name,
               u.id AS unit_id, u.unit_number, u.block, u.floor,
               ic.cycle_number, ic.id AS cycle_id,
               (SELECT COUNT(*) FROM defect d
                WHERE d.unit_id = u.id AND d.raised_cycle_id = ic.id
                AND d.status = 'open' AND d.tenant_id = i.tenant_id) AS defect_count
        FROM inspection i
        JOIN unit u ON i.unit_id = u.id
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.tenant_id = ? AND i.status = 'submitted'
        ORDER BY u.block, u.floor, u.unit_number
    """, [tenant_id])]

    return render_template('certification/my_reviews.html', inspections=inspections)''',
    '''def my_reviews():
    """Team Lead review queue - grouped by batch and zone."""
    tenant_id = session['tenant_id']
    FLOOR_LABELS = {0: 'Ground Floor', 1: '1st Floor', 2: '2nd Floor'}

    # Get all submitted inspections with batch context
    rows = [dict(r) for r in query_db("""
        SELECT i.id AS inspection_id, i.status AS inspection_status,
               i.submitted_at, i.inspector_name,
               u.id AS unit_id, u.unit_number, u.block, u.floor,
               ic.cycle_number, ic.id AS cycle_id,
               ib.id AS batch_id, ib.name AS batch_name, ib.received_date,
               (SELECT COUNT(*) FROM defect d
                WHERE d.unit_id = u.id AND d.raised_cycle_id = ic.id
                AND d.status = 'open' AND d.tenant_id = i.tenant_id) AS defect_count
        FROM inspection i
        JOIN unit u ON i.unit_id = u.id
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        LEFT JOIN batch_unit bu ON bu.unit_id = u.id AND bu.cycle_id = ic.id AND bu.status != 'removed'
        LEFT JOIN inspection_batch ib ON bu.batch_id = ib.id
        WHERE i.tenant_id = ? AND i.status = 'submitted'
        ORDER BY ib.received_date DESC, u.block, u.floor, u.unit_number
    """, [tenant_id])]

    # Also get reviewed counts per cycle for progress
    reviewed_counts = {}
    for r in query_db("""
        SELECT ic.id AS cycle_id, COUNT(*) AS cnt
        FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.tenant_id = ? AND i.status = 'reviewed'
        GROUP BY ic.id
    """, [tenant_id]):
        reviewed_counts[r['cycle_id']] = r['cnt']

    # Group: batch -> zone -> units
    from collections import OrderedDict
    batches = OrderedDict()
    for r in rows:
        bid = r['batch_id'] or 'no_batch'
        bname = r['batch_name'] or 'Unassigned'
        breceived = r['received_date'] or ''

        if bid not in batches:
            batches[bid] = {
                'id': bid,
                'name': bname,
                'received_date': breceived,
                'zones': OrderedDict(),
                'total_units': 0,
                'total_defects': 0,
            }

        zone_key = (r['block'], r['floor'], r['cycle_id'])
        floor_label = FLOOR_LABELS.get(r['floor'], str(r['floor']))
        zone_name = '{} {} C{}'.format(r['block'], floor_label, r['cycle_number'])

        if zone_key not in batches[bid]['zones']:
            batches[bid]['zones'][zone_key] = {
                'name': zone_name,
                'block': r['block'],
                'floor': r['floor'],
                'floor_label': floor_label,
                'cycle_number': r['cycle_number'],
                'cycle_id': r['cycle_id'],
                'units': [],
                'total_defects': 0,
                'reviewed_count': reviewed_counts.get(r['cycle_id'], 0),
            }

        batches[bid]['zones'][zone_key]['units'].append(r)
        batches[bid]['zones'][zone_key]['total_defects'] += r['defect_count']
        batches[bid]['total_units'] += 1
        batches[bid]['total_defects'] += r['defect_count']

    # Convert zones dict to list
    for bid in batches:
        batches[bid]['zones'] = list(batches[bid]['zones'].values())

    total_waiting = len(rows)
    return render_template('certification/my_reviews.html',
                           batches=list(batches.values()),
                           total_waiting=total_waiting)''',
    'my-reviews-route'
)

# EDIT 2: Replace entire template
TEMPLATE = r'''{% extends "base.html" %}

{% block title %}My Reviews{% endblock %}

{% block content %}
<div class="mb-6">
    <h1 class="text-2xl font-bold text-gray-900">My Reviews</h1>
    <p class="text-sm text-gray-500 mt-1">
        {% if total_waiting %}
        {{ total_waiting }} unit{{ 's' if total_waiting != 1 }} waiting for review
        {% else %}
        No units waiting for review
        {% endif %}
    </p>
</div>

{% if batches %}
<div class="space-y-6">
    {% for batch in batches %}
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <!-- Batch header -->
        <div class="px-4 py-3 border-b border-gray-100 bg-gray-50">
            <div class="flex justify-between items-center">
                <div>
                    <h2 class="text-base font-bold text-gray-900">{{ batch.name }}</h2>
                    <p class="text-xs text-gray-500 mt-0.5">
                        {{ batch.total_units }} unit{{ 's' if batch.total_units != 1 }} &middot;
                        {{ batch.total_defects }} defects
                        {% if batch.received_date %} &middot; Received {{ batch.received_date }}{% endif %}
                    </p>
                </div>
            </div>
        </div>

        <!-- Zones -->
        {% for zone in batch.zones %}
        <div class="border-b border-gray-100 last:border-b-0">
            <!-- Zone header -->
            <div class="px-4 py-2.5 bg-gray-50/50 flex justify-between items-center">
                <div class="flex items-center gap-2">
                    <span class="text-sm font-semibold text-gray-700">{{ zone.block }} &middot; {{ zone.floor_label }}</span>
                    {% if zone.cycle_number > 1 %}
                    <span class="text-xs px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 font-semibold">C{{ zone.cycle_number }}</span>
                    {% else %}
                    <span class="text-xs text-gray-400">C{{ zone.cycle_number }}</span>
                    {% endif %}
                </div>
                <div class="flex items-center gap-3">
                    <span class="text-xs text-gray-500">{{ zone.units|length }} to review &middot; {{ zone.total_defects }} defects</span>
                    <span class="text-xs font-medium text-green-600">{{ zone.reviewed_count }} reviewed</span>
                </div>
            </div>

            <!-- Unit rows -->
            <div class="divide-y divide-gray-50">
                {% for insp in zone.units %}
                <div class="px-4 py-2.5 flex items-center justify-between hover:bg-gray-50">
                    <div class="flex items-center gap-3 flex-1 min-w-0">
                        <span class="text-sm font-bold text-gray-800 w-12">{{ insp.unit_number }}</span>
                        <span class="text-xs text-gray-500 truncate">{{ insp.inspector_name }}</span>
                        <span class="text-xs font-medium text-gray-700">{{ insp.defect_count }}</span>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                        <a href="{{ url_for('certification.view_unit', unit_id=insp.unit_id) }}"
                           class="px-3 py-1.5 text-xs font-semibold rounded bg-gray-100 text-gray-700 hover:bg-gray-200">View</a>
                        <form method="POST" action="{{ url_for('certification.review_unit', unit_id=insp.unit_id) }}" class="inline">
                            <button type="submit"
                                    class="px-3 py-1.5 text-xs font-semibold rounded bg-green-600 text-white hover:bg-green-700">Reviewed</button>
                        </form>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endfor %}
    </div>
    {% endfor %}
</div>
{% else %}
<div class="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center">
    <svg class="w-12 h-12 text-green-500 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
    </svg>
    <p class="text-gray-500 text-lg">All caught up!</p>
    <p class="text-gray-400 text-sm mt-1">No units waiting for review</p>
</div>
{% endif %}
{% endblock %}
'''

write_file('app/templates/certification/my_reviews.html', TEMPLATE, 'reviews-template')

print("\n=== ALL EDITS APPLIED ===")
print("Next: git add -A && git commit -m 'My Reviews: batch/zone hierarchy, compact rows, progress counters' && git push")
