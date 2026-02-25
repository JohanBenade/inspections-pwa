#!/usr/bin/env python3
"""
Fix Audit Trail PDF Feature
Run on MacBook (already in project dir): python3 fix_audit_pdf.py

Changes:
1. analytics.py: Extract _build_audit_data_dict(), add /audit/view and /audit/pdf routes
2. inspector_audit.html: Remove back link, replace Print button with View PDF + Download
3. Create inspector_audit_pdf.html (standalone WeasyPrint-compatible template)
"""
import sys
import os

# Safety check - must be in project root
if not os.path.exists('app/routes/analytics.py'):
    print('ERROR: Run this from the project root directory')
    sys.exit(1)

errors = []

# =============================================================
# 1. MODIFY analytics.py
# =============================================================
print('--- Modifying app/routes/analytics.py ---')

with open('app/routes/analytics.py', 'r') as f:
    content = f.read()

# 1a. Replace function declaration (route+decorator+def+docstring -> just def+docstring)
old_header = """@analytics_bp.route('/audit')
@require_manager
def inspector_audit():
    \"\"\"Inspector Audit Trail - payment verification page.\"\"\""""

new_header = """def _build_audit_data_dict():
    \"\"\"Shared data builder for inspector audit trail.\"\"\""""

if old_header not in content:
    errors.append('Could not find inspector_audit function header')
else:
    content = content.replace(old_header, new_header, 1)
    print('  Replaced function header -> _build_audit_data_dict()')

# 1b. Replace return render_template with return dict + 3 route functions
old_return = """    return render_template('analytics/inspector_audit.html',
        inspectors=inspectors,
        total_units=total_units,
        total_defects=total_defects,
        inspector_count=len(inspectors),
        from_date=from_date,
        to_date=to_date,
        period_label=period_label,
    )"""

new_return = """    return dict(
        inspectors=inspectors,
        total_units=total_units,
        total_defects=total_defects,
        inspector_count=len(inspectors),
        from_date=from_date,
        to_date=to_date,
        period_label=period_label,
    )


@analytics_bp.route('/audit')
@require_manager
def inspector_audit():
    \"\"\"Inspector Audit Trail - payment verification page.\"\"\"
    data = _build_audit_data_dict()
    return render_template('analytics/inspector_audit.html', **data)


@analytics_bp.route('/audit/view')
@require_manager
def inspector_audit_view():
    \"\"\"Standalone HTML view for audit trail PDF.\"\"\"
    data = _build_audit_data_dict()
    from datetime import datetime as dt
    data['now'] = dt.now().strftime('%Y-%m-%d %H:%M')
    return render_template('analytics/inspector_audit_pdf.html', **data)


@analytics_bp.route('/audit/pdf')
@require_manager
def inspector_audit_pdf():
    \"\"\"Download audit trail as PDF.\"\"\"
    data = _build_audit_data_dict()
    from datetime import datetime as dt
    data['now'] = dt.now().strftime('%Y-%m-%d %H:%M')
    from weasyprint import HTML
    html_str = render_template('analytics/inspector_audit_pdf.html', **data)
    pdf_bytes = HTML(string=html_str, base_url=request.host_url).write_pdf()
    resp = make_response(pdf_bytes)
    resp.headers['Content-Type'] = 'application/pdf'
    period = data.get('period_label', '').replace(' ', '_') or 'all'
    resp.headers['Content-Disposition'] = f'attachment; filename=inspector_audit_{period}.pdf'
    return resp"""

if old_return not in content:
    errors.append('Could not find inspector_audit return statement')
else:
    content = content.replace(old_return, new_return, 1)
    print('  Replaced return -> dict + 3 route functions')

if not errors:
    with open('app/routes/analytics.py', 'w') as f:
        f.write(content)
    print('  analytics.py saved')

# =============================================================
# 2. MODIFY inspector_audit.html
# =============================================================
print('\n--- Modifying app/templates/analytics/inspector_audit.html ---')

with open('app/templates/analytics/inspector_audit.html', 'r') as f:
    html = f.read()

# 2a. Remove back link
old_back = '    <a href="javascript:history.back()" class="no-print inline-block text-xs text-blue-600 hover:text-blue-800 mb-2">&larr; Back</a>'
if old_back in html:
    html = html.replace(old_back, '', 1)
    print('  Removed back link')
else:
    # Try without leading spaces
    old_back2 = '<a href="javascript:history.back()" class="no-print inline-block text-xs text-blue-600 hover:text-blue-800 mb-2">&larr; Back</a>'
    if old_back2 in html:
        html = html.replace(old_back2, '', 1)
        print('  Removed back link (alt match)')
    else:
        errors.append('Could not find back link in template')

# 2b. Replace Print button with View PDF + Download
old_button = '            <button onclick="window.print()" style="padding: 0.4rem 1rem; background: #1A1A1A; color: white; border: none; border-radius: 4px; font-size: 0.82rem; font-weight: 600; cursor: pointer;">Print / PDF</button>'

new_buttons = """            <a href="{{ url_for('analytics.inspector_audit_view', from_date=from_date, to_date=to_date) }}" target="_blank" style="padding: 0.4rem 1rem; background: #F5F3EE; color: #1A1A1A; border: 1px solid #DDD; border-radius: 4px; font-size: 0.82rem; font-weight: 600; cursor: pointer; text-decoration: none;">View PDF</a>
            <a href="{{ url_for('analytics.inspector_audit_pdf', from_date=from_date, to_date=to_date) }}" style="padding: 0.4rem 1rem; background: #1A1A1A; color: white; border: none; border-radius: 4px; font-size: 0.82rem; font-weight: 600; cursor: pointer; text-decoration: none;">Download</a>"""

if old_button in html:
    html = html.replace(old_button, new_buttons, 1)
    print('  Replaced Print button with View PDF + Download')
else:
    errors.append('Could not find Print/PDF button in template')

if not errors:
    with open('app/templates/analytics/inspector_audit.html', 'w') as f:
        f.write(html)
    print('  inspector_audit.html saved')

# =============================================================
# 3. CREATE inspector_audit_pdf.html (standalone PDF template)
# =============================================================
print('\n--- Creating app/templates/analytics/inspector_audit_pdf.html ---')

pdf_template = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Inspector Audit Trail{% if period_label %} - {{ period_label }}{% endif %}</title>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700&family=DM+Sans:wght@400;500;600;700&display=swap');

    @page {
        size: A4 landscape;
        margin: 15mm 18mm 18mm 18mm;
        @bottom-center {
            content: "Monograph Architects | Inspector Audit Trail | Generated " attr(data-date);
            font-family: 'DM Sans', sans-serif;
            font-size: 8pt;
            color: #9A9A9A;
        }
        @bottom-right {
            content: "Page " counter(page) " of " counter(pages);
            font-family: 'DM Sans', sans-serif;
            font-size: 8pt;
            color: #9A9A9A;
        }
    }

    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
        font-family: 'DM Sans', sans-serif;
        color: #1A1A1A;
        font-size: 9pt;
        line-height: 1.4;
        background: #FAFAF8;
        print-color-adjust: exact;
        -webkit-print-color-adjust: exact;
    }

    h1 {
        font-family: 'Cormorant Garamond', serif;
        font-size: 22pt;
        font-weight: 700;
        color: #0A0A0A;
        margin-bottom: 4px;
    }

    .subtitle {
        font-size: 10pt;
        color: #6B6B6B;
        margin-bottom: 16px;
    }

    .header-line {
        border-bottom: 2px solid #0A0A0A;
        margin-bottom: 16px;
    }

    /* KPI cards as table */
    .kpi-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 10px 0;
        margin-bottom: 20px;
    }
    .kpi-cell {
        background: #F5F3EE;
        border-left: 3px solid #C8963E;
        padding: 10px 14px;
        text-align: left;
        vertical-align: top;
        width: 25%;
    }
    .kpi-value {
        font-family: 'Cormorant Garamond', serif;
        font-size: 20pt;
        font-weight: 700;
        color: #0A0A0A;
    }
    .kpi-label {
        font-size: 8pt;
        color: #6B6B6B;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Inspector section */
    .inspector-header {
        border-left: 4px solid #C8963E;
        padding: 6px 0 6px 12px;
        margin: 18px 0 8px 0;
        page-break-inside: avoid;
    }
    .inspector-name {
        font-family: 'Cormorant Garamond', serif;
        font-size: 14pt;
        font-weight: 600;
        color: #0A0A0A;
    }
    .inspector-stats {
        font-size: 8pt;
        color: #6B6B6B;
    }

    /* Data tables */
    .data-table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 12px;
        page-break-inside: auto;
    }
    .data-table thead { page-break-after: avoid; }
    .data-table tr { page-break-inside: avoid; }
    .data-table th {
        background: #0A0A0A;
        color: #FAFAF8;
        padding: 6px 10px;
        text-align: left;
        font-size: 8pt;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .data-table td {
        padding: 5px 10px;
        border-bottom: 1px solid #E5E5E5;
        font-size: 9pt;
    }
    .data-table tr:nth-child(even) td {
        background: rgba(245, 243, 238, 0.5);
    }
    .text-right { text-align: right; }
    .text-center { text-align: center; }

    .status-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 3px;
        font-size: 7.5pt;
        font-weight: 600;
    }

    .toolbar {
        background: #1A1A1A;
        color: white;
        padding: 10px 20px;
        margin: -15px -18px 20px -18px;
        font-size: 10pt;
    }
    .toolbar a {
        color: white;
        text-decoration: none;
        margin-right: 16px;
        padding: 4px 12px;
        border: 1px solid rgba(255,255,255,0.3);
        border-radius: 4px;
    }
    .toolbar a:hover { background: rgba(255,255,255,0.1); }

    @media print {
        .toolbar { display: none; }
        body { background: white; }
    }
</style>
</head>
<body>

<!-- Toolbar (hidden in print/PDF) -->
<div class="toolbar">
    <a href="{{ url_for('analytics.inspector_audit', from_date=from_date, to_date=to_date) }}">&larr; Back</a>
    <a href="{{ url_for('analytics.inspector_audit_pdf', from_date=from_date, to_date=to_date) }}">Download PDF</a>
    <a href="javascript:window.print()">Print</a>
</div>

<!-- Header -->
<h1>Inspector Audit Trail</h1>
<div class="subtitle">
    Power Park Student Housing Phase 3
    {% if period_label %} | {{ period_label }}{% endif %}
    {% if now %} | Generated {{ now }}{% endif %}
</div>
<div class="header-line"></div>

<!-- KPI Cards -->
<table class="kpi-table"><tr>
    <td class="kpi-cell">
        <div class="kpi-value">{{ inspector_count }}</div>
        <div class="kpi-label">Inspectors</div>
    </td>
    <td class="kpi-cell">
        <div class="kpi-value">{{ total_units }}</div>
        <div class="kpi-label">Units Inspected</div>
    </td>
    <td class="kpi-cell">
        <div class="kpi-value">{{ total_defects }}</div>
        <div class="kpi-label">Total Defects</div>
    </td>
    <td class="kpi-cell">
        <div class="kpi-value">{{ (total_defects / total_units)|round(1) if total_units else 0 }}</div>
        <div class="kpi-label">Avg Defects / Unit</div>
    </td>
</tr></table>

<!-- Inspector Sections -->
{% for inspector in inspectors %}
<div class="inspector-header" style="border-left-color: {{ inspector.colour }};">
    <div class="inspector-name">{{ inspector.name }}</div>
    <div class="inspector-stats">
        {{ inspector.unit_count }} units | {{ inspector.total_defects }} defects | Avg {{ inspector.avg_defects }}/unit
        {% if inspector.date_range %} | {{ inspector.date_range }}{% endif %}
    </div>
</div>

<table class="data-table">
    <thead>
        <tr>
            <th>Unit</th>
            <th>Zone</th>
            <th>Date</th>
            <th>Cycle</th>
            <th>Duration</th>
            <th class="text-right">Defects</th>
            <th class="text-center">Status</th>
        </tr>
    </thead>
    <tbody>
        {% for unit in inspector.units %}
        <tr>
            <td><strong>{{ unit.unit_number }}</strong></td>
            <td>{{ unit.zone }}</td>
            <td>{{ unit.inspection_date }}</td>
            <td>{{ unit.cycle }}</td>
            <td>{{ unit.duration }}</td>
            <td class="text-right"><strong>{{ unit.defect_count }}</strong></td>
            <td class="text-center">
                <span class="status-badge" style="background: {{ unit.status_bg }}; color: {{ unit.status_colour }};">
                    {{ unit.status_label }}
                </span>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endfor %}

</body>
</html>"""

os.makedirs('app/templates/analytics', exist_ok=True)
with open('app/templates/analytics/inspector_audit_pdf.html', 'w') as f:
    f.write(pdf_template)
print('  inspector_audit_pdf.html created')

# =============================================================
# FINAL REPORT
# =============================================================
print('\n=== RESULT ===')
if errors:
    print('ERRORS (changes NOT saved):')
    for e in errors:
        print(f'  - {e}')
    sys.exit(1)
else:
    print('All changes applied successfully.')
    print('\nNext steps:')
    print('  git add -A && git commit -m "Add audit trail View PDF + Download feature" && git push')
