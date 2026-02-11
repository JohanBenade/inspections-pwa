"""
Patch: Per-block callouts under each chart in combined report.
1. Backend: compute per-block worst unit + high defect counts
2. Template: replace single callout with per-block callouts + project summary
"""
import os, ast

REPO = os.path.expanduser('~/Documents/GitHub/inspections-pwa')
PY_FILE = os.path.join(REPO, 'app/routes/analytics.py')
HTML_FILE = os.path.join(REPO, 'app/templates/analytics/report_combined.html')

# === BACKEND ===
with open(PY_FILE, 'r') as f:
    py = f.read()

if 'b5_worst_unit' not in py:
    anchor = "    high_defect_pct = round((high_defect_units / total_units) * 100) if total_units > 0 else 0"
    new_code = anchor + """

    # Per-block worst unit + high defect counts
    b5_ud = [u for u in all_unit_defects if u['block'] == 'Block 5']
    b6_ud = [u for u in all_unit_defects if u['block'] == 'Block 6']
    b5_worst_unit = max(b5_ud, key=lambda x: x['defect_count']) if b5_ud else {'unit_number': '-', 'defect_count': 0}
    b6_worst_unit = max(b6_ud, key=lambda x: x['defect_count']) if b6_ud else {'unit_number': '-', 'defect_count': 0}
    b5_high = sum(1 for u in b5_ud if u['defect_count'] > 30)
    b6_high = sum(1 for u in b6_ud if u['defect_count'] > 30)"""

    if anchor in py:
        py = py.replace(anchor, new_code)
        print('[1] Added: per-block worst unit + high defect counts')
    else:
        print('[FAIL] Could not find anchor in analytics.py')

    # Add to return dict
    old_ret = "        'high_defect_pct': high_defect_pct,"
    new_ret = """        'high_defect_pct': high_defect_pct,
        'b5_worst_unit': b5_worst_unit,
        'b6_worst_unit': b6_worst_unit,
        'b5_high': b5_high,
        'b6_high': b6_high,"""
    py = py.replace(old_ret, new_ret, 1)
    print('[2] Added: per-block vars to return dict')

    with open(PY_FILE, 'w') as f:
        f.write(py)

    try:
        ast.parse(py)
        print('[3] Syntax: OK')
    except SyntaxError as e:
        print(f'[FAIL] Syntax: {e}')
else:
    print('[SKIP] b5_worst_unit already in backend')

# === TEMPLATE ===
with open(HTML_FILE, 'r') as f:
    html = f.read()

# Replace: move callout into each block section
old_b5_close = """            </table>
        </div>
    </div>

    <!-- BLOCK 6 -->"""

new_b5_close = """            </table>
        </div>
        <div class="callout callout-gold" style="margin-top: 6px; margin-bottom: 14px;">
            <strong>Block 5 average: {{ b5.avg_defects }} defects/unit.</strong>
            {{ b5_high }} of {{ b5.total_units }} units exceed 30 defects.
            {% if b5_worst_unit.defect_count > 0 %}Worst: {{ b5_worst_unit.unit_number }} with {{ b5_worst_unit.defect_count }}.{% endif %}
        </div>
    </div>

    <!-- BLOCK 6 -->"""

if old_b5_close in html:
    html = html.replace(old_b5_close, new_b5_close, 1)
    print('[4] Added: Block 5 callout')
else:
    print('[FAIL] Could not find Block 5 close')

# Add Block 6 callout after its table
old_b6_close = """            </table>
        </div>
    </div>

    <!-- Legend -->"""

new_b6_close = """            </table>
        </div>
        <div class="callout callout-blue" style="margin-top: 6px; margin-bottom: 14px;">
            <strong>Block 6 average: {{ b6.avg_defects }} defects/unit.</strong>
            {{ b6_high }} of {{ b6.total_units }} units exceed 30 defects.
            {% if b6_worst_unit.defect_count > 0 %}Worst: {{ b6_worst_unit.unit_number }} with {{ b6_worst_unit.defect_count }}.{% endif %}
        </div>
    </div>

    <!-- Legend -->"""

if old_b6_close in html:
    html = html.replace(old_b6_close, new_b6_close, 1)
    print('[5] Added: Block 6 callout')
else:
    print('[FAIL] Could not find Block 6 close')

# Simplify bottom callout to project-only
old_bottom = """    <div class="callout callout-gold">
        <strong>Project average: {{ avg_defects }} defects per unit.</strong>
        Block 5 averages {{ b5.avg_defects }} defects/unit; Block 6 averages {{ b6.avg_defects }} defects/unit.
        {{ high_defect_units }} of {{ total_units }} units ({{ high_defect_pct }}%) exceed 30 defects.
        The worst-performing unit is {{ worst_unit.unit_number }} with {{ worst_unit.defect_count }} defects.
    </div>"""

new_bottom = """    <div class="callout callout-gold">
        <strong>Project average: {{ avg_defects }} defects per unit</strong> across {{ total_units }} units. {{ high_defect_units }} ({{ high_defect_pct }}%) exceed 30 defects.
    </div>"""

if old_bottom in html:
    html = html.replace(old_bottom, new_bottom)
    print('[6] Simplified: project callout')
else:
    print('[FAIL] Could not find bottom callout')

with open(HTML_FILE, 'w') as f:
    f.write(html)
print(f'Lines: {len(html.splitlines())}')
