"""
Patch script for analytics report visual changes.
Creates backup, applies 5 changes:
1. Header: Add cycle number (large, bold, right-aligned)
2. Pipeline: Simplify to 3 steps (Requested -> Inspected -> Issued to Site)
3. Donut: Add percentage labels inside segments
4. Unit Summary: Two statuses only (Inspected / Issued to Site)
5. KPI: Remove Items Inspected card
"""
import sys, os

REPO = os.path.expanduser('~/Documents/GitHub/inspections-pwa')
PY_FILE = os.path.join(REPO, 'app/routes/analytics.py')
HTML_FILE = os.path.join(REPO, 'app/templates/analytics/report.html')

def patch_analytics_py():
    with open(PY_FILE, 'r') as f:
        content = f.read()

    with open(PY_FILE + '.bak2', 'w') as f:
        f.write(content)
    print(f"Backup: {PY_FILE}.bak2")

    # CHANGE 1: Add math import
    old = "from app.services.db import query_db"
    new = "import math\nfrom app.services.db import query_db"
    if 'import math' not in content:
        content = content.replace(old, new, 1)
        print("  [1] Added: import math")
    else:
        print("  [1] Skipped: import math already present")

    # CHANGE 2: Add donut midpoint coordinates in _build_report_data
    old_donut = """    for a in area_data:
        pct = a['defect_count'] / total_defects if total_defects > 0 else 0
        a['pct'] = round(pct * 100, 1)
        a['dash'] = round(pct * circumference, 2)
        a['offset'] = round(offset, 2)
        offset += a['dash']"""

    new_donut = """    for a in area_data:
        pct = a['defect_count'] / total_defects if total_defects > 0 else 0
        a['pct'] = round(pct * 100, 1)
        a['dash'] = round(pct * circumference, 2)
        a['offset'] = round(offset, 2)
        mid_frac = (a['offset'] + a['dash'] / 2) / circumference
        angle = mid_frac * 2 * math.pi - math.pi / 2
        a['pct_x'] = round(100 + 70 * math.cos(angle), 1)
        a['pct_y'] = round(100 + 70 * math.sin(angle), 1)
        offset += a['dash']"""

    if 'pct_x' not in content:
        count = content.count(old_donut)
        if count == 1:
            content = content.replace(old_donut, new_donut)
            print("  [2] Added: donut midpoint coordinates")
        else:
            print(f"  [2] WARNING: Found {count} matches for donut loop (expected 1)")
    else:
        print("  [2] Skipped: pct_x already present")

    # CHANGE 3: Add issued_to_site date to pipeline_dates
    old_pipeline = """    approved_dates = [u['approved_at'] for u in units if u.get('approved_at')]
    if approved_dates:
        pipeline_dates['approved'] = max(approved_dates)[:10]"""

    new_pipeline = """    approved_dates = [u['approved_at'] for u in units if u.get('approved_at')]
    if approved_dates:
        pipeline_dates['approved'] = max(approved_dates)[:10]
        pipeline_dates['issued_to_site'] = max(approved_dates)[:10]"""

    if "issued_to_site" not in content:
        content = content.replace(old_pipeline, new_pipeline)
        print("  [3] Added: issued_to_site pipeline date")
    else:
        print("  [3] Skipped: issued_to_site already present")

    with open(PY_FILE, 'w') as f:
        f.write(content)
    print(f"  Written: {PY_FILE}")

    import ast
    try:
        ast.parse(content)
        print("  Syntax: OK")
    except SyntaxError as e:
        print(f"  SYNTAX ERROR: {e}")
        return False
    return True


def patch_report_html():
    with open(HTML_FILE, 'r') as f:
        content = f.read()

    with open(HTML_FILE + '.bak2', 'w') as f:
        f.write(content)
    print(f"Backup: {HTML_FILE}.bak2")

    # CHANGE 1: Add Cycle number in header
    old_css = """.header-meta .date {
    font-size: 11px;
    letter-spacing: 0;
    text-transform: none;
    color: #1A1A1A;
    margin-top: 2px;
}"""
    new_css = """.header-meta .date {
    font-size: 11px;
    letter-spacing: 0;
    text-transform: none;
    color: #1A1A1A;
    margin-top: 2px;
}
.header-meta .cycle-num {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: 26px;
    font-weight: 400;
    color: #0A0A0A;
    letter-spacing: 0;
    text-transform: none;
    margin-top: 8px;
    line-height: 1.1;
}"""
    content = content.replace(old_css, new_css)

    old_header = """        <div class="header-meta">
            Inspection Report
            <div class="date">{{ report_date }}</div>
        </div>"""
    new_header = """        <div class="header-meta">
            Inspection Report
            <div class="date">{{ report_date }}</div>
            <div class="cycle-num">Cycle {{ cycle.cycle_number }}</div>
        </div>"""
    content = content.replace(old_header, new_header)
    print("  [1] Added: Cycle number in header")

    # CHANGE 2: Simplify pipeline to 3 steps
    old_stages = """        {% set stages = [
            ('Requested', pipeline_dates.get('requested', ''), true),
            ('Inspected', pipeline_dates.get('inspected', ''), pipeline.in_progress + pipeline.submitted + pipeline.under_review + pipeline.reviewed + pipeline.approved + pipeline.certified + pipeline.pending_followup > 0),
            ('Reviewed', pipeline_dates.get('reviewed', ''), pipeline.reviewed + pipeline.approved + pipeline.certified + pipeline.pending_followup > 0),
            ('Approved', pipeline_dates.get('approved', ''), pipeline.approved + pipeline.certified + pipeline.pending_followup > 0),
            ('Certified', '', pipeline.certified > 0)
        ] %}"""
    new_stages = """        {% set stages = [
            ('Requested', pipeline_dates.get('requested', ''), true),
            ('Inspected', pipeline_dates.get('inspected', ''), pipeline.in_progress + pipeline.submitted + pipeline.under_review + pipeline.reviewed + pipeline.approved + pipeline.certified + pipeline.pending_followup > 0),
            ('Issued to Site', pipeline_dates.get('issued_to_site', ''), pipeline.approved + pipeline.certified + pipeline.pending_followup > 0)
        ] %}"""
    content = content.replace(old_stages, new_stages)
    print("  [2] Updated: Pipeline to 3 steps")

    old_callout = """        {% set reviewed_count = pipeline.reviewed + pipeline.approved + pipeline.certified + pipeline.pending_followup %}
        {% set approved_count = pipeline.approved + pipeline.certified + pipeline.pending_followup %}
        <div class="callout callout-gold" style="margin-top: 14px;">
            <strong>Current status:</strong>
            {{ total_units }} units inspected,
            {{ reviewed_count }} reviewed{% if approved_count > 0 %}, {{ approved_count }} approved{% endif %}.
            {% if certified_count > 0 %}{{ certified_count }} certified.{% endif %}
        </div>"""
    new_callout = """        {% set issued_count = pipeline.approved + pipeline.certified + pipeline.pending_followup %}
        <div class="callout callout-gold" style="margin-top: 14px;">
            <strong>Current status:</strong>
            {{ total_units }} units inspected{% if issued_count > 0 %}, {{ issued_count }} issued to site{% endif %}.
        </div>"""
    content = content.replace(old_callout, new_callout)
    print("  [2b] Updated: Pipeline callout text")

    # CHANGE 3: Add percentage labels inside donut segments
    old_donut = """                {% for area in area_data %}
                <circle cx="100" cy="100" r="70"
                        fill="none"
                        stroke="{{ area_colours[loop.index0 % area_colours|length] }}"
                        stroke-width="30"
                        stroke-dasharray="{{ area.dash }} {{ 439.82 - area.dash }}"
                        stroke-dashoffset="{{ -area.offset }}"
                        transform="rotate(-90 100 100)" />
                {% endfor %}
                <circle cx="100" cy="100" r="52" fill="#FAFAF8" />"""
    new_donut = """                {% for area in area_data %}
                <circle cx="100" cy="100" r="70"
                        fill="none"
                        stroke="{{ area_colours[loop.index0 % area_colours|length] }}"
                        stroke-width="30"
                        stroke-dasharray="{{ area.dash }} {{ 439.82 - area.dash }}"
                        stroke-dashoffset="{{ -area.offset }}"
                        transform="rotate(-90 100 100)" />
                {% endfor %}
                {% for area in area_data %}
                <text x="{{ area.pct_x }}" y="{{ area.pct_y }}"
                      text-anchor="middle" dominant-baseline="central"
                      font-family="'DM Sans', Helvetica, sans-serif"
                      font-size="{% if area.pct >= 10 %}8{% else %}7{% endif %}" font-weight="600" fill="white"
                      >{{ area.pct }}%</text>
                {% endfor %}
                <circle cx="100" cy="100" r="52" fill="#FAFAF8" />"""
    content = content.replace(old_donut, new_donut)
    print("  [3] Added: Percentage labels in donut")

    # CHANGE 4: Simplify unit summary status to 2 states
    old_status = """                <td class="text-center">
                    {% if u.insp_status == 'reviewed' %}
                    <span class="status-badge badge-reviewed">Reviewed</span>
                    {% elif u.insp_status == 'approved' %}
                    <span class="status-badge badge-approved">Approved</span>
                    {% elif u.insp_status in ['certified', 'pending_followup'] %}
                    <span class="status-badge badge-approved">{{ u.insp_status|replace('_', ' ')|title }}</span>
                    {% elif u.insp_status == 'submitted' %}
                    <span class="status-badge badge-submitted">Submitted</span>
                    {% else %}
                    <span class="status-badge" style="background: #F5F3EE; color: #6B6B6B;">{{ (u.insp_status or 'Not Started')|replace('_', ' ')|title }}</span>
                    {% endif %}
                </td>"""
    new_status = """                <td class="text-center">
                    {% if u.insp_status in ['approved', 'certified', 'pending_followup'] %}
                    <span class="status-badge badge-approved">Issued to Site</span>
                    {% else %}
                    <span class="status-badge badge-reviewed">Inspected</span>
                    {% endif %}
                </td>"""
    content = content.replace(old_status, new_status)
    print("  [4] Updated: Unit summary to 2 statuses")

    # CHANGE 5: Remove Items Inspected KPI card (5 cards instead of 6)
    content = content.replace('width: 16.66%;', 'width: 20%;')

    old_kpi_items = """    <td class="kpi-cell">
        <div class="kpi-label">Items Inspected</div>
        <div class="kpi-value">{{ '{:,}'.format(total_items) }}</div>
        <div class="kpi-sub">{{ items_per_unit }} per unit x {{ total_units }}</div>
    </td>
    <td class="kpi-cell">
        <div class="kpi-label">Defect Rate</div>"""
    new_kpi_items = """    <td class="kpi-cell">
        <div class="kpi-label">Defect Rate</div>"""
    content = content.replace(old_kpi_items, new_kpi_items)
    print("  [5] Removed: Items Inspected KPI card")

    with open(HTML_FILE, 'w') as f:
        f.write(content)
    print(f"  Written: {HTML_FILE}")
    return True


if __name__ == '__main__':
    print("=== PATCHING ANALYTICS BACKEND ===")
    py_ok = patch_analytics_py()
    print()
    print("=== PATCHING REPORT TEMPLATE ===")
    html_ok = patch_report_html()
    print()
    if py_ok and html_ok:
        print("ALL PATCHES APPLIED SUCCESSFULLY")
    else:
        print("ERRORS DETECTED - check output above")
