import os
import py_compile

REPO_ROOT = os.getcwd()
ANALYTICS_PATH = os.path.join(REPO_ROOT, 'app/routes/analytics.py')
TEMPLATE_DIR = os.path.join(REPO_ROOT, 'app/templates/analytics')

NEW_DASHBOARD_CODE = '''
# ============================================================
# ANALYTICS DASHBOARD v2 - Block+Floor Cards
# ============================================================

ITEMS_PER_UNIT = 437
PROJECT_TOTAL_UNITS = 690
CARD_COLOURS = ['#C8963E', '#3D6B8E', '#4A7C59', '#C44D3F', '#7B6B8D', '#5A8A7A', '#B07D4B']


def _block_to_slug(block_name):
    """Convert block name to URL slug: 'Block 5' -> 'block-5'."""
    return block_name.lower().replace(' ', '-')


def _slug_to_block(slug):
    """Convert URL slug back to block name: 'block-5' -> 'Block 5'."""
    return slug.replace('-', ' ').title()


@analytics_bp.route('/')
@require_manager
def dashboard():
    """Analytics Dashboard - block+floor cards with project overview."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    # 1. Unit counts per block+floor
    unit_counts_raw = query_db("""
        SELECT u.block, u.floor, COUNT(DISTINCT u.id) as total_units
        FROM unit u
        WHERE u.tenant_id = ? AND u.unit_number NOT LIKE 'TEST%'
        GROUP BY u.block, u.floor
        ORDER BY u.block, u.floor
    """, [tenant_id])
    unit_counts = [dict(r) for r in unit_counts_raw]

    if not unit_counts:
        return render_template('analytics/dashboard_v2.html',
                               has_data=False, cards=[], project={})

    # 2. Open defects per block+floor
    defect_counts_raw = query_db("""
        SELECT u.block, u.floor, COUNT(d.id) as open_defects
        FROM defect d
        JOIN unit u ON d.unit_id = u.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%'
        GROUP BY u.block, u.floor
    """, [tenant_id])
    defect_map = {}
    for r in defect_counts_raw:
        defect_map[(r['block'], r['floor'])] = r['open_defects']

    # 3. Round breakdown per block+floor
    rounds_raw = query_db("""
        SELECT ic.block, ic.floor, ic.cycle_number as round_number,
            COUNT(DISTINCT i.unit_id) as units_inspected
        FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%'
        AND i.status NOT IN ('not_started')
        GROUP BY ic.block, ic.floor, ic.cycle_number
        ORDER BY ic.block, ic.floor, ic.cycle_number
    """, [tenant_id])
    rounds_map = {}
    for r in rounds_raw:
        key = (r['block'], r['floor'])
        if key not in rounds_map:
            rounds_map[key] = []
        rounds_map[key].append({
            'round_number': r['round_number'],
            'units_inspected': r['units_inspected'],
        })

    # 4. Certified counts per block+floor
    certified_raw = query_db("""
        SELECT u.block, u.floor, COUNT(DISTINCT i.unit_id) as certified
        FROM inspection i
        JOIN unit u ON i.unit_id = u.id
        WHERE i.tenant_id = ? AND i.status = 'certified'
        AND i.cycle_id NOT LIKE 'test-%'
        GROUP BY u.block, u.floor
    """, [tenant_id])
    certified_map = {}
    for r in certified_raw:
        certified_map[(r['block'], r['floor'])] = r['certified']

    # 5. Build cards
    cards = []
    total_units_project = 0
    total_defects_project = 0
    total_certified_project = 0

    for idx, uc in enumerate(unit_counts):
        key = (uc['block'], uc['floor'])
        total_units = uc['total_units']
        open_defects = defect_map.get(key, 0)
        rounds = rounds_map.get(key, [])
        certified = certified_map.get(key, 0)
        max_round = max((r['round_number'] for r in rounds), default=1)
        avg_defects = round(open_defects / total_units, 1) if total_units > 0 else 0
        items_inspected = ITEMS_PER_UNIT * total_units
        defect_rate = round(open_defects / items_inspected * 100, 1) if items_inspected > 0 else 0

        floor_label = FLOOR_LABELS.get(uc['floor'], 'Floor {}'.format(uc['floor']))

        cards.append({
            'block': uc['block'],
            'floor': uc['floor'],
            'label': '{} {}'.format(uc['block'], floor_label),
            'block_slug': _block_to_slug(uc['block']),
            'total_units': total_units,
            'open_defects': open_defects,
            'avg_defects': avg_defects,
            'defect_rate': defect_rate,
            'rounds': rounds,
            'max_round': max_round,
            'certified': certified,
            'colour': CARD_COLOURS[idx % len(CARD_COLOURS)],
        })

        total_units_project += total_units
        total_defects_project += open_defects
        total_certified_project += certified

    # 6. Project overview
    items_project = ITEMS_PER_UNIT * total_units_project
    project = {
        'total_units': total_units_project,
        'open_defects': total_defects_project,
        'avg_defects': round(total_defects_project / total_units_project, 1) if total_units_project > 0 else 0,
        'defect_rate': round(total_defects_project / items_project * 100, 1) if items_project > 0 else 0,
        'certified': total_certified_project,
    }

    return render_template('analytics/dashboard_v2.html',
                           has_data=True,
                           cards=cards,
                           project=project)


@analytics_bp.route('/<block_slug>/<int:floor>')
@require_manager
def block_floor_detail(block_slug, floor):
    """Block+Floor detail page - placeholder until Phase B."""
    block = _slug_to_block(block_slug)
    floor_label = FLOOR_LABELS.get(floor, 'Floor {}'.format(floor))
    return render_template('analytics/block_floor_detail.html',
                           block=block, floor=floor,
                           label='{} {}'.format(block, floor_label))

'''

DASHBOARD_V2_TEMPLATE = r'''{% extends "base.html" %}

{% block title %}Analytics{% endblock %}

{% block content %}
<div class="space-y-6">

    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
            <h1 class="text-2xl font-bold text-gray-900">Analytics Dashboard</h1>
            <p class="text-sm text-gray-500 mt-1">Power Park Student Housing - Phase 3</p>
        </div>
        <a href="{{ url_for('analytics.dashboard_legacy') }}" class="text-xs text-gray-400 hover:text-gray-600">Legacy view</a>
    </div>

    {% if not has_data %}
    <div class="bg-white rounded-lg shadow p-8 text-center text-gray-500">
        No inspection data available yet.
    </div>
    {% else %}

    <!-- Project Overview Card -->
    <div class="bg-white rounded-lg shadow p-5" style="border-left: 4px solid #1e3a5f;">
        <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Project Overview</h2>
        <div class="grid grid-cols-2 sm:grid-cols-5 gap-4">
            <div>
                <div class="text-2xl font-bold text-gray-900">{{ project.total_units }}</div>
                <div class="text-xs text-gray-500">of ~690 units</div>
            </div>
            <div>
                <div class="text-2xl font-bold {% if project.open_defects > 0 %}text-red-600{% else %}text-emerald-600{% endif %}">{{ project.open_defects }}</div>
                <div class="text-xs text-gray-500">open defects</div>
            </div>
            <div>
                <div class="text-2xl font-bold text-gray-900">{{ project.avg_defects }}</div>
                <div class="text-xs text-gray-500">avg per unit</div>
            </div>
            <div>
                <div class="text-2xl font-bold text-gray-900">{{ project.defect_rate }}%</div>
                <div class="text-xs text-gray-500">defect rate</div>
            </div>
            <div>
                <div class="text-2xl font-bold {% if project.certified > 0 %}text-emerald-600{% else %}text-gray-400{% endif %}">{{ project.certified }}</div>
                <div class="text-xs text-gray-500">certified</div>
            </div>
        </div>
    </div>

    <!-- Block + Floor Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        {% for card in cards %}
        <div class="bg-white rounded-lg shadow p-5" style="border-left: 4px solid {{ card.colour }};">
            <!-- Card Header -->
            <div class="flex items-center justify-between mb-3">
                <h3 class="text-sm font-semibold text-gray-500 uppercase tracking-wide">{{ card.label }}</h3>
                <span class="text-xs px-2 py-0.5 rounded-full
                    {% if card.max_round > 1 %}bg-blue-100 text-blue-700{% else %}bg-gray-100 text-gray-600{% endif %}">
                    {% if card.max_round > 1 %}Re-inspections{% else %}Round 1{% endif %}
                </span>
            </div>

            <!-- Stats Row -->
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                <div>
                    <div class="text-2xl font-bold text-gray-900">{{ card.total_units }}</div>
                    <div class="text-xs text-gray-500">units</div>
                </div>
                <div>
                    <div class="text-2xl font-bold {% if card.open_defects > 0 %}text-red-600{% else %}text-emerald-600{% endif %}">{{ card.open_defects }}</div>
                    <div class="text-xs text-gray-500">open defects</div>
                </div>
                <div>
                    <div class="text-2xl font-bold text-gray-900">{{ card.avg_defects }}</div>
                    <div class="text-xs text-gray-500">avg per unit</div>
                </div>
                <div>
                    <div class="text-2xl font-bold text-gray-900">{{ card.defect_rate }}%</div>
                    <div class="text-xs text-gray-500">defect rate</div>
                </div>
            </div>

            <!-- Round Progress -->
            <div class="space-y-1 mb-4">
                {% for round in card.rounds %}
                <div class="flex items-center justify-between text-sm">
                    <span class="text-gray-600">Round {{ round.round_number }}</span>
                    <span class="text-gray-900 font-medium">{{ round.units_inspected }} inspected</span>
                </div>
                {% endfor %}
            </div>

            <!-- Certified + View Link -->
            <div class="flex items-center justify-between pt-3 border-t border-gray-100">
                <span class="text-sm {% if card.certified > 0 %}text-emerald-600 font-medium{% else %}text-gray-400{% endif %}">
                    {{ card.certified }} certified
                </span>
                <a href="{{ url_for('analytics.block_floor_detail', block_slug=card.block_slug, floor=card.floor) }}"
                   class="text-sm font-medium text-primary hover:underline">
                    View Details &rarr;
                </a>
            </div>
        </div>
        {% endfor %}
    </div>

    {% endif %}
</div>
{% endblock %}
'''

DETAIL_TEMPLATE = r'''{% extends "base.html" %}

{% block title %}{{ label }}{% endblock %}

{% block content %}
<div class="space-y-6">
    <div class="flex items-center gap-4">
        <a href="{{ url_for('analytics.dashboard') }}" class="text-primary hover:underline text-sm">&larr; Dashboard</a>
        <h1 class="text-2xl font-bold text-gray-900">{{ label }}</h1>
    </div>
    <div class="bg-white rounded-lg shadow p-8 text-center text-gray-500">
        <p class="text-lg mb-2">Detail view coming soon</p>
        <p class="text-sm">Unit table, round comparison, area breakdown, and top defect types will appear here.</p>
    </div>
</div>
{% endblock %}
'''


def main():
    print("=== Analytics Restructure: Phase A Deploy ===")
    print()

    errors = 0

    with open(ANALYTICS_PATH, 'r') as f:
        content = f.read()

    old_route = '@analytics_bp.route(\'/\')\n@require_manager\ndef dashboard():\n    """Analytics Dashboard - defect patterns across all units in a cycle."""'
    new_route = '@analytics_bp.route(\'/legacy\')\n@require_manager\ndef dashboard_legacy():\n    """LEGACY: Analytics Dashboard - cycle-based view. Will be removed."""'

    if old_route in content:
        content = content.replace(old_route, new_route, 1)
        print("OK: Renamed dashboard -> dashboard_legacy at /legacy")
    else:
        print("ERROR: Could not find old dashboard route signature")
        errors += 1

    insert_marker = "@analytics_bp.route('/legacy')"
    if insert_marker in content:
        content = content.replace(insert_marker,
                                  NEW_DASHBOARD_CODE + "\n" + insert_marker, 1)
        print("OK: New dashboard + block_floor_detail functions inserted")
    else:
        print("ERROR: Could not find insert marker")
        errors += 1

    if errors > 0:
        print("\nABORTING - fix errors above")
        return

    with open(ANALYTICS_PATH, 'w') as f:
        f.write(content)

    try:
        py_compile.compile(ANALYTICS_PATH, doraise=True)
        print("OK: analytics.py syntax check passed")
    except py_compile.PyCompileError as e:
        print("SYNTAX ERROR: {}".format(e))
        return

    v2_path = os.path.join(TEMPLATE_DIR, 'dashboard_v2.html')
    with open(v2_path, 'w') as f:
        f.write(DASHBOARD_V2_TEMPLATE)
    print("OK: Created dashboard_v2.html")

    detail_path = os.path.join(TEMPLATE_DIR, 'block_floor_detail.html')
    with open(detail_path, 'w') as f:
        f.write(DETAIL_TEMPLATE)
    print("OK: Created block_floor_detail.html (stub)")

    old_dash_path = os.path.join(TEMPLATE_DIR, 'dashboard.html')
    with open(old_dash_path, 'r') as f:
        old_dash = f.read()
    old_form = "url_for('analytics.dashboard')"
    new_form = "url_for('analytics.dashboard_legacy')"
    if old_form in old_dash:
        old_dash = old_dash.replace(old_form, new_form)
        with open(old_dash_path, 'w') as f:
            f.write(old_dash)
        print("OK: Fixed dashboard.html form action -> dashboard_legacy")
    else:
        print("SKIP: dashboard.html form action already updated")

    print("\nPhase A complete.")


if __name__ == '__main__':
    main()
