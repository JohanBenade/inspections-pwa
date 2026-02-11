"""
Patch combined report:
1. Remove Items Inspected KPI, adjust width to 20%
2. Split unit bar chart by block with headers + dashed average lines
"""
import os

REPO = os.path.expanduser('~/Documents/GitHub/inspections-pwa')
HTML_FILE = os.path.join(REPO, 'app/templates/analytics/report_combined.html')

with open(HTML_FILE, 'r') as f:
    content = f.read()

changes = 0

# === FIX 1: Remove Items Inspected KPI ===
old_kpi = """    <td class="kpi-cell">
        <div class="kpi-label">Items Inspected</div>
        <div class="kpi-value">{{ '{:,}'.format(total_items) }}</div>
        <div class="kpi-sub">{{ items_per_unit }} per unit x {{ total_units }}</div>
    </td>"""
if old_kpi in content:
    content = content.replace(old_kpi, '')
    print('[1] Removed: Items Inspected KPI')
    changes += 1
else:
    print('[FAIL] Could not find Items Inspected KPI')

# === FIX 2: Width 16.66% -> 20% ===
if 'width: 16.66%' in content:
    content = content.replace('width: 16.66%', 'width: 20%')
    print('[2] Updated: KPI width to 20%')
    changes += 1
else:
    print('[SKIP] Width already changed or not found')

# === FIX 3: Replace unit chart with split-by-block version ===
old_chart = """    <!-- Vertical bar chart via table -->
    <div style="overflow-x: auto;">
    <table class="unit-bar-table" style="height: 180px;">
    <tr>
    {% for u in unit_defects %}
        <td style="height: 160px; vertical-align: bottom;">
            {% set bar_height = (u.defect_count / max_defects * 140) | int if max_defects > 0 else 2 %}
            {% if u.defect_count > 30 %}
                {% set bar_colour = '#C44D3F' %}
            {% elif u.defect_count > 20 %}
                {% set bar_colour = '#C8963E' %}
            {% else %}
                {% set bar_colour = '#4A7C59' %}
            {% endif %}
            <div class="unit-bar" style="height: {{ bar_height }}px; background: {{ bar_colour }};">
                <span class="unit-bar-label">{{ u.defect_count }}</span>
            </div>
        </td>
    {% endfor %}
    </tr>
    <tr style="border-top: 1px solid #E5E5E5;">
    {% for u in unit_defects %}
        <td style="padding-top: 4px;">
            <span class="unit-name-label">{{ u.unit_number }}</span>
        </td>
    {% endfor %}
    </tr>
    <tr>
    {% for u in unit_defects %}
        <td style="padding-top: 0;">
            {% if u.block == 'Block 5' %}
            <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #C8963E;"></span>
            {% else %}
            <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #3D6B8E;"></span>
            {% endif %}
        </td>
    {% endfor %}
    </tr>
    </table>
    </div>

    <!-- Legend + average line note -->
    <table class="legend-table">
    <tr>
        <td><span class="legend-swatch" style="background: #C8963E; border-radius: 50%;"></span><span class="legend-text">Block 5</span></td>
        <td style="padding-left: 16px;"><span class="legend-swatch" style="background: #3D6B8E; border-radius: 50%;"></span><span class="legend-text">Block 6</span></td>
        <td style="padding-left: 16px;"><span class="legend-swatch" style="background: #4A7C59;"></span><span class="legend-text">&le;20 defects</span></td>
        <td style="padding-left: 10px;"><span class="legend-swatch" style="background: #C8963E;"></span><span class="legend-text">21-30</span></td>
        <td style="padding-left: 10px;"><span class="legend-swatch" style="background: #C44D3F;"></span><span class="legend-text">&gt;30</span></td>
    </tr>
    </table>

    <div class="callout callout-gold">
        <strong>Project average: {{ avg_defects }} defects per unit.</strong> {{ high_defect_units }} of {{ total_units }} units ({{ high_defect_pct }}%) exceed 30 defects. The worst-performing unit is {{ worst_unit.unit_number }} with {{ worst_unit.defect_count }} defects.
    </div>"""

new_chart = """    {% set b5_units = unit_defects | selectattr('block', 'equalto', 'Block 5') | list %}
    {% set b6_units = unit_defects | selectattr('block', 'equalto', 'Block 6') | list %}

    <!-- BLOCK 5 -->
    <div style="margin-bottom: 6px;">
        <div style="font-size: 9px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #C8963E; margin-bottom: 6px;">Block 5 &mdash; Units {{ b5_units[0].unit_number }}-{{ b5_units[-1].unit_number }} &bull; Avg {{ b5.avg_defects }} defects/unit</div>
        <div style="position: relative; overflow-x: auto;">
            <!-- Average line -->
            {% set avg_line_b5 = (b5.avg_defects / max_defects * 140) | int if max_defects > 0 else 0 %}
            <div style="position: absolute; left: 0; right: 40px; bottom: {{ avg_line_b5 + 38 }}px; border-top: 2px dashed #C8963E; opacity: 0.5; z-index: 1;"></div>
            <table class="unit-bar-table" style="height: 180px; position: relative; z-index: 2;">
            <tr>
            {% for u in b5_units %}
                <td style="height: 160px; vertical-align: bottom;">
                    {% set bar_height = (u.defect_count / max_defects * 140) | int if max_defects > 0 else 2 %}
                    {% if u.defect_count > 30 %}{% set bar_colour = '#C44D3F' %}{% elif u.defect_count > 20 %}{% set bar_colour = '#C8963E' %}{% else %}{% set bar_colour = '#4A7C59' %}{% endif %}
                    <div class="unit-bar" style="height: {{ bar_height }}px; background: {{ bar_colour }};">
                        <span class="unit-bar-label">{{ u.defect_count }}</span>
                    </div>
                </td>
            {% endfor %}
            </tr>
            <tr style="border-top: 1px solid #E5E5E5;">
            {% for u in b5_units %}<td style="padding-top: 4px;"><span class="unit-name-label">{{ u.unit_number }}</span></td>{% endfor %}
            </tr>
            </table>
        </div>
    </div>

    <!-- BLOCK 6 -->
    <div style="margin-bottom: 6px;">
        <div style="font-size: 9px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #3D6B8E; margin-bottom: 6px;">Block 6 &mdash; Units {{ b6_units[0].unit_number }}-{{ b6_units[-1].unit_number }} &bull; Avg {{ b6.avg_defects }} defects/unit</div>
        <div style="position: relative; overflow-x: auto;">
            <!-- Average line -->
            {% set avg_line_b6 = (b6.avg_defects / max_defects * 140) | int if max_defects > 0 else 0 %}
            <div style="position: absolute; left: 0; right: 40px; bottom: {{ avg_line_b6 + 38 }}px; border-top: 2px dashed #3D6B8E; opacity: 0.5; z-index: 1;"></div>
            <table class="unit-bar-table" style="height: 180px; position: relative; z-index: 2;">
            <tr>
            {% for u in b6_units %}
                <td style="height: 160px; vertical-align: bottom;">
                    {% set bar_height = (u.defect_count / max_defects * 140) | int if max_defects > 0 else 2 %}
                    {% if u.defect_count > 30 %}{% set bar_colour = '#C44D3F' %}{% elif u.defect_count > 20 %}{% set bar_colour = '#C8963E' %}{% else %}{% set bar_colour = '#4A7C59' %}{% endif %}
                    <div class="unit-bar" style="height: {{ bar_height }}px; background: {{ bar_colour }};">
                        <span class="unit-bar-label">{{ u.defect_count }}</span>
                    </div>
                </td>
            {% endfor %}
            </tr>
            <tr style="border-top: 1px solid #E5E5E5;">
            {% for u in b6_units %}<td style="padding-top: 4px;"><span class="unit-name-label">{{ u.unit_number }}</span></td>{% endfor %}
            </tr>
            </table>
        </div>
    </div>

    <!-- Legend -->
    <table class="legend-table">
    <tr>
        <td><span class="legend-swatch" style="background: #4A7C59;"></span><span class="legend-text">&le;20 defects</span></td>
        <td style="padding-left: 10px;"><span class="legend-swatch" style="background: #C8963E;"></span><span class="legend-text">21-30</span></td>
        <td style="padding-left: 10px;"><span class="legend-swatch" style="background: #C44D3F;"></span><span class="legend-text">&gt;30</span></td>
        <td style="padding-left: 16px;"><span style="display: inline-block; width: 16px; height: 0; border-top: 2px dashed #6B6B6B; vertical-align: middle;"></span><span class="legend-text" style="padding-left: 4px;">Block average</span></td>
    </tr>
    </table>

    <div class="callout callout-gold">
        <strong>Project average: {{ avg_defects }} defects per unit.</strong>
        Block 5 averages {{ b5.avg_defects }} defects/unit; Block 6 averages {{ b6.avg_defects }} defects/unit.
        {{ high_defect_units }} of {{ total_units }} units ({{ high_defect_pct }}%) exceed 30 defects.
        The worst-performing unit is {{ worst_unit.unit_number }} with {{ worst_unit.defect_count }} defects.
    </div>"""

if old_chart in content:
    content = content.replace(old_chart, new_chart)
    print('[3] Replaced: Unit chart with split-by-block + avg lines')
    changes += 1
else:
    print('[FAIL] Could not find unit chart block')

with open(HTML_FILE, 'w') as f:
    f.write(content)
print(f'Lines: {len(content.splitlines())}')
print(f'Changes applied: {changes}/3')
