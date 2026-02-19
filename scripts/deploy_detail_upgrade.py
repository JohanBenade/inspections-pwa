"""
Upgrade block_floor_detail: Add median, deep dive, callouts, worst-first sorting.
Patches analytics.py backend + replaces template.
"""
import os
import re
import py_compile

REPO = os.getcwd()
ANALYTICS = os.path.join(REPO, 'app/routes/analytics.py')
TEMPLATE = os.path.join(REPO, 'app/templates/analytics/block_floor_detail.html')

def main():
    print("=== Upgrade Detail Page: Legacy-Aligned ===\n")

    with open(ANALYTICS, 'r') as f:
        content = f.read()

    errors = 0

    old1 = """    units = []
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
    }"""

    new1 = """    units = []
    for un in sorted(unit_latest.keys()):
        r = unit_latest[un]
        u_defect_rate = round(r['defect_count'] / ITEMS_PER_UNIT * 100, 1) if ITEMS_PER_UNIT > 0 else 0
        units.append({
            'unit_number': un,
            'round_number': r['round_number'],
            'insp_status': r['insp_status'],
            'status_label': status_display.get(r['insp_status'], r['insp_status']),
            'status_colour': status_colour.get(r['insp_status'], 'bg-gray-100 text-gray-600'),
            'defect_count': r['defect_count'],
            'defect_rate': u_defect_rate,
            'inspector_name': r['inspector_name'] or '-',
        })
    # Sort worst-first
    units.sort(key=lambda u: u['defect_count'], reverse=True)

    # Summary stats
    total_units = len(units)
    total_defects = sum(u['defect_count'] for u in units)
    avg_defects = round(total_defects / total_units, 1) if total_units > 0 else 0
    items_inspected = ITEMS_PER_UNIT * total_units
    defect_rate = round(total_defects / items_inspected * 100, 1) if items_inspected > 0 else 0

    # Median calculation
    counts_list = sorted(u['defect_count'] for u in units)
    if not counts_list:
        median_defects = 0
    elif len(counts_list) % 2 == 0:
        median_defects = round((counts_list[len(counts_list)//2-1] + counts_list[len(counts_list)//2]) / 2, 1)
    else:
        median_defects = counts_list[len(counts_list)//2]

    summary = {
        'total_units': total_units,
        'total_defects': total_defects,
        'avg_defects': avg_defects,
        'defect_rate': defect_rate,
        'items_inspected': items_inspected,
        'max_round': max_round,
        'median_defects': median_defects,
    }"""

    if old1 in content:
        content = content.replace(old1, new1, 1)
        print("OK: Patch 1 - defect_rate, worst-first sort, median")
    else:
        print("ERROR: Patch 1 - could not find unit building block")
        errors += 1

    old2 = """    # 5. Top defect types (scoped to block+floor)"""
    new2 = """    # 5. Area Deep Dive - top 3 defects in top 2 areas
    area_deep_dive = []
    dd_colours = ['#C8963E', '#3D6B8E']
    for idx, area_row in enumerate(area_data_raw[:2]):
        area_name = area_row['area']
        area_defects = [dict(r) for r in query_db(\"\"\"
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
        \"\"\", [block, floor, tenant_id, area_name])]
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

    # 6. Top defect types (scoped to block+floor)"""

    if old2 in content:
        content = content.replace(old2, new2, 1)
        print("OK: Patch 2 - area deep dive + callout")
    else:
        print("ERROR: Patch 2 - could not find top defects comment")
        errors += 1

    old3 = """    max_defect_count = top_defects[0]['count'] if top_defects else 1
    for d in top_defects:
        d['bar_pct'] = round(d['count'] / max_defect_count * 100)
        d['pct'] = round(d['count'] / total_defects * 100, 1) if total_defects > 0 else 0

    return render_template('analytics/block_floor_detail.html',"""

    new3 = """    max_defect_count = top_defects[0]['count'] if top_defects else 1
    for d in top_defects:
        d['bar_pct'] = round(d['count'] / max_defect_count * 100)
        d['pct'] = round(d['count'] / total_defects * 100, 1) if total_defects > 0 else 0

    # Top defect median for colour coding
    td_counts = sorted(d['count'] for d in top_defects) if top_defects else []
    if not td_counts:
        td_median = 0
    elif len(td_counts) % 2 == 0:
        td_median = round((td_counts[len(td_counts)//2-1] + td_counts[len(td_counts)//2]) / 2, 1)
    else:
        td_median = td_counts[len(td_counts)//2]

    return render_template('analytics/block_floor_detail.html',"""

    if old3 in content:
        content = content.replace(old3, new3, 1)
        print("OK: Patch 3 - td_median")
    else:
        print("ERROR: Patch 3 - could not find render_template block")
        errors += 1

    old4 = """                           area_data=area_data_raw,
                           top_defects=top_defects,
                           summary=summary)"""

    new4 = """                           area_data=area_data_raw,
                           area_deep_dive=area_deep_dive,
                           dd_callout=dd_callout,
                           top_defects=top_defects,
                           td_median=td_median,
                           summary=summary)"""

    if old4 in content:
        content = content.replace(old4, new4, 1)
        print("OK: Patch 4 - render_template args")
    else:
        print("ERROR: Patch 4 - could not find render args")
        errors += 1

    old5 = """                               has_data=False, units=[], rounds=[],
                               area_data=[], top_defects=[], summary={})"""

    new5 = """                               has_data=False, units=[], rounds=[],
                               area_data=[], area_deep_dive=[], dd_callout='',
                               top_defects=[], summary={}, td_median=0)"""

    if old5 in content:
        content = content.replace(old5, new5, 1)
        print("OK: Patch 5 - empty state render args")
    else:
        print("ERROR: Patch 5 - could not find empty render args")
        errors += 1

    if errors > 0:
        print("\nABORTING - {} errors".format(errors))
        return

    with open(ANALYTICS, 'w') as f:
        f.write(content)

    try:
        py_compile.compile(ANALYTICS, doraise=True)
        print("OK: Syntax check passed")
    except py_compile.PyCompileError as e:
        print("SYNTAX ERROR: {}".format(e))
        os.system("cd {} && git checkout -- app/routes/analytics.py".format(REPO))
        print("Reverted analytics.py")
        return

    DETAIL_HTML = r'''{% extends "base.html" %}
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
                <div class="flex items-center gap-2 mb-1"><span class="text-sm text-gray-800 flex-1">{{ d.description }}</span><span class="text-sm font-semibold tabular-nums {% if d.count > td_median %}text-red-600{% elif d.count == td_median %}text-amber-600{% else %}text-emerald-600{% endif %}">{{ d.count }}</span><span class="text-xs tabular-nums text-gray-400 w-12 text-right">{{ d.pct }}%</span></div>
                <div class="w-full bg-gray-100 rounded-full h-2"><div class="h-2 rounded-full {% if d.count > td_median %}bg-red-400{% elif d.count == td_median %}bg-amber-400{% else %}bg-emerald-400{% endif %}" style="width: {{ d.bar_pct }}%;"></div></div>
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

    with open(TEMPLATE, 'w') as f:
        f.write(DETAIL_HTML)
    print("OK: Template replaced with legacy-aligned version")

    print("\n=== ALL PATCHES APPLIED ===")
    print("\nNext: git add -A && git commit -m 'fix: detail page legacy-aligned visuals' && git push origin main")

if __name__ == '__main__':
    main()
