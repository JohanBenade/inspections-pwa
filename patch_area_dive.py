"""
Patch: Add Area Deep Dive section (S03) to per-cycle report.
Two side-by-side cards showing top 3 defect types for top 2 areas.
Renumbers existing S03-S06 to S04-S07.
"""
import os

REPO = os.path.expanduser('~/Documents/GitHub/inspections-pwa')
PY_FILE = os.path.join(REPO, 'app/routes/analytics.py')
HTML_FILE = os.path.join(REPO, 'app/templates/analytics/report.html')


def patch_backend():
    with open(PY_FILE, 'r') as f:
        content = f.read()

    if 'area_deep_dive' in content:
        print('  [SKIP] area_deep_dive already present')
        return True

    # Insert after area_data donut computation, before trade_data query
    anchor = "    # --- Defects by category (trade) ---"

    new_code = """    # --- Area deep dive: top 3 defect types for top 2 areas ---
    area_deep_dive = []
    top_area_names = [a['area'] for a in area_data[:2]]
    for area_name in top_area_names:
        area_defects = _to_dicts(query_db(\"\"\"
            SELECT d.original_comment as description, COUNT(*) as count
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at2 ON ct.area_id = at2.id
            WHERE d.raised_cycle_id = ? AND d.tenant_id = ? AND d.status = 'open'
            AND at2.area_name = ?
            GROUP BY d.original_comment
            ORDER BY count DESC
            LIMIT 3
        \"\"\", [cycle_id, tenant_id, area_name]))
        area_total = next((a['defect_count'] for a in area_data if a['area'] == area_name), 0)
        area_pct = next((a['pct'] for a in area_data if a['area'] == area_name), 0)
        max_count = area_defects[0]['count'] if area_defects else 1
        for d in area_defects:
            d['bar_pct'] = round((d['count'] / max_count) * 100, 1)
            d['item_pct'] = round((d['count'] / area_total) * 100, 1) if area_total > 0 else 0
        area_deep_dive.append({
            'area': area_name,
            'total': area_total,
            'pct': area_pct,
            'defects': area_defects,
        })

    """ + anchor

    if anchor in content:
        content = content.replace(anchor, new_code)
        print('  [1] Added: area_deep_dive query')
    else:
        print('  [FAIL] Could not find trade anchor')
        return False

    # Add to return dict
    old_return = "        'area_colours': report_area_colours,"
    new_return = "        'area_deep_dive': area_deep_dive,\n        'area_colours': report_area_colours,"
    content = content.replace(old_return, new_return, 1)
    print('  [2] Added: area_deep_dive to return dict')

    with open(PY_FILE, 'w') as f:
        f.write(content)

    import ast
    try:
        ast.parse(content)
        print('  Syntax: OK')
    except SyntaxError as e:
        print(f'  SYNTAX ERROR: {e}')
        return False
    return True


def patch_template():
    with open(HTML_FILE, 'r') as f:
        content = f.read()

    if 'Area Deep Dive' in content:
        print('  [SKIP] Area Deep Dive section already present')
        return True

    # STEP 1: Insert new S03 section after S02 closing callout
    # Find the end of S02 (the callout div closing)
    s02_end_marker = """    {% endif %}
</div>

<!-- 03 DEFECTS BY CATEGORY (TRADE) -->"""

    new_section = """    {% endif %}
</div>

<!-- 03 AREA DEEP DIVE -->
<div class="section">
    <div class="section-header">
        <span class="section-num">03</span>
        <span class="section-title">Area Deep Dive</span>
    </div>
    <div class="section-divider"></div>
    <div class="clearfix">
        {% for area_info in area_deep_dive %}
        <div style="float: {% if loop.first %}left{% else %}right{% endif %}; width: 48%;">
            <div style="background: #F5F3EE; border-left: 3px solid {% if loop.first %}#C8963E{% else %}#3D6B8E{% endif %}; padding: 14px 16px;">
                <div style="font-size: 8px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; color: #6B6B6B; margin-bottom: 2px;">{{ area_info.area }}</div>
                <div style="margin-bottom: 10px;">
                    <span style="font-family: 'Cormorant Garamond', Georgia, serif; font-size: 24px; font-weight: 300; color: #0A0A0A;">{{ area_info.total }}</span>
                    <span style="font-size: 10px; color: #9A9A9A; margin-left: 4px;">defects ({{ area_info.pct }}%)</span>
                </div>
                <table style="width: 100%; border-collapse: collapse;">
                    {% for d in area_info.defects %}
                    <tr>
                        <td style="width: 18px; vertical-align: top; padding: 4px 0;">
                            <div style="width: 18px; height: 18px; border-radius: 50%; background: {% if loop.first %}{% if loop.parentloop.first %}#C8963E{% else %}#3D6B8E{% endif %}{% else %}#F5F3EE; border: 1px solid #E8E6E1{% endif %}; color: {% if loop.first %}white{% else %}#6B6B6B{% endif %}; text-align: center; line-height: 18px; font-size: 8px; font-weight: 600;">{{ loop.index }}</div>
                        </td>
                        <td style="padding: 4px 8px; vertical-align: top;">
                            <div style="font-size: 10px; color: #1A1A1A; margin-bottom: 3px;">{{ d.description }}</div>
                            <div style="height: 3px; background: #E8E6E1; border-radius: 2px; overflow: hidden;">
                                <div style="height: 3px; border-radius: 2px; width: {{ d.bar_pct }}%; background: {% if loop.parentloop.first %}#C8963E{% else %}#3D6B8E{% endif %};"></div>
                            </div>
                        </td>
                        <td style="width: 50px; text-align: right; vertical-align: top; padding: 4px 0;">
                            <div style="font-size: 10px; font-weight: 600; color: #0A0A0A;">{{ d.count }}</div>
                            <div style="font-size: 8px; color: #9A9A9A;">{{ d.item_pct }}%</div>
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
        {% if area_deep_dive|length >= 2 %}
        {{ area_deep_dive[0].area }} and {{ area_deep_dive[1].area }} combined account for {{ area_deep_dive[0].pct + area_deep_dive[1].pct }}% of all defects.
        The most frequent defect in {{ area_deep_dive[0].area }} is {{ area_deep_dive[0].defects[0].description|lower }} ({{ area_deep_dive[0].defects[0].count }} occurrences).
        {% endif %}
    </div>
</div>

<!-- 04 DEFECTS BY CATEGORY (TRADE) -->"""

    if s02_end_marker in content:
        content = content.replace(s02_end_marker, new_section)
        print('  [1] Added: Area Deep Dive section')
    else:
        print('  [FAIL] Could not find S02 end marker')
        return False

    # STEP 2: Renumber S04, S05, S06
    content = content.replace('<!-- 04 DEFECTS BY CATEGORY (TRADE) -->', '<!-- 04 DEFECTS BY CATEGORY (TRADE) -->')  # already done above
    content = content.replace("""        <span class="section-num">03</span>
        <span class="section-title">Defects by Category (Trade)</span>""",
        """        <span class="section-num">04</span>
        <span class="section-title">Defects by Category (Trade)</span>""")
    print('  [2] Renumbered: Trade -> 04')

    content = content.replace('<!-- 04 TOP DEFECT TYPES -->', '<!-- 05 TOP DEFECT TYPES -->')
    content = content.replace("""        <span class="section-num">04</span>
        <span class="section-title">Most Common Defect Types</span>""",
        """        <span class="section-num">05</span>
        <span class="section-title">Most Common Defect Types</span>""")
    print('  [3] Renumbered: Top Defects -> 05')

    content = content.replace('<!-- 05 DEFECT COUNT BY UNIT -->', '<!-- 06 DEFECT COUNT BY UNIT -->')
    content = content.replace("""        <span class="section-num">05</span>
        <span class="section-title">Defect Count by Unit</span>""",
        """        <span class="section-num">06</span>
        <span class="section-title">Defect Count by Unit</span>""")
    print('  [4] Renumbered: Unit Chart -> 06')

    content = content.replace('<!-- 06 UNIT SUMMARY TABLE -->', '<!-- 07 UNIT SUMMARY TABLE -->')
    content = content.replace("""        <span class="section-num">06</span>
        <span class="section-title">Unit Summary Table</span>""",
        """        <span class="section-num">07</span>
        <span class="section-title">Unit Summary Table</span>""")
    print('  [5] Renumbered: Unit Summary -> 07')

    with open(HTML_FILE, 'w') as f:
        f.write(content)
    print(f'  Lines: {len(content.splitlines())}')
    return True


if __name__ == '__main__':
    print('=== PATCHING BACKEND ===')
    py_ok = patch_backend()
    print()
    print('=== PATCHING TEMPLATE ===')
    html_ok = patch_template()
    print()
    if py_ok and html_ok:
        print('ALL PATCHES APPLIED SUCCESSFULLY')
    else:
        print('ERRORS - check output above')
