import os
import py_compile

REPO_ROOT = os.getcwd()
ANALYTICS_PATH = os.path.join(REPO_ROOT, 'app/routes/analytics.py')
TEMPLATE_DIR = os.path.join(REPO_ROOT, 'app/templates/analytics')

NEW_DETAIL_FUNCTION = '''@analytics_bp.route('/<block_slug>/<int:floor>')
@require_manager
def block_floor_detail(block_slug, floor):
    """Block+Floor detail page - unit table, round comparison, area breakdown, top defects."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')
    block = _slug_to_block(block_slug)
    floor_label = FLOOR_LABELS.get(floor, 'Floor {}'.format(floor))
    label = '{} {}'.format(block, floor_label)

    # 1. All cycles for this block+floor
    cycles = [dict(r) for r in query_db("""
        SELECT id, cycle_number
        FROM inspection_cycle
        WHERE block = ? AND floor = ? AND tenant_id = ? AND id NOT LIKE 'test-%'
        ORDER BY cycle_number
    """, [block, floor, tenant_id])]
    cycle_ids = [c['id'] for c in cycles]
    max_round = max((c['cycle_number'] for c in cycles), default=0)

    if not cycle_ids:
        return render_template('analytics/block_floor_detail.html',
                               block=block, floor=floor, label=label,
                               has_data=False, units=[], rounds=[],
                               area_data=[], top_defects=[], summary={})

    # Build cycle_id -> round_number lookup
    cycle_round_map = {c['id']: c['cycle_number'] for c in cycles}

    # 2. Unit status table
    units_raw = [dict(r) for r in query_db("""
        SELECT u.id as unit_id, u.unit_number,
            i.id as inspection_id, i.status as insp_status,
            i.cycle_id, i.inspector_name,
            ic.cycle_number as round_number,
            COUNT(d.id) as defect_count
        FROM unit u
        JOIN inspection i ON i.unit_id = u.id AND i.tenant_id = u.tenant_id
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        LEFT JOIN defect d ON d.unit_id = u.id AND d.raised_cycle_id = i.cycle_id
            AND d.status = 'open' AND d.tenant_id = u.tenant_id
        WHERE u.block = ? AND u.floor = ? AND u.tenant_id = ?
        AND i.cycle_id NOT LIKE 'test-%'
        GROUP BY u.id, i.cycle_id
        ORDER BY u.unit_number, ic.cycle_number
    """, [block, floor, tenant_id])]

    # Keep only the latest round per unit for the table
    unit_latest = {}
    for r in units_raw:
        un = r['unit_number']
        if un not in unit_latest or r['round_number'] > unit_latest[un]['round_number']:
            unit_latest[un] = r

    # Status display mapping
    status_display = {
        'not_started': 'Not Started',
        'in_progress': 'In Progress',
        'submitted': 'Submitted',
        'reviewed': 'Reviewed',
        'pending_followup': 'Signed Off',
        'approved': 'Approved',
        'certified': 'Certified',
        'closed': 'Closed',
    }
    status_colour = {
        'not_started': 'bg-gray-100 text-gray-600',
        'in_progress': 'bg-blue-100 text-blue-700',
        'submitted': 'bg-yellow-100 text-yellow-700',
        'reviewed': 'bg-purple-100 text-purple-700',
        'pending_followup': 'bg-emerald-100 text-emerald-700',
        'approved': 'bg-emerald-100 text-emerald-700',
        'certified': 'bg-emerald-200 text-emerald-800',
        'closed': 'bg-gray-200 text-gray-700',
    }

    units = []
    for un in sorted(unit_latest.keys()):
        r = unit_latest[un]
        units.append({
            'unit_number': un,
            'round_number': r['round_number'],
            'insp_status': r['insp_status'],
            'status_label': status_display.get(r['insp_status'], r['insp_status']),
            'status_colour': status_colour.get(r['insp_status'], 'bg-gray-100 text-gray-600'),
            'defect_count': r['defect_count'],
            'inspector_name': r['inspector_name'] or '-',
        })

    # Summary stats
    total_units = len(units)
    total_defects = sum(u['defect_count'] for u in units)
    avg_defects = round(total_defects / total_units, 1) if total_units > 0 else 0
    items_inspected = ITEMS_PER_UNIT * total_units
    defect_rate = round(total_defects / items_inspected * 100, 1) if items_inspected > 0 else 0
    max_defects_unit = max(units, key=lambda u: u['defect_count']) if units else None

    summary = {
        'total_units': total_units,
        'total_defects': total_defects,
        'avg_defects': avg_defects,
        'defect_rate': defect_rate,
        'max_round': max_round,
        'worst_unit': max_defects_unit['unit_number'] if max_defects_unit else '-',
        'worst_count': max_defects_unit['defect_count'] if max_defects_unit else 0,
    }

    # 3. Round comparison (only if max_round > 1)
    rounds = []
    if max_round > 1:
        rounds_raw = [dict(r) for r in query_db("""
            SELECT ic.cycle_number as round_number,
                COUNT(DISTINCT d.id) as total_defects,
                COUNT(DISTINCT i.unit_id) as units_inspected,
                SUM(CASE WHEN d.status = 'open' THEN 1 ELSE 0 END) as still_open,
                SUM(CASE WHEN d.status = 'cleared' THEN 1 ELSE 0 END) as cleared
            FROM inspection_cycle ic
            JOIN inspection i ON i.cycle_id = ic.id AND i.tenant_id = ic.tenant_id
            LEFT JOIN defect d ON d.raised_cycle_id = ic.id AND d.tenant_id = ic.tenant_id
            WHERE ic.block = ? AND ic.floor = ? AND ic.tenant_id = ?
            AND ic.id NOT LIKE 'test-%'
            GROUP BY ic.cycle_number
            ORDER BY ic.cycle_number
        """, [block, floor, tenant_id])]

        for r in rounds_raw:
            r['avg_defects'] = round(r['total_defects'] / r['units_inspected'], 1) if r['units_inspected'] > 0 else 0
            clearance_base = r['total_defects']
            r['clearance_pct'] = round(r['cleared'] / clearance_base * 100, 1) if clearance_base > 0 else 0
        rounds = rounds_raw

    # 4. Area breakdown (all open defects in this block+floor)
    area_data_raw = [dict(r) for r in query_db("""
        SELECT at2.area_name as area, COUNT(d.id) as defect_count
        FROM defect d
        JOIN unit u ON d.unit_id = u.id
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE u.block = ? AND u.floor = ? AND d.tenant_id = ?
        AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%'
        GROUP BY at2.area_name
        ORDER BY defect_count DESC
    """, [block, floor, tenant_id])]

    max_area_count = area_data_raw[0]['defect_count'] if area_data_raw else 1
    for a in area_data_raw:
        a['bar_pct'] = round(a['defect_count'] / max_area_count * 100)
        a['pct'] = round(a['defect_count'] / total_defects * 100, 1) if total_defects > 0 else 0
        a['colour'] = AREA_COLOURS.get(a['area'], '#9ca3af')

    # 5. Top defect types (scoped to block+floor)
    top_defects = [dict(r) for r in query_db("""
        SELECT d.original_comment as description, COUNT(*) as count
        FROM defect d
        JOIN unit u ON d.unit_id = u.id
        WHERE u.block = ? AND u.floor = ? AND d.tenant_id = ?
        AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%'
        GROUP BY d.original_comment
        ORDER BY count DESC
        LIMIT 10
    """, [block, floor, tenant_id])]

    max_defect_count = top_defects[0]['count'] if top_defects else 1
    for d in top_defects:
        d['bar_pct'] = round(d['count'] / max_defect_count * 100)
        d['pct'] = round(d['count'] / total_defects * 100, 1) if total_defects > 0 else 0

    return render_template('analytics/block_floor_detail.html',
                           block=block, floor=floor, label=label,
                           block_slug=block_slug,
                           has_data=True,
                           units=units,
                           rounds=rounds,
                           area_data=area_data_raw,
                           top_defects=top_defects,
                           summary=summary)
'''

DETAIL_TEMPLATE = r'''{% extends "base.html" %}

{% block title %}{{ label }}{% endblock %}

{% block content %}
<div class="space-y-6">

    <!-- Header + Back -->
    <div>
        <a href="{{ url_for('analytics.dashboard') }}" class="text-primary hover:underline text-sm">&larr; Dashboard</a>
        <h1 class="text-2xl font-bold text-gray-900 mt-1">{{ label }}</h1>
    </div>

    {% if not has_data %}
    <div class="bg-white rounded-lg shadow p-8 text-center text-gray-500">
        No inspection data for this block+floor yet.
    </div>
    {% else %}

    <!-- Summary Cards -->
    <div class="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div class="bg-white rounded-lg shadow p-4">
            <div class="text-2xl font-bold text-gray-900">{{ summary.total_units }}</div>
            <div class="text-xs text-gray-500">units</div>
        </div>
        <div class="bg-white rounded-lg shadow p-4">
            <div class="text-2xl font-bold {% if summary.total_defects > 0 %}text-red-600{% else %}text-emerald-600{% endif %}">{{ summary.total_defects }}</div>
            <div class="text-xs text-gray-500">open defects</div>
        </div>
        <div class="bg-white rounded-lg shadow p-4">
            <div class="text-2xl font-bold text-gray-900">{{ summary.avg_defects }}</div>
            <div class="text-xs text-gray-500">avg per unit</div>
        </div>
        <div class="bg-white rounded-lg shadow p-4">
            <div class="text-2xl font-bold text-gray-900">{{ summary.defect_rate }}%</div>
            <div class="text-xs text-gray-500">defect rate</div>
        </div>
        <div class="bg-white rounded-lg shadow p-4">
            <div class="text-2xl font-bold text-gray-900">R{{ summary.max_round }}</div>
            <div class="text-xs text-gray-500">latest round</div>
        </div>
    </div>

    <!-- Section 1: Unit Status Table -->
    <div class="bg-white rounded-lg shadow overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-100">
            <h2 class="text-lg font-semibold text-gray-900">Unit Status</h2>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead class="bg-gray-50 text-gray-500 text-xs uppercase">
                    <tr>
                        <th class="px-4 py-3 text-left">Unit</th>
                        <th class="px-4 py-3 text-left">Round</th>
                        <th class="px-4 py-3 text-left">Status</th>
                        <th class="px-4 py-3 text-right">Defects</th>
                        <th class="px-4 py-3 text-left hidden sm:table-cell">Inspector</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                    {% for u in units %}
                    <tr class="{% if u.defect_count > 30 %}bg-red-50{% elif u.defect_count <= 20 %}bg-emerald-50{% endif %}">
                        <td class="px-4 py-3 font-medium text-gray-900">{{ u.unit_number }}</td>
                        <td class="px-4 py-3 text-gray-600">{{ u.round_number }}</td>
                        <td class="px-4 py-3">
                            <span class="inline-block text-xs px-2 py-0.5 rounded-full {{ u.status_colour }}">{{ u.status_label }}</span>
                        </td>
                        <td class="px-4 py-3 text-right font-medium {% if u.defect_count > 30 %}text-red-600{% elif u.defect_count <= 20 %}text-emerald-600{% else %}text-gray-900{% endif %}">{{ u.defect_count }}</td>
                        <td class="px-4 py-3 text-gray-500 hidden sm:table-cell">{{ u.inspector_name }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- Section 2: Round Comparison (conditional) -->
    {% if rounds|length > 1 %}
    <div class="bg-white rounded-lg shadow overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-100">
            <h2 class="text-lg font-semibold text-gray-900">Round Comparison</h2>
        </div>
        <div class="p-5">
            <div class="grid grid-cols-1 sm:grid-cols-{{ rounds|length }} gap-4">
                {% for r in rounds %}
                <div class="p-4 rounded-lg {% if loop.last %}bg-blue-50 border border-blue-200{% else %}bg-gray-50{% endif %}">
                    <div class="text-sm font-semibold text-gray-500 uppercase mb-3">Round {{ r.round_number }}</div>
                    <div class="space-y-2">
                        <div class="flex justify-between text-sm">
                            <span class="text-gray-600">Units inspected</span>
                            <span class="font-medium text-gray-900">{{ r.units_inspected }}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span class="text-gray-600">Defects raised</span>
                            <span class="font-medium text-gray-900">{{ r.total_defects }}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span class="text-gray-600">Still open</span>
                            <span class="font-medium {% if r.still_open > 0 %}text-red-600{% else %}text-emerald-600{% endif %}">{{ r.still_open }}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span class="text-gray-600">Cleared</span>
                            <span class="font-medium text-emerald-600">{{ r.cleared }}</span>
                        </div>
                        {% if r.cleared > 0 or r.total_defects > 0 %}
                        <div class="flex justify-between text-sm pt-2 border-t border-gray-200">
                            <span class="text-gray-600">Clearance rate</span>
                            <span class="font-medium {% if r.clearance_pct >= 50 %}text-emerald-600{% else %}text-amber-600{% endif %}">{{ r.clearance_pct }}%</span>
                        </div>
                        {% endif %}
                        <div class="flex justify-between text-sm">
                            <span class="text-gray-600">Avg per unit</span>
                            <span class="font-medium text-gray-900">{{ r.avg_defects }}</span>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
    {% endif %}

    <!-- Section 3: Area Breakdown -->
    {% if area_data %}
    <div class="bg-white rounded-lg shadow overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-100">
            <h2 class="text-lg font-semibold text-gray-900">Defects by Area</h2>
        </div>
        <div class="p-5 space-y-3">
            {% for a in area_data %}
            <div>
                <div class="flex items-center justify-between text-sm mb-1">
                    <span class="text-gray-700 font-medium">{{ a.area }}</span>
                    <span class="text-gray-500">{{ a.defect_count }} ({{ a.pct }}%)</span>
                </div>
                <div class="w-full bg-gray-100 rounded-full h-4">
                    <div class="h-4 rounded-full" style="width: {{ a.bar_pct }}%; background-color: {{ a.colour }};"></div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    {% endif %}

    <!-- Section 4: Top Defect Types -->
    {% if top_defects %}
    <div class="bg-white rounded-lg shadow overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-100">
            <h2 class="text-lg font-semibold text-gray-900">Top Defect Types</h2>
        </div>
        <div class="p-5 space-y-3">
            {% for d in top_defects %}
            <div>
                <div class="flex items-center justify-between text-sm mb-1">
                    <span class="text-gray-700 truncate mr-4">{{ d.description }}</span>
                    <span class="text-gray-500 whitespace-nowrap">{{ d.count }} ({{ d.pct }}%)</span>
                </div>
                <div class="w-full bg-gray-100 rounded-full h-3">
                    <div class="h-3 rounded-full bg-primary" style="width: {{ d.bar_pct }}%;"></div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    {% endif %}

    {% endif %}
</div>
{% endblock %}
'''


def main():
    print("=== Analytics Restructure: Phase B Deploy ===")
    print()

    with open(ANALYTICS_PATH, 'r') as f:
        content = f.read()

    old_stub = """@analytics_bp.route('/<block_slug>/<int:floor>')
@require_manager
def block_floor_detail(block_slug, floor):
    \"\"\"Block+Floor detail page - placeholder until Phase B.\"\"\"
    block = _slug_to_block(block_slug)
    floor_label = FLOOR_LABELS.get(floor, 'Floor {}'.format(floor))
    return render_template('analytics/block_floor_detail.html',
                           block=block, floor=floor,
                           label='{} {}'.format(block, floor_label))"""

    if old_stub in content:
        content = content.replace(old_stub, NEW_DETAIL_FUNCTION, 1)
        print("OK: Replaced stub with full block_floor_detail")
    else:
        print("ERROR: Could not find stub function")
        return

    with open(ANALYTICS_PATH, 'w') as f:
        f.write(content)

    try:
        py_compile.compile(ANALYTICS_PATH, doraise=True)
        print("OK: analytics.py syntax check passed")
    except py_compile.PyCompileError as e:
        print("SYNTAX ERROR: {}".format(e))
        return

    detail_path = os.path.join(TEMPLATE_DIR, 'block_floor_detail.html')
    with open(detail_path, 'w') as f:
        f.write(DETAIL_TEMPLATE)
    print("OK: Replaced block_floor_detail.html with full template")

    print("\nPhase B complete.")


if __name__ == '__main__':
    main()
