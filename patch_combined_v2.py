"""
Combined report: donut labels, area deep dive, 2-status
"""
import os, ast

REPO = os.path.expanduser('~/Documents/GitHub/inspections-pwa')
PY = os.path.join(REPO, 'app/routes/analytics.py')
HTML = os.path.join(REPO, 'app/templates/analytics/report_combined.html')

with open(PY, 'r') as f:
    py = f.read()
with open(HTML, 'r') as f:
    html = f.read()

changes = 0

# === 1. DONUT MIDPOINTS (backend) ===
old_donut = """    # Compute donut SVG data
    circumference = 439.82
    offset = 0
    for a in area_data_raw:
        pct = a['defect_count'] / total_defects if total_defects > 0 else 0
        a['pct'] = round(pct * 100, 1)
        a['dash'] = round(pct * circumference, 2)
        a['offset'] = round(offset, 2)
        offset += a['dash']"""

new_donut = """    # Compute donut SVG data
    circumference = 439.82
    offset = 0
    for a in area_data_raw:
        pct = a['defect_count'] / total_defects if total_defects > 0 else 0
        a['pct'] = round(pct * 100, 1)
        a['dash'] = round(pct * circumference, 2)
        a['offset'] = round(offset, 2)
        offset += a['dash']
    for a in area_data_raw:
        mid_frac = (a['offset'] + a['dash'] / 2) / circumference
        angle = mid_frac * 2 * math.pi - math.pi / 2
        a['pct_x'] = round(100 + 70 * math.cos(angle), 1)
        a['pct_y'] = round(100 + 70 * math.sin(angle), 1)"""

if old_donut in py:
    py = py.replace(old_donut, new_donut, 1)
    print('[1] Backend: donut midpoints added')
    changes += 1
else:
    print('[SKIP/FAIL] donut block not found')

# === 2. AREA DEEP DIVE QUERY (backend) ===
anchor = "    area_colours = ['#C8963E', '#3D6B8E', '#4A7C59', '#C44D3F', '#7B6B8D', '#5A8A7A', '#B07D4B']\n\n    return {"

if 'combined_area_dive' not in py:
    new_query = '''    # --- Combined area deep dive: top 3 defects for top 2 areas with B5/B6 ---
    combined_area_dive = []
    top_2_areas = [a['area'] for a in area_data_raw[:2]]
    for area_name in top_2_areas:
        top_types = _to_dicts(query_db("""
            SELECT d.original_comment as description, COUNT(*) as total
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at2 ON ct.area_id = at2.id
            WHERE d.tenant_id = ? AND d.status = 'open' AND at2.area_name = ?
            GROUP BY d.original_comment ORDER BY total DESC LIMIT 3
        """, [tenant_id, area_name]))
        for dt in top_types:
            for blk in [b5, b6]:
                cid = blk.get('cycle_id', '')
                row = query_db("""
                    SELECT COUNT(*) as cnt FROM defect d
                    JOIN item_template it ON d.item_template_id = it.id
                    JOIN category_template ct ON it.category_id = ct.id
                    JOIN area_template at2 ON ct.area_id = at2.id
                    WHERE d.tenant_id = ? AND d.status = 'open'
                    AND at2.area_name = ? AND d.original_comment = ?
                    AND d.raised_cycle_id = ?
                """, [tenant_id, area_name, dt['description'], cid], one=True)
                label = 'b5' if blk is b5 else 'b6'
                dt[label] = dict(row)['cnt'] if row else 0
        area_total = next((a['defect_count'] for a in area_data_raw if a['area'] == area_name), 0)
        area_pct = next((a['pct'] for a in area_data_raw if a['area'] == area_name), 0)
        max_count = top_types[0]['total'] if top_types else 1
        for dt in top_types:
            dt['bar_pct'] = round((dt['total'] / max_count) * 100, 1)
        combined_area_dive.append({
            'area': area_name,
            'total': area_total,
            'pct': area_pct,
            'defects': top_types,
        })

''' + "    area_colours = ['#C8963E', '#3D6B8E', '#4A7C59', '#C44D3F', '#7B6B8D', '#5A8A7A', '#B07D4B']\n\n    return {"

    if anchor in py:
        py = py.replace(anchor, new_query, 1)
        print('[2] Backend: combined_area_dive query added')
        changes += 1
    else:
        print('[FAIL] return anchor not found')

    old_ret = "        'area_colours': area_colours,"
    new_ret = "        'combined_area_dive': combined_area_dive,\n        'area_colours': area_colours,"
    py = py.replace(old_ret, new_ret, 1)
    print('[3] Backend: combined_area_dive in return dict')
    changes += 1
else:
    print('[SKIP] combined_area_dive already exists')

# Write backend
with open(PY, 'w') as f:
    f.write(py)
try:
    ast.parse(py)
    print('[4] Syntax: OK')
except SyntaxError as e:
    print(f'[FAIL] Syntax: {e}')
    exit(1)

# === 5. DONUT PERCENTAGE LABELS (template) ===
old_svg = """                    {% endfor %}
                    <circle cx="100" cy="100" r="52" fill="#FAFAF8" />"""

new_svg = """                    {% endfor %}
                    {% for a in area_data %}
                    {% if a.pct >= 5 %}
                    <text x="{{ a.pct_x }}" y="{{ a.pct_y + 3 }}" text-anchor="middle"
                          font-family="'DM Sans', Helvetica, sans-serif" font-size="8" font-weight="600"
                          fill="white">{{ a.pct }}%</text>
                    {% endif %}
                    {% endfor %}
                    <circle cx="100" cy="100" r="52" fill="#FAFAF8" />"""

if 'a.pct_x' not in html:
    html = html.replace(old_svg, new_svg, 1)
    print('[5] Template: donut percentage labels')
    changes += 1
else:
    print('[SKIP] donut labels already present')

# === 6. AREA DEEP DIVE SECTION (template) ===
s02_end = """    {% endif %}
</div>

<!-- ============ 03: DEFECTS BY CATEGORY (TRADE) ============ -->"""

deep_dive_html = """    {% endif %}
</div>

<!-- ============ 03: AREA DEEP DIVE ============ -->
<div class="section">
    <div class="section-header">
        <span class="section-number">03</span>
        <span class="section-title">Area Deep Dive: Block Comparison</span>
    </div>
    <div class="clearfix">
        {% for area_info in combined_area_dive %}
        {% set outer_first = loop.first %}
        <div style="float: {% if loop.first %}left{% else %}right{% endif %}; width: 48%;">
            <div style="background: #F5F3EE; border-left: 3px solid {% if outer_first %}#C8963E{% else %}#3D6B8E{% endif %}; padding: 14px 16px;">
                <div style="font-size: 8px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #6B6B6B; margin-bottom: 2px;">{{ area_info.area }}</div>
                <div style="margin-bottom: 10px;">
                    <span style="font-family: 'Cormorant Garamond', Georgia, serif; font-size: 24px; font-weight: 300; color: #0A0A0A;">{{ area_info.total }}</span>
                    <span style="font-size: 10px; color: #9A9A9A; margin-left: 4px;">defects ({{ area_info.pct }}%)</span>
                </div>
                <table style="width: 100%; border-collapse: collapse;">
                    {% for d in area_info.defects %}
                    <tr>
                        <td style="width: 18px; vertical-align: top; padding: 4px 0;">
                            <div style="width: 18px; height: 18px; border-radius: 50%; background: {% if loop.first %}{% if outer_first %}#C8963E{% else %}#3D6B8E{% endif %}{% else %}#F5F3EE; border: 1px solid #E8E6E1{% endif %}; color: {% if loop.first %}white{% else %}#6B6B6B{% endif %}; text-align: center; line-height: 18px; font-size: 8px; font-weight: 600;">{{ loop.index }}</div>
                        </td>
                        <td style="padding: 4px 8px; vertical-align: top;">
                            <div style="font-size: 10px; color: #1A1A1A; margin-bottom: 3px;">{{ d.description }}</div>
                            <div style="height: 3px; background: #E8E6E1; border-radius: 2px; overflow: hidden;">
                                <div style="height: 3px; border-radius: 2px; width: {{ d.bar_pct }}%; background: {% if outer_first %}#C8963E{% else %}#3D6B8E{% endif %};"></div>
                            </div>
                        </td>
                        <td style="width: 70px; text-align: right; vertical-align: top; padding: 4px 0;">
                            <div style="font-size: 10px; font-weight: 600; color: #0A0A0A;">{{ d.total }}</div>
                            <div style="font-size: 8px; color: #9A9A9A;">
                                <span style="color: #C8963E;">B5: {{ d.b5 }}</span>
                                <span style="color: #3D6B8E; margin-left: 3px;">B6: {{ d.b6 }}</span>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
        </div>
        {% endfor %}
    </div>
    <div class="callout callout-gold" style="margin-top: 12px;">
        <strong>Key finding:</strong>
        {% if combined_area_dive|length >= 2 and combined_area_dive[0].defects and combined_area_dive[1].defects %}
        The most frequent defect in {{ combined_area_dive[0].area }} is {{ combined_area_dive[0].defects[0].description|lower }} ({{ combined_area_dive[0].defects[0].total }}: B5 {{ combined_area_dive[0].defects[0].b5 }}, B6 {{ combined_area_dive[0].defects[0].b6 }}).
        In {{ combined_area_dive[1].area }}, {{ combined_area_dive[1].defects[0].description|lower }} leads with {{ combined_area_dive[1].defects[0].total }}.
        {% endif %}
    </div>
</div>

<!-- ============ 04: DEFECTS BY CATEGORY (TRADE) ============ -->"""

if 'Area Deep Dive' not in html:
    if s02_end in html:
        html = html.replace(s02_end, deep_dive_html, 1)
        print('[6] Template: Area Deep Dive section added')
        changes += 1

        # Renumber 03->04, 04->05, 05->06, 06->07
        for old_n, new_n, label in [
            ('03', '04', 'Trade'),
            ('04', '05', 'Top Defects'),
            ('05', '06', 'Unit Chart'),
            ('06', '07', 'Unit Summary'),
        ]:
            html = html.replace(
                f'<span class="section-number">{old_n}</span>\n        <span class="section-title">Defects by Category (Trade)',
                f'<span class="section-number">{new_n}</span>\n        <span class="section-title">Defects by Category (Trade)') if old_n == '03' else html
            if old_n == '04':
                html = html.replace(
                    f'<span class="section-number">{old_n}</span>\n        <span class="section-title">Most Common',
                    f'<span class="section-number">{new_n}</span>\n        <span class="section-title">Most Common')
            elif old_n == '05':
                html = html.replace(
                    f'<span class="section-number">{old_n}</span>\n        <span class="section-title">Defect Count',
                    f'<span class="section-number">{new_n}</span>\n        <span class="section-title">Defect Count')
            elif old_n == '06':
                html = html.replace(
                    f'<span class="section-number">{old_n}</span>\n        <span class="section-title">Unit Summary',
                    f'<span class="section-number">{new_n}</span>\n        <span class="section-title">Unit Summary')
        print('[7] Template: sections renumbered 04-07')
        changes += 1
    else:
        print('[FAIL] S02 end marker not found')
else:
    print('[SKIP] Area Deep Dive already present')

# === 8. UNIT SUMMARY 2-STATUS (template) ===
old_status = """            {% if u.insp_status == 'reviewed' %}
            <span class="status-badge badge-reviewed">Reviewed</span>
            {% elif u.insp_status == 'approved' %}
            <span class="status-badge badge-approved">Approved</span>
            {% elif u.insp_status in ['certified', 'pending_followup'] %}
            <span class="status-badge badge-approved">{{ u.insp_status|replace('_', ' ')|title }}</span>
            {% elif u.insp_status == 'submitted' %}
            <span class="status-badge badge-submitted">Submitted</span>
            {% else %}
            <span class="status-badge" style="background: #F5F3EE; color: #6B6B6B;">{{ (u.insp_status or 'Not Started')|replace('_', ' ')|title }}</span>
            {% endif %}"""

new_status = """            {% if u.insp_status in ['approved', 'certified', 'pending_followup'] %}
            <span class="status-badge badge-approved">Issued to Site</span>
            {% else %}
            <span class="status-badge badge-reviewed">Inspected</span>
            {% endif %}"""

if 'Issued to Site' not in html:
    html = html.replace(old_status, new_status, 1)
    print('[8] Template: 2-status simplification')
    changes += 1
else:
    print('[SKIP] 2-status already applied')

with open(HTML, 'w') as f:
    f.write(html)
print(f'Lines: {len(html.splitlines())}')
print(f'Total changes: {changes}')
