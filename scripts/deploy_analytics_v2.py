"""
Analytics Restructure: Combined Phase A + B Deploy
Uses regex matching (robust against whitespace variations).
Run from repo root: python3 scripts/deploy_analytics_v2.py
"""
import os
import re
import py_compile

REPO_ROOT = os.getcwd()
ANALYTICS_PATH = os.path.join(REPO_ROOT, 'app/routes/analytics.py')
TEMPLATE_DIR = os.path.join(REPO_ROOT, 'app/templates/analytics')

NEW_CODE = '''
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

    items_project = ITEMS_PER_UNIT * total_units_project
    project = {
        'total_units': total_units_project,
        'open_defects': total_defects_project,
        'avg_defects': round(total_defects_project / total_units_project, 1) if total_units_project > 0 else 0,
        'defect_rate': round(total_defects_project / items_project * 100, 1) if items_project > 0 else 0,
        'certified': total_certified_project,
    }

    return render_template('analytics/dashboard_v2.html',
                           has_data=True, cards=cards, project=project)


@analytics_bp.route('/<block_slug>/<int:floor>')
@require_manager
def block_floor_detail(block_slug, floor):
    """Block+Floor detail page - unit table, round comparison, area breakdown, top defects."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')
    block = _slug_to_block(block_slug)
    floor_label = FLOOR_LABELS.get(floor, 'Floor {}'.format(floor))
    label = '{} {}'.format(block, floor_label)

    cycles = [dict(r) for r in query_db("""
        SELECT id, cycle_number
        FROM inspection_cycle
        WHERE block = ? AND floor = ? AND tenant_id = ? AND id NOT LIKE 'test-%'
        ORDER BY cycle_number
    """, [block, floor, tenant_id])]
    max_round = max((c['cycle_number'] for c in cycles), default=0)

    if not cycles:
        return render_template('analytics/block_floor_detail.html',
                               block=block, floor=floor, label=label,
                               has_data=False, units=[], rounds=[],
                               area_data=[], area_deep_dive=[], dd_callout='',
                               top_defects=[], summary={}, td_median=0)

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

    unit_latest = {}
    for r in units_raw:
        un = r['unit_number']
        if un not in unit_latest or r['round_number'] > unit_latest[un]['round_number']:
            unit_latest[un] = r

    status_display = {
        'not_started': 'Not Started', 'in_progress': 'In Progress',
        'submitted': 'Submitted', 'reviewed': 'Reviewed',
        'pending_followup': 'Signed Off', 'approved': 'Approved',
        'certified': 'Certified', 'closed': 'Closed',
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
        defect_rate = round(r['defect_count'] / ITEMS_PER_UNIT * 100, 1) if ITEMS_PER_UNIT > 0 else 0
        units.append({
            'unit_number': un, 'round_number': r['round_number'],
            'insp_status': r['insp_status'],
            'status_label': status_display.get(r['insp_status'], r['insp_status']),
            'status_colour': status_colour.get(r['insp_status'], 'bg-gray-100 text-gray-600'),
            'defect_count': r['defect_count'], 'defect_rate': defect_rate,
            'inspector_name': r['inspector_name'] or '-',
        })
    units.sort(key=lambda u: u['defect_count'], reverse=True)

    total_units = len(units)
    total_defects = sum(u['defect_count'] for u in units)
    avg_defects = round(total_defects / total_units, 1) if total_units > 0 else 0
    items_inspected = ITEMS_PER_UNIT * total_units
    defect_rate = round(total_defects / items_inspected * 100, 1) if items_inspected > 0 else 0

    counts_sorted = sorted(u['defect_count'] for u in units)
    if not counts_sorted:
        median_defects = 0
    elif len(counts_sorted) % 2 == 0:
        median_defects = round((counts_sorted[len(counts_sorted) // 2 - 1] + counts_sorted[len(counts_sorted) // 2]) / 2, 1)
    else:
        median_defects = counts_sorted[len(counts_sorted) // 2]

    summary = {
        'total_units': total_units, 'total_defects': total_defects,
        'avg_defects': avg_defects, 'defect_rate': defect_rate,
        'items_inspected': items_inspected, 'max_round': max_round,
        'median_defects': median_defects,
    }

    rounds = []
    if max_round > 1:
        rounds = [dict(r) for r in query_db("""
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
        for r in rounds:
            r['avg_defects'] = round(r['total_defects'] / r['units_inspected'], 1) if r['units_inspected'] > 0 else 0
            r['clearance_pct'] = round(r['cleared'] / r['total_defects'] * 100, 1) if r['total_defects'] > 0 else 0

    area_data = [dict(r) for r in query_db("""
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

    max_area_count = area_data[0]['defect_count'] if area_data else 1
    for a in area_data:
        a['bar_pct'] = round(a['defect_count'] / max_area_count * 100)
        a['pct'] = round(a['defect_count'] / total_defects * 100, 1) if total_defects > 0 else 0
        a['colour'] = AREA_COLOURS.get(a['area'], '#9ca3af')

    area_deep_dive = []
    dd_colours = ['#C8963E', '#3D6B8E']
    for idx, area_row in enumerate(area_data[:2]):
        area_name = area_row['area']
        area_defects = [dict(r) for r in query_db("""
            SELECT d.original_comment as description, COUNT(*) as count
            FROM defect d
            JOIN unit u ON d.unit_id = u.id
            JOIN item_template it ON d.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at2 ON ct.area_id = at2.id
            WHERE u.block = ? AND u.floor = ? AND d.tenant_id = ?
            AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%'
            AND at2.area_name = ?
            GROUP BY d.original_comment
            ORDER BY count DESC
            LIMIT 3
        """, [block, floor, tenant_id, area_name])]
        max_dd = area_defects[0]['count'] if area_defects else 1
        for d in area_defects:
            d['bar_pct'] = round(d['count'] / max_dd * 100)
        area_deep_dive.append({
            'area': area_name, 'total': area_row['defect_count'],
            'pct_of_total': area_row['pct'], 'colour': dd_colours[idx],
            'defects': area_defects,
        })

    dd_callout = ''
    if len(area_deep_dive) >= 1 and area_deep_dive[0]['defects']:
        a1 = area_deep_dive[0]
        d1 = a1['defects'][0]
        dd_callout = 'The most frequent defect in {} is {} ({} occurrences).'.format(
            a1['area'], d1['description'].lower(), d1['count'])
        if len(area_deep_dive) >= 2 and area_deep_dive[1]['defects']:
            a2 = area_deep_dive[1]
            d2 = a2['defects'][0]
            dd_callout += ' In {}, {} leads with {} occurrences.'.format(
                a2['area'], d2['description'].lower(), d2['count'])

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

    td_counts = sorted(d['count'] for d in top_defects) if top_defects else []
    if not td_counts:
        td_median = 0
    elif len(td_counts) % 2 == 0:
        td_median = round((td_counts[len(td_counts) // 2 - 1] + td_counts[len(td_counts) // 2]) / 2, 1)
    else:
        td_median = td_counts[len(td_counts) // 2]

    return render_template('analytics/block_floor_detail.html',
                           block=block, floor=floor, label=label,
                           block_slug=block_slug,
                           has_data=True, units=units, rounds=rounds,
                           area_data=area_data, area_deep_dive=area_deep_dive,
                           dd_callout=dd_callout, top_defects=top_defects,
                           td_median=td_median, summary=summary)

'''

DASHBOARD_V2_TEMPLATE = r'''{% extends "base.html" %}
{% block title %}Analytics{% endblock %}
{% block content %}
<div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
            <h1 class="text-2xl font-bold text-gray-900">Analytics Dashboard</h1>
            <p class="text-sm text-gray-500 mt-1">Power Park Student Housing - Phase 3</p>
        </div>
        <a href="{{ url_for('analytics.dashboard_legacy') }}" class="text-xs text-gray-400 hover:text-gray-600">Legacy view</a>
    </div>
    {% if not has_data %}
    <div class="bg-white rounded-lg shadow p-8 text-center text-gray-500">No inspection data available yet.</div>
    {% else %}
    <div class="bg-white rounded-lg shadow p-5" style="border-left: 4px solid #1e3a5f;">
        <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Project Overview</h2>
        <div class="grid grid-cols-2 sm:grid-cols-5 gap-4">
            <div><div class="text-2xl font-bold text-gray-900">{{ project.total_units }}</div><div class="text-xs text-gray-500">of ~690 units</div></div>
            <div><div class="text-2xl font-bold {% if project.open_defects > 0 %}text-red-600{% else %}text-emerald-600{% endif %}">{{ project.open_defects }}</div><div class="text-xs text-gray-500">open defects</div></div>
            <div><div class="text-2xl font-bold text-gray-900">{{ project.avg_defects }}</div><div class="text-xs text-gray-500">avg per unit</div></div>
            <div><div class="text-2xl font-bold text-gray-900">{{ project.defect_rate }}%</div><div class="text-xs text-gray-500">defect rate</div></div>
            <div><div class="text-2xl font-bold {% if project.certified > 0 %}text-emerald-600{% else %}text-gray-400{% endif %}">{{ project.certified }}</div><div class="text-xs text-gray-500">certified</div></div>
        </div>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        {% for card in cards %}
        <div class="bg-white rounded-lg shadow p-5" style="border-left: 4px solid {{ card.colour }};">
            <div class="flex items-center justify-between mb-3">
                <h3 class="text-sm font-semibold text-gray-500 uppercase tracking-wide">{{ card.label }}</h3>
                <span class="text-xs px-2 py-0.5 rounded-full {% if card.max_round > 1 %}bg-blue-100 text-blue-700{% else %}bg-gray-100 text-gray-600{% endif %}">{% if card.max_round > 1 %}Re-inspections{% else %}Round 1{% endif %}</span>
            </div>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                <div><div class="text-2xl font-bold text-gray-900">{{ card.total_units }}</div><div class="text-xs text-gray-500">units</div></div>
                <div><div class="text-2xl font-bold {% if card.open_defects > 0 %}text-red-600{% else %}text-emerald-600{% endif %}">{{ card.open_defects }}</div><div class="text-xs text-gray-500">open defects</div></div>
                <div><div class="text-2xl font-bold text-gray-900">{{ card.avg_defects }}</div><div class="text-xs text-gray-500">avg per unit</div></div>
                <div><div class="text-2xl font-bold text-gray-900">{{ card.defect_rate }}%</div><div class="text-xs text-gray-500">defect rate</div></div>
            </div>
            <div class="space-y-1 mb-4">{% for round in card.rounds %}<div class="flex items-center justify-between text-sm"><span class="text-gray-600">Round {{ round.round_number }}</span><span class="text-gray-900 font-medium">{{ round.units_inspected }} inspected</span></div>{% endfor %}</div>
            <div class="flex items-center justify-between pt-3 border-t border-gray-100">
                <span class="text-sm {% if card.certified > 0 %}text-emerald-600 font-medium{% else %}text-gray-400{% endif %}">{{ card.certified }} certified</span>
                <a href="{{ url_for('analytics.block_floor_detail', block_slug=card.block_slug, floor=card.floor) }}" class="text-sm font-medium text-primary hover:underline">View Details &rarr;</a>
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
    <div>
        <a href="{{ url_for('analytics.dashboard') }}" class="text-primary hover:underline text-sm">&larr; Dashboard</a>
        <h1 class="text-2xl font-bold text-gray-900 mt-1">{{ label }}</h1>
    </div>
    {% if not has_data %}
    <div class="bg-white rounded-lg shadow p-8 text-center text-gray-500">No inspection data for this block+floor yet.</div>
    {% else %}
    <div class="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div class="bg-white rounded-lg shadow p-4"><div class="text-3xl font-bold text-gray-900">{{ summary.total_units }}</div><div class="text-sm text-gray-500 mt-1">units inspected</div></div>
        <div class="bg-white rounded-lg shadow p-4"><div class="text-3xl font-bold {% if summary.total_defects > 0 %}text-red-600{% else %}text-emerald-600{% endif %}">{{ summary.total_defects }}</div><div class="text-sm text-gray-500 mt-1">open defects</div></div>
        <div class="bg-white rounded-lg shadow p-4"><div class="text-3xl font-bold text-gray-900">{{ summary.avg_defects }}</div><div class="text-sm text-gray-500 mt-1">avg per unit</div><div class="text-xs text-gray-400 mt-0.5">median: {{ summary.median_defects }}</div></div>
        <div class="bg-white rounded-lg shadow p-4"><div class="text-3xl font-bold text-gray-900">{{ summary.defect_rate }}%</div><div class="text-sm text-gray-500 mt-1">defect rate ({{ summary.items_inspected }} items)</div></div>
        <div class="bg-white rounded-lg shadow p-4"><div class="text-3xl font-bold text-gray-900">R{{ summary.max_round }}</div><div class="text-sm text-gray-500 mt-1">latest round</div></div>
    </div>
    {% if rounds|length > 1 %}
    <div class="bg-white rounded-lg shadow p-4">
        <h2 class="text-lg font-semibold text-gray-900 mb-1">Round Comparison</h2>
        <p class="text-sm text-gray-500 mb-4">Side-by-side performance across inspection rounds.</p>
        <div class="grid grid-cols-1 sm:grid-cols-{{ rounds|length }} gap-4">
            {% for r in rounds %}
            <div class="p-4 rounded-lg {% if loop.last %}bg-blue-50 border border-blue-200{% else %}bg-gray-50{% endif %}">
                <div class="text-sm font-semibold text-gray-500 uppercase mb-3">Round {{ r.round_number }}</div>
                <div class="space-y-2">
                    <div class="flex justify-between text-sm"><span class="text-gray-600">Units inspected</span><span class="font-medium text-gray-900">{{ r.units_inspected }}</span></div>
                    <div class="flex justify-between text-sm"><span class="text-gray-600">Defects raised</span><span class="font-medium text-gray-900">{{ r.total_defects }}</span></div>
                    <div class="flex justify-between text-sm"><span class="text-gray-600">Still open</span><span class="font-medium {% if r.still_open > 0 %}text-red-600{% else %}text-emerald-600{% endif %}">{{ r.still_open }}</span></div>
                    <div class="flex justify-between text-sm"><span class="text-gray-600">Cleared</span><span class="font-medium text-emerald-600">{{ r.cleared }}</span></div>
                    <div class="flex justify-between text-sm pt-2 border-t border-gray-200"><span class="text-gray-600">Clearance rate</span><span class="font-medium {% if r.clearance_pct >= 50 %}text-emerald-600{% else %}text-amber-600{% endif %}">{{ r.clearance_pct }}%</span></div>
                    <div class="flex justify-between text-sm"><span class="text-gray-600">Avg per unit</span><span class="font-medium text-gray-900">{{ r.avg_defects }}</span></div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    {% endif %}
    {% if area_data %}
    <div class="bg-white rounded-lg shadow p-4">
        <h2 class="text-lg font-semibold text-gray-900 mb-1">Defect Distribution by Area</h2>
        <p class="text-sm text-gray-500 mb-4">Breakdown of defects by physical area.</p>
        <div class="space-y-3">
            {% for a in area_data %}
            <div>
                <div class="flex items-center justify-between mb-1"><span class="text-sm text-gray-800">{{ a.area }}</span><span class="text-sm font-semibold text-gray-900">{{ a.defect_count }} <span class="text-gray-400 font-normal">({{ a.pct }}%)</span></span></div>
                <div class="w-full bg-gray-100 rounded-full h-2"><div class="h-2 rounded-full" style="width: {{ a.bar_pct }}%; background: {{ a.colour }};"></div></div>
            </div>
            {% endfor %}
        </div>
        {% if area_data|length >= 2 %}
        <div class="mt-4 p-3 bg-amber-50 rounded text-sm text-gray-700" style="border-left: 3px solid #d97706;"><span class="font-semibold">Key finding:</span> {{ area_data[0].area }} and {{ area_data[1].area }} account for {{ area_data[0].pct + area_data[1].pct }}% of all defects.</div>
        {% endif %}
    </div>
    {% endif %}
    {% if area_deep_dive %}
    <div class="bg-white rounded-lg shadow p-4">
        <h2 class="text-lg font-semibold text-gray-900 mb-1">Area Deep Dive</h2>
        <p class="text-sm text-gray-500 mb-4">Top 3 defect types in the highest-defect areas.</p>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {% for area in area_deep_dive %}
            <div class="border rounded-lg p-4" style="border-left: 4px solid {{ area.colour }};">
                <div class="flex items-center justify-between mb-3"><h3 class="font-semibold text-gray-900">{{ area.area }}</h3><span class="text-sm text-gray-500">{{ area.total }} defects ({{ area.pct_of_total }}%)</span></div>
                <div class="space-y-3">
                    {% for d in area.defects %}
                    <div>
                        <div class="flex items-center gap-2 mb-1"><span class="inline-flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold text-white" style="background: {{ area.colour }};">{{ loop.index }}</span><span class="text-sm text-gray-800 flex-1">{{ d.description }}</span><span class="text-sm font-semibold text-gray-700">{{ d.count }}</span></div>
                        <div class="w-full bg-gray-100 rounded-full h-2"><div class="h-2 rounded-full" style="width: {{ d.bar_pct }}%; background: {{ area.colour }}; opacity: 0.7;"></div></div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% if dd_callout %}
        <div class="mt-4 p-3 bg-amber-50 rounded text-sm text-gray-700" style="border-left: 3px solid #d97706;"><span class="font-semibold">Key finding:</span> {{ dd_callout }}</div>
        {% endif %}
    </div>
    {% endif %}
    {% if top_defects %}
    <div class="bg-white rounded-lg shadow p-4">
        <h2 class="text-lg font-semibold text-gray-900 mb-1">Most Common Defect Types</h2>
        <p class="text-sm text-gray-500 mb-3">Top 10 defect descriptions by frequency. <span class="text-gray-400">Median: {{ td_median }}</span></p>
        {% set max_cnt = top_defects[0].count if top_defects else 1 %}
        <div class="space-y-3">
            {% for d in top_defects %}
            <div>
                <div class="flex items-center gap-2 mb-1"><span class="text-sm text-gray-800 flex-1">{{ d.description }}</span><span class="text-sm font-semibold tabular-nums {% if d.count > td_median %}text-red-600{% elif d.count == td_median %}text-amber-600{% else %}text-emerald-600{% endif %}">{{ d.count }}</span><span class="text-xs tabular-nums text-gray-400 w-12 text-right">{{ (d.count / summary.total_defects * 100)|round(1) }}%</span></div>
                <div class="w-full bg-gray-100 rounded-full h-2"><div class="h-2 rounded-full {% if d.count > td_median %}bg-red-400{% elif d.count == td_median %}bg-amber-400{% else %}bg-emerald-400{% endif %}" style="width: {{ (d.count / max_cnt * 100)|round }}%;"></div></div>
            </div>
            {% endfor %}
        </div>
    </div>
    {% endif %}
    {% if units %}
    <div class="bg-white rounded-lg shadow p-4">
        <h2 class="text-lg font-semibold text-gray-900 mb-1">Unit Summary</h2>
        <p class="text-sm text-gray-500 mb-3">All units ranked by defect count (worst first). <span class="text-gray-400">Median: {{ summary.median_defects }}</span></p>
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead><tr class="border-b border-gray-200"><th class="text-left py-2 px-3 text-gray-600 font-medium">Unit</th><th class="text-center py-2 px-3 text-gray-600 font-medium">Round</th><th class="text-center py-2 px-3 text-gray-600 font-medium">Status</th><th class="text-left py-2 px-3 text-gray-600 font-medium">Defects</th></tr></thead>
                <tbody>
                    {% set max_defects = units[0].defect_count if units else 1 %}
                    {% for u in units %}
                    <tr class="border-b border-gray-100 hover:bg-gray-50">
                        <td class="py-2 px-3 font-medium">{{ u.unit_number }}</td>
                        <td class="py-2 px-3 text-center text-gray-500">{{ u.round_number }}</td>
                        <td class="py-2 px-3 text-center"><span class="inline-block px-2 py-0.5 rounded text-xs font-semibold {{ u.status_colour }}">{{ u.status_label }}</span></td>
                        <td class="py-2 px-3">
                            <div class="flex items-center gap-2">
                                <span class="text-sm font-semibold tabular-nums w-8 text-right {% if u.defect_count > summary.median_defects %}text-red-600{% elif u.defect_count == summary.median_defects %}text-amber-600{% else %}text-emerald-600{% endif %}">{{ u.defect_count }}</span>
                                <div class="flex-1 bg-gray-100 rounded-full h-2"><div class="h-2 rounded-full {% if u.defect_count > summary.median_defects %}bg-red-400{% elif u.defect_count == summary.median_defects %}bg-amber-400{% else %}bg-emerald-400{% endif %}" style="width: {{ (u.defect_count / max_defects * 100)|round }}%;"></div></div>
                                <span class="text-xs tabular-nums text-gray-400 w-12 text-right">{{ u.defect_rate }}%</span>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        <p class="text-xs text-gray-400 mt-3 flex items-center flex-wrap gap-x-4 gap-y-1">
            <span>Median: {{ summary.median_defects }} defects</span>
            <span class="inline-flex items-center gap-1"><span class="inline-block w-2 h-2 rounded-full bg-emerald-500"></span> Below</span>
            <span class="inline-flex items-center gap-1"><span class="inline-block w-2 h-2 rounded-full bg-amber-500"></span> At</span>
            <span class="inline-flex items-center gap-1"><span class="inline-block w-2 h-2 rounded-full bg-red-500"></span> Above</span>
        </p>
    </div>
    {% endif %}
    {% endif %}
</div>
{% endblock %}
'''


def main():
    print("=== Analytics Restructure: Combined A+B Deploy ===")
    print()

    with open(ANALYTICS_PATH, 'r') as f:
        content = f.read()

    if 'def dashboard_legacy' in content:
        print("ERROR: dashboard_legacy already exists. Revert first:")
        print("  git checkout -- app/routes/analytics.py")
        return
    if '_block_to_slug' in content:
        print("ERROR: New code already present. Revert first:")
        print("  git checkout -- app/routes/analytics.py")
        return

    pattern = re.compile(
        r"(@analytics_bp\.route\('/'\)\s*\n"
        r"@require_manager\s*\n"
        r"def dashboard\(\):)\s*\n"
        r'(\s*"""[^"]*""")'
    )
    match = pattern.search(content)
    if not match:
        print("ERROR: Could not find dashboard() function.")
        idx = content.find('def dashboard()')
        if idx >= 0:
            print("Found at index {}. Context:".format(idx))
            print(repr(content[max(0,idx-100):idx+100]))
        return

    old_sig = match.group(1)
    new_sig = old_sig.replace("@analytics_bp.route('/')", "@analytics_bp.route('/legacy')")
    new_sig = new_sig.replace("def dashboard():", "def dashboard_legacy():")
    new_doc = '    """LEGACY: Analytics Dashboard - cycle-based view. Will be removed."""'
    content = content[:match.start()] + new_sig + '\n' + new_doc + content[match.end():]
    print("OK: Renamed dashboard() -> dashboard_legacy() at /legacy")

    insert_point = content.find("@analytics_bp.route('/legacy')")
    content = content[:insert_point] + NEW_CODE + "\n" + content[insert_point:]
    print("OK: Inserted new dashboard + block_floor_detail code")

    with open(ANALYTICS_PATH, 'w') as f:
        f.write(content)

    try:
        py_compile.compile(ANALYTICS_PATH, doraise=True)
        print("OK: Syntax check passed")
    except py_compile.PyCompileError as e:
        print("SYNTAX ERROR: {}".format(e))
        os.system("cd {} && git checkout -- app/routes/analytics.py".format(REPO_ROOT))
        print("Reverted analytics.py")
        return

    with open(os.path.join(TEMPLATE_DIR, 'dashboard_v2.html'), 'w') as f:
        f.write(DASHBOARD_V2_TEMPLATE)
    print("OK: Created dashboard_v2.html")

    with open(os.path.join(TEMPLATE_DIR, 'block_floor_detail.html'), 'w') as f:
        f.write(DETAIL_TEMPLATE)
    print("OK: Created block_floor_detail.html")

    old_dash_path = os.path.join(TEMPLATE_DIR, 'dashboard.html')
    with open(old_dash_path, 'r') as f:
        old_dash = f.read()
    if "url_for('analytics.dashboard')" in old_dash:
        old_dash = old_dash.replace("url_for('analytics.dashboard')", "url_for('analytics.dashboard_legacy')")
        with open(old_dash_path, 'w') as f:
            f.write(old_dash)
        print("OK: Fixed dashboard.html form action")

    routes = re.findall(r"@analytics_bp\.route\('([^']+)'\)", content)
    print("\nRoutes: {}".format(', '.join('/analytics' + r for r in routes[:8])))
    print("\n=== COMPLETE ===")
    print("\nNext: git add -A && git commit -m 'feat: analytics restructure - block+floor dashboard + detail pages' && git push origin main")

if __name__ == '__main__':
    main()
