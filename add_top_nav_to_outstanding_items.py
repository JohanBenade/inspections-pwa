#!/usr/bin/env python3
"""
Outstanding Items: add top nav bar to HTML view.

OI template is a standalone HTML document (doesn't extend base.html), so
the nav doesn't carry over by default. Inline a self-contained nav
matching base.html's structure and colours, gated by:
  - {% if not is_pdf %} so the PDF render is unaffected
  - @media print so browser print also hides it

Raw CSS, no Tailwind dependency.
"""
from pathlib import Path

TPL = Path("app/templates/analytics/outstanding_items.html")
assert TPL.exists()

# CSS for top nav, inserted just before </style>
CSS_OLD = """@media print { .no-print { display: none !important; } }
</style>"""

CSS_NEW = """@media print { .no-print { display: none !important; } }
.top-nav {
    background: #1e3a5f; color: #FFF;
    height: 56px; padding: 0 16px;
    display: flex; align-items: center; justify-content: space-between;
    font-family: 'DM Sans', system-ui, sans-serif; font-size: 14px;
    position: sticky; top: 0; z-index: 50;
}
.top-nav .left { display: flex; align-items: center; gap: 22px; flex-wrap: wrap; }
.top-nav .right { display: flex; align-items: center; gap: 14px; font-size: 13px; color: #D1D5DB; }
.top-nav a { color: #D1D5DB; text-decoration: none; }
.top-nav a:hover { color: #FFF; }
.top-nav .brand { color: #FFF; font-weight: 700; font-size: 17px; }
.top-nav .current { color: #FFF; }
.top-nav .role-badge { background: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 4px; font-size: 11px; color: #FFF; }
@media print { .top-nav { display: none !important; } }
</style>"""

# Nav HTML, inserted just after <body>
NAV_OLD = """<body>
<div class="report-wrap">"""

NAV_NEW = """<body>
{% if not is_pdf and current_user %}
<nav class="top-nav">
    <div class="left">
        <a href="{{ url_for('home') }}" class="brand">Monograph</a>
        {% if current_user.role in ['inspector', 'office_admin'] %}
            <a href="{{ url_for('home') }}">Home</a>
        {% endif %}
        {% if current_user.role in ['team_lead', 'manager', 'admin'] %}
            <a href="{{ url_for('batches.list_batches') }}">Batches</a>
            <a href="{{ url_for('analytics.batch_reports_picker') }}">Batch Reports</a>
            <a href="{{ url_for('analytics.pipeline_dashboard') }}">Pipeline</a>
            <a href="{{ url_for('analytics.site_meeting_brief_view') }}">Brief</a>
            <a href="{{ url_for('analytics.outstanding_items_view') }}" class="current">Outstanding</a>
        {% endif %}
        {% if current_user.role == 'team_lead' %}
            <a href="{{ url_for('certification.my_reviews') }}">Team Lead Reviews</a>
            <a href="{{ url_for('certification.my_inspections') }}">My Inspections</a>
            <a href="{{ url_for('approvals.cleanup') }}">Defects Cleanup</a>
        {% endif %}
        {% if current_user.role in ('office_admin', 'team_lead') %}
            <a href="{{ url_for('analytics.inspector_audit') }}">Inspector Log</a>
            <a href="{{ url_for('analytics.inspector_audit_units') }}">Unit Register</a>
        {% endif %}
        {% if current_user.role in ['manager', 'admin'] %}
            <a href="{{ url_for('approvals.pipeline') }}">Approvals</a>
            <a href="{{ url_for('approvals.cleanup') }}">Defects Cleanup</a>
            <a href="{{ url_for('analytics.inspector_audit') }}">Inspector Log</a>
            <a href="{{ url_for('analytics.login_status') }}">Login Status</a>
            {% if current_user.role == 'admin' %}
                <a href="{{ url_for('data_quality.descriptions') }}">Data Quality</a>
            {% endif %}
        {% endif %}
    </div>
    <div class="right">
        <span>{{ current_user.name }}</span>
        <span class="role-badge">{{ current_user.role }}</span>
        <a href="{{ url_for('logout') }}">Logout</a>
    </div>
</nav>
{% endif %}
<div class="report-wrap">"""


def main():
    src = TPL.read_text()

    if 'class="top-nav"' in src:
        print('[NO-OP] Already applied.')
        raise SystemExit(0)

    for old, new in [(CSS_OLD, CSS_NEW), (NAV_OLD, NAV_NEW)]:
        assert old in src, f"Anchor missing: {old[:80]!r}"
        assert src.count(old) == 1, f"Anchor not unique: {old[:80]!r}"
        src = src.replace(old, new)

    assert '<nav class="top-nav">' in src
    assert "{% if not is_pdf and current_user %}" in src
    assert '.top-nav {' in src

    TPL.write_text(src)
    print('[OK] Top nav added to outstanding_items.html.')


if __name__ == '__main__':
    main()
