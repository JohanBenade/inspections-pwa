#!/usr/bin/env python3
"""
Fix audit trail UX to match report page pattern.
Run on MacBook: python3 fix_audit_ux.py

1. inspector_audit.html: Replace View PDF + Download with Print + Download PDF (gold)
2. inspector_audit_pdf.html: Rewrite with fixed columns, sticky toolbar, matching button pattern
"""
import sys, os

if not os.path.exists('app/routes/analytics.py'):
    print('ERROR: Run from project root')
    sys.exit(1)

# =============================================================
# 1. FIX BUTTONS ON AUDIT PAGE
# =============================================================
print('--- Fixing inspector_audit.html ---')
with open('app/templates/analytics/inspector_audit.html', 'r') as f:
    html = f.read()

old_buttons = """            <a href="{{ url_for('analytics.inspector_audit_view', from_date=from_date, to_date=to_date) }}" target="_blank" style="padding: 0.4rem 1rem; background: #F5F3EE; color: #1A1A1A; border: 1px solid #DDD; border-radius: 4px; font-size: 0.82rem; font-weight: 600; cursor: pointer; text-decoration: none;">View PDF</a>
            <a href="{{ url_for('analytics.inspector_audit_pdf', from_date=from_date, to_date=to_date) }}" style="padding: 0.4rem 1rem; background: #1A1A1A; color: white; border: none; border-radius: 4px; font-size: 0.82rem; font-weight: 600; cursor: pointer; text-decoration: none;">Download</a>"""

new_buttons = """            <button onclick="window.print()" style="padding: 0.4rem 1rem; background: #F5F3EE; color: #1A1A1A; border: 1px solid #E8E6E1; border-radius: 4px; font-size: 0.82rem; font-weight: 600; cursor: pointer;">Print</button>
            <a href="{{ url_for('analytics.inspector_audit_pdf', from_date=from_date, to_date=to_date) }}" style="padding: 0.4rem 1rem; background: #C8963E; color: white; border: none; border-radius: 4px; font-size: 0.82rem; font-weight: 600; cursor: pointer; text-decoration: none;">Download PDF</a>"""

if old_buttons in html:
    html = html.replace(old_buttons, new_buttons, 1)
    with open('app/templates/analytics/inspector_audit.html', 'w') as f:
        f.write(html)
    print('  Buttons updated: Print + Download PDF (gold)')
else:
    print('  ERROR: Could not find current buttons')
    sys.exit(1)

# =============================================================
# 2. REWRITE PDF TEMPLATE (complete replacement)
# =============================================================
print('\n--- Rewriting inspector_audit_pdf.html ---')

pdf_template = r"""<!DOCTYPE html>
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
            content: "Monograph Architects | Inspector Audit Trail";
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

    .content-area {
        padding-top: 60px;
    }

    /* KPI cards as table */
    .kpi-table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 20px;
    }
    .kpi-cell {
        background: #F5F3EE;
        border-left: 3px solid #C8963E;
        padding: 10px 14px;
        text-align: left;
        vertical-align: top;
        width: 25%;
        border-right: 1px solid #E5E5E5;
    }
    .kpi-cell:last-child {
        border-right: none;
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

    /* Data tables with fixed column widths */
    .data-table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 12px;
        page-break-inside: auto;
        table-layout: fixed;
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
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .data-table tr:nth-child(even) td {
        background: rgba(245, 243, 238, 0.5);
    }

    /* Fixed column widths */
    .col-unit { width: 7%; }
    .col-zone { width: 22%; }
    .col-date { width: 14%; }
    .col-cycle { width: 8%; }
    .col-duration { width: 12%; }
    .col-defects { width: 10%; }
    .col-status { width: 12%; }

    .text-right { text-align: right; }
    .text-center { text-align: center; }

    .status-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 3px;
        font-size: 7.5pt;
        font-weight: 600;
    }

    /* Toolbar - sticky, screen only */
    .toolbar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 100;
        background: #1A1A1A;
        color: white;
        padding: 12px 20px;
        font-size: 10pt;
    }
    .toolbar a, .toolbar button {
        color: white;
        text-decoration: none;
        margin-right: 12px;
        padding: 6px 14px;
        border: 1px solid rgba(255,255,255,0.3);
        border-radius: 4px;
        font-size: 10pt;
        font-family: 'DM Sans', sans-serif;
        cursor: pointer;
        background: transparent;
    }
    .toolbar a:hover, .toolbar button:hover { background: rgba(255,255,255,0.1); }
    .toolbar .btn-pdf { background: #C8963E; border-color: #C8963E; }
    .toolbar .btn-pdf:hover { background: #D4A94F; border-color: #D4A94F; }

    @media print {
        .toolbar { display: none !important; }
        .content-area { padding-top: 0; }
        body { background: white; }
    }
</style>
</head>
<body>

<!-- Toolbar (sticky, hidden in print/PDF) -->
<div class="toolbar">
    <a href="{{ url_for('analytics.inspector_audit', from_date=from_date, to_date=to_date) }}">Back</a>
    <button onclick="window.print()">Print</button>
    <a href="{{ url_for('analytics.inspector_audit_pdf', from_date=from_date, to_date=to_date) }}" class="btn-pdf">Download PDF</a>
</div>

<div class="content-area">

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
    <colgroup>
        <col class="col-unit">
        <col class="col-zone">
        <col class="col-date">
        <col class="col-cycle">
        <col class="col-duration">
        <col class="col-defects">
        <col class="col-status">
    </colgroup>
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

</div>
</body>
</html>"""

with open('app/templates/analytics/inspector_audit_pdf.html', 'w') as f:
    f.write(pdf_template)
print('  inspector_audit_pdf.html rewritten')

print('\n=== ALL DONE ===')
print('git add -A && git commit -m "Match audit UX to report pattern: Print + Download PDF" && git push')
