"""
Patch: Hotspot panel improvements
"""
import re

REPO = '/Users/johanbenade/Documents/GitHub/inspections-pwa'

# ============================================================
# PATCH 1: Backend - analytics.py
# ============================================================
analytics_path = f'{REPO}/app/routes/analytics.py'
with open(analytics_path, 'r') as f:
    lines = f.readlines()

code = ''.join(lines)

# 1a. After area_max line, insert area_median + top-2 insight
old_area = "    area_max = area_data[0]['defect_count'] if area_data else 1\n"
new_area = (
    "    area_max = area_data[0]['defect_count'] if area_data else 1\n"
    "\n"
    "    # Area median for colour coding\n"
    "    area_counts_sorted = sorted([a['defect_count'] for a in area_data])\n"
    "    if area_counts_sorted:\n"
    "        mid = len(area_counts_sorted) // 2\n"
    "        area_median = area_counts_sorted[mid] if len(area_counts_sorted) % 2 else (area_counts_sorted[mid - 1] + area_counts_sorted[mid]) / 2\n"
    "    else:\n"
    "        area_median = 0\n"
    "    # Top 2 areas insight\n"
    "    area_top2_sum = sum(a['defect_count'] for a in area_data[:2]) if len(area_data) >= 2 else 0\n"
    "    area_top2_pct = round(area_top2_sum / project['open_defects'] * 100) if project['open_defects'] > 0 else 0\n"
    "    area_top2_names = [a['area'].title() for a in area_data[:2]] if len(area_data) >= 2 else []\n"
)

assert old_area in code, "ABORT: Cannot find area_max line"
code = code.replace(old_area, new_area, 1)

# 1b. After worst_units LIMIT 5 block, insert insight computation
old_worst_marker = "    # Separate active vs awaiting blocks (a block is active if ANY zone has inspections)\n"
new_worst_insert = (
    "    # Worst units insight for footer\n"
    "    worst_sum = sum(u['defect_count'] for u in worst_units)\n"
    "    worst_pct = round(worst_sum / project['open_defects'] * 100) if project['open_defects'] > 0 else 0\n"
    "    worst_blocks = {}\n"
    "    for u in worst_units:\n"
    "        key = u['block'] + ' ' + FLOOR_LABELS.get(u['floor'], 'Floor ' + str(u['floor']))\n"
    "        worst_blocks[key] = worst_blocks.get(key, 0) + 1\n"
    "    worst_dominant = max(worst_blocks.items(), key=lambda x: x[1]) if worst_blocks else ('', 0)\n"
    "\n"
    "    # Separate active vs awaiting blocks (a block is active if ANY zone has inspections)\n"
)

assert old_worst_marker in code, "ABORT: Cannot find active/awaiting marker"
code = code.replace(old_worst_marker, new_worst_insert, 1)

# 1c. Add new variables to render_template call
old_render = "                           area_colours=AREA_COLOURS,"
new_render = (
    "                           area_colours=AREA_COLOURS,\n"
    "                           area_median=area_median,\n"
    "                           area_top2_pct=area_top2_pct,\n"
    "                           area_top2_names=area_top2_names,\n"
    "                           worst_pct=worst_pct,\n"
    "                           worst_dominant_zone=worst_dominant[0],\n"
    "                           worst_dominant_count=worst_dominant[1],"
)

assert old_render in code, "ABORT: Cannot find area_colours render line"
code = code.replace(old_render, new_render, 1)

with open(analytics_path, 'w') as f:
    f.write(code)
print("PATCHED: analytics.py")

# ============================================================
# PATCH 2: Template - dashboard_v2.html
# ============================================================
tmpl_path = f'{REPO}/app/templates/analytics/dashboard_v2.html'
with open(tmpl_path, 'r') as f:
    tmpl = f.read()

# 2a. Worst Units title
old_title = '<span style="font-size: 0.9rem; font-weight: 600; color: #1A1A1A;">Worst Units</span>\n                <span style="font-size: 0.7rem; color: #9A9A9A;">top 5 by open defects</span>'
new_title = '<span style="font-size: 0.9rem; font-weight: 600; color: #1A1A1A;">5 Worst Units by Open Defects</span>'

assert old_title in tmpl, "ABORT: Cannot find Worst Units title"
tmpl = tmpl.replace(old_title, new_title, 1)

# 2b. Area bars: severity colour coding
old_bar = "background: {{ area_colours.get(area.area, '#6B6B6B') }};"
new_bar = "background: {% if area.defect_count > area_median * 1.5 %}#C44D3F{% elif area.defect_count > area_median %}#C8963E{% else %}#4A7C59{% endif %};"

assert old_bar in tmpl, "ABORT: Cannot find area bar colour"
tmpl = tmpl.replace(old_bar, new_bar, 1)

# 2c. Area footer
old_area_footer = (
    """<div style="font-size: 0.7rem; color: #9A9A9A; margin-top: 0.5rem; padding-top: 0.4rem; border-top: 1px solid #f0f0f0;">"""
    """{{ '{:,}'.format(project.open_defects) }} open defects &middot; Colours identify areas &middot; Tap to drill down</div>"""
)
new_area_footer = (
    '<div style="font-size: 0.7rem; color: #9A9A9A; margin-top: 0.5rem; padding-top: 0.4rem; border-top: 1px solid #f0f0f0;">\n'
    '                <div style="margin-bottom: 0.25rem;">\n'
    '                    <span class="legend-item"><span class="legend-dot" style="background: #C44D3F;"></span> &gt;{{ (area_median * 1.5)|round|int }}</span>&ensp;\n'
    '                    <span class="legend-item"><span class="legend-dot" style="background: #C8963E;"></span> {{ area_median|round|int }}&ndash;{{ (area_median * 1.5)|round|int }}</span>&ensp;\n'
    '                    <span class="legend-item"><span class="legend-dot" style="background: #4A7C59;"></span> &lt;{{ area_median|round|int }}</span>&ensp;\n'
    '                    <span style="color: #BABABA;">&middot;</span>&ensp;\n'
    '                    median: {{ area_median|round|int }}\n'
    '                </div>\n'
    '                <div style="margin-bottom: 0.25rem;">{{ area_top2_names[0] }} and {{ area_top2_names[1] }} account for {{ area_top2_pct }}% of all defects</div>\n'
    '                <div>Tap any area to explore units and defect detail &rarr;</div>\n'
    '            </div>'
)

assert old_area_footer in tmpl, "ABORT: Cannot find area footer"
tmpl = tmpl.replace(old_area_footer, new_area_footer, 1)

# 2d. Worst Units footer - match by unique opening
old_worst_footer_start = 'median: {{ project.median_defects }} &middot; Tap to drill down\n            </div>'
new_worst_footer_end = (
    'median: {{ project.median_defects }}\n'
    '                </div>\n'
    '                <div style="margin-bottom: 0.25rem;">These 5 units hold {{ worst_pct }}% of all open defects &middot; {{ worst_dominant_count }} of 5 are {{ worst_dominant_zone }}</div>\n'
    '                <div>Tap any unit to drill down &rarr;</div>\n'
    '            </div>'
)

assert old_worst_footer_start in tmpl, "ABORT: Cannot find worst units footer end"
tmpl = tmpl.replace(old_worst_footer_start, new_worst_footer_end, 1)

with open(tmpl_path, 'w') as f:
    f.write(tmpl)
print("PATCHED: dashboard_v2.html")

print("\nALL PATCHES APPLIED SUCCESSFULLY")
