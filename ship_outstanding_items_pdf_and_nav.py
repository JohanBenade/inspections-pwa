#!/usr/bin/env python3
"""
Outstanding Items: header polish + PDF route + nav links.

Three files in one commit:
  1. app/templates/analytics/outstanding_items.html
     - Title: "Outstanding Items List" -> "Outstanding Items"
     - Add caption line (snag carryovers + latent findings combined)
     - Cover stat labels: Open Snag Items / Latent Defects / Units Affected
       with small grey sublabels
     - Small print-hidden "Download PDF" button at top
     - .no-print CSS rule

  2. app/routes/analytics.py
     - New outstanding_items_pdf() route mirroring site_meeting_brief_pdf

  3. app/templates/base.html
     - Desktop nav: "Outstanding" link in TL/manager/admin block, next to Brief
     - Mobile bottom nav: same, with icon
"""
from pathlib import Path

# ----------------------------------------------------------------------------
# 1. outstanding_items.html
# ----------------------------------------------------------------------------
TPL = Path("app/templates/analytics/outstanding_items.html")
assert TPL.exists()

TPL_PAIRS = [
    # Title tag
    (
        '<title>Outstanding Items List - Power Park Phase 3</title>',
        '<title>Outstanding Items - Power Park Phase 3</title>',
    ),
    # H1
    (
        '<h1 class="report-title">Outstanding Items List</h1>',
        '<h1 class="report-title">Outstanding Items</h1>',
    ),
    # Header sub tag
    (
        '<span class="sub">Site Punch List</span>',
        '<span class="sub">Punch List</span>',
    ),
    # Add .no-print rule and download-btn rule at end of <style>
    (
        '.footer {\n    margin-top: 24px;\n    padding-top: 8px;\n    border-top: 1px solid #E8E6E1;\n    font-size: 7pt; color: #9A9A9A; text-align: center;\n    letter-spacing: 0.5px;\n}\n</style>',
        '.footer {\n    margin-top: 24px;\n    padding-top: 8px;\n    border-top: 1px solid #E8E6E1;\n    font-size: 7pt; color: #9A9A9A; text-align: center;\n    letter-spacing: 0.5px;\n}\n.action-row { margin: 8px 0 14px 0; display: flex; gap: 8px; justify-content: flex-end; }\n.btn-pdf {\n    background: #C8963E; color: #FFF; padding: 7px 14px;\n    border-radius: 4px; text-decoration: none;\n    font-size: 9pt; font-weight: 600; letter-spacing: 0.3px;\n}\n.btn-pdf:hover { background: #B0822F; }\n@media print { .no-print { display: none !important; } }\n</style>',
    ),
    # Add Download PDF button just after report-header div, and add caption line
    (
        '<h1 class="report-title">Outstanding Items</h1>\n<div class="report-subtitle">Power Park Student Housing &mdash; Phase 3</div>\n<div class="report-meta">Live data &middot; {{ snapshot_label }} &middot; Scope: dwelling units only</div>',
        '<div class="action-row no-print">\n    <a href="{{ url_for(\'analytics.outstanding_items_pdf\') }}" class="btn-pdf" onclick="this.textContent=\'Preparing...\'">Download PDF</a>\n</div>\n\n<h1 class="report-title">Outstanding Items</h1>\n<div class="report-subtitle">Power Park Student Housing &mdash; Phase 3</div>\n<div class="report-meta">Live data &middot; {{ snapshot_label }} &middot; Scope: dwelling units only</div>\n<div class="report-meta" style="margin-top: 4px;">Items still open on units in active de-snag. Snag carryovers and latent findings combined.</div>',
    ),
    # Cover labels with sublabels
    (
        '<div class="num">{{ totals.open_defects }}</div>\n        <div class="label">Open Defects</div>',
        '<div class="num">{{ totals.open_defects }}</div>\n        <div class="label">Open Snag Items</div>\n        <div class="label" style="color: #B0B0B0; text-transform: none; letter-spacing: 0; font-size: 7pt; margin-top: 2px;">from C1, awaiting rectification</div>',
    ),
    (
        '<div class="num latent">{{ totals.latent_outstanding }}</div>\n        <div class="label">Latent Outstanding</div>',
        '<div class="num latent">{{ totals.latent_outstanding }}</div>\n        <div class="label">Latent Defects</div>\n        <div class="label" style="color: #B0B0B0; text-transform: none; letter-spacing: 0; font-size: 7pt; margin-top: 2px;">found by TLs during de-snag</div>',
    ),
    (
        '<div class="num units">{{ totals.units_affected }}</div>\n        <div class="label">Units Affected</div>',
        '<div class="num units">{{ totals.units_affected }}</div>\n        <div class="label">Units Affected</div>\n        <div class="label" style="color: #B0B0B0; text-transform: none; letter-spacing: 0; font-size: 7pt; margin-top: 2px;">in active de-snag</div>',
    ),
]


# ----------------------------------------------------------------------------
# 2. analytics.py - new PDF route
# ----------------------------------------------------------------------------
ANALYTICS = Path("app/routes/analytics.py")
assert ANALYTICS.exists()

# Anchor on the END of outstanding_items_view. Use a unique closing snippet.
ANALYTICS_OLD = """    return render_template('analytics/outstanding_items.html', **data)
"""

ANALYTICS_NEW = """    return render_template('analytics/outstanding_items.html', **data)


@analytics_bp.route('/outstanding-items/pdf')
@require_team_lead
def outstanding_items_pdf():
    \"\"\"Outstanding Items List - PDF download.\"\"\"
    from app.services.pdf_playwright import html_to_pdf
    import datetime as _dt, base64 as _b64, os as _os
    from flask import current_app as _ca
    _tenant = session.get('tenant_id', 'MONOGRAPH')
    data = _build_outstanding_items_data(_tenant)
    data['is_pdf'] = True
    data['report_date'] = _dt.datetime.now().strftime('%d %B %Y')
    logo_path = _os.path.join(_ca.static_folder, 'monograph_logo.jpg')
    if _os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            data['logo_b64'] = _b64.b64encode(f.read()).decode()
    else:
        data['logo_b64'] = ''
    html_str = render_template('analytics/outstanding_items.html', **data)
    footer = '''<div style="width: 100%; font-size: 8px; font-family: 'DM Sans', Helvetica, Arial, sans-serif; padding: 0 16mm; display: flex; justify-content: space-between; color: #9A9A9A;">
        <span>Confidential &mdash; Monograph Architects</span>
        <span>Power Park Student Housing &ndash; Phase 3</span>
        <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
    </div>'''
    pdf_bytes = html_to_pdf(html_str, footer_template=footer)
    resp = make_response(pdf_bytes)
    resp.headers['Content-Type'] = 'application/pdf'
    today_iso = _dt.datetime.now().strftime('%Y-%m-%d')
    resp.headers['Content-Disposition'] = 'attachment; filename=Outstanding_Items_{}.pdf'.format(today_iso)
    return resp
"""


# ----------------------------------------------------------------------------
# 3. base.html - nav links (desktop + mobile)
# ----------------------------------------------------------------------------
BASE = Path("app/templates/base.html")
assert BASE.exists()

# Desktop nav: add after Brief link, inside TL/manager/admin block
BASE_DESKTOP_OLD = """                        <a href="{{ url_for('analytics.site_meeting_brief_view') }}" class="text-sm text-gray-300 hover:text-white">Brief</a>
                        {% endif %}
                        {% if current_user.role == 'team_lead' %}"""

BASE_DESKTOP_NEW = """                        <a href="{{ url_for('analytics.site_meeting_brief_view') }}" class="text-sm text-gray-300 hover:text-white">Brief</a>
                        <a href="{{ url_for('analytics.outstanding_items_view') }}" class="text-sm text-gray-300 hover:text-white">Outstanding</a>
                        {% endif %}
                        {% if current_user.role == 'team_lead' %}"""

# Mobile bottom nav: add after Brief link block, inside TL/manager/admin block.
# Anchor on closing </a> + {% endif %} that wraps the team_lead-and-above mobile block.
BASE_MOBILE_OLD = """            <!-- Brief -->
            <a href="{{ url_for('analytics.site_meeting_brief_view') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/>
                </svg>
                <span class="text-xs mt-1">Brief</span>
            </a>
            {% endif %}"""

BASE_MOBILE_NEW = """            <!-- Brief -->
            <a href="{{ url_for('analytics.site_meeting_brief_view') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/>
                </svg>
                <span class="text-xs mt-1">Brief</span>
            </a>
            <!-- Outstanding Items -->
            <a href="{{ url_for('analytics.outstanding_items_view') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2M9 12h6m-6 4h6"/>
                </svg>
                <span class="text-xs mt-1">Outstanding</span>
            </a>
            {% endif %}"""


# ----------------------------------------------------------------------------
# Apply
# ----------------------------------------------------------------------------
def patch(path, pairs, idempotency_check=None):
    src = path.read_text()
    if idempotency_check and idempotency_check(src):
        print(f'[NO-OP] {path}: already applied.')
        return False
    for old, new in pairs:
        assert old in src, f'{path}: anchor missing\n    {old[:120]!r}'
        assert src.count(old) == 1, f'{path}: anchor not unique\n    {old[:120]!r}'
        src = src.replace(old, new)
    path.write_text(src)
    print(f'[OK] {path} patched ({len(pairs)} replacements).')
    return True


def main():
    patch(
        TPL,
        TPL_PAIRS,
        idempotency_check=lambda s: 'Open Snag Items' in s,
    )
    patch(
        ANALYTICS,
        [(ANALYTICS_OLD, ANALYTICS_NEW)],
        idempotency_check=lambda s: 'def outstanding_items_pdf' in s,
    )
    patch(
        BASE,
        [(BASE_DESKTOP_OLD, BASE_DESKTOP_NEW), (BASE_MOBILE_OLD, BASE_MOBILE_NEW)],
        idempotency_check=lambda s: 'analytics.outstanding_items_view' in s,
    )

    # Post-flight cross-file assertions
    assert 'outstanding_items_view' in BASE.read_text(), 'nav link missing'
    assert 'def outstanding_items_pdf' in ANALYTICS.read_text(), 'PDF route missing'
    assert 'Open Snag Items' in TPL.read_text(), 'header relabel missing'
    print('[ALL OK]')


if __name__ == '__main__':
    main()
