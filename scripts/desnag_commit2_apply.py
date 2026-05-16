#!/usr/bin/env python3
"""De-snag Report - Commit 2 (v2): clone OI template + adapt header, repoint routes.

v2 fix: analytics.batch_reports_picker appears in OI top nav at line 159,
so the post-assert must allow baseline+1 occurrences (inherited nav + new back-link).

Run from repo root:
    python3 scripts/desnag_commit2_apply.py

Idempotent: refuses to run if batch_desnag.html already exists.
"""
import os
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_TEMPLATE = os.path.join(REPO_ROOT, 'app', 'templates', 'analytics', 'outstanding_items.html')
NEW_TEMPLATE = os.path.join(REPO_ROOT, 'app', 'templates', 'analytics', 'batch_desnag.html')
ROUTES_FILE = os.path.join(REPO_ROOT, 'app', 'routes', 'analytics.py')


def main():
    if not os.path.exists(SRC_TEMPLATE):
        sys.exit("[FAIL] Source template not found: {}".format(SRC_TEMPLATE))
    if not os.path.exists(ROUTES_FILE):
        sys.exit("[FAIL] Routes file not found: {}".format(ROUTES_FILE))
    if os.path.exists(NEW_TEMPLATE):
        sys.exit("[FAIL] {} already exists - aborting (idempotency guard)".format(NEW_TEMPLATE))

    shutil.copy(SRC_TEMPLATE, NEW_TEMPLATE)
    print("[OK] Cloned outstanding_items.html -> batch_desnag.html")

    template_edits = [
        ("title tag",
         "<title>Outstanding Items - Power Park Phase 3</title>",
         "<title>De-snag Report - {{ batch_name }} - Power Park Phase 3</title>"),

        ("eyebrow Punch List",
         '<span class="sub">Punch List</span>',
         '<span class="sub">De-snag Report</span>'),

        ("PDF button URL",
         "<a href=\"{{ url_for('analytics.outstanding_items_pdf') }}\" class=\"btn-pdf\" onclick=\"this.textContent='Preparing...'\">Download PDF</a>",
         "<a href=\"{{ url_for('analytics.batch_desnag_pdf', batch_id=batch_id) }}\" class=\"btn-pdf\" onclick=\"this.textContent='Preparing...'\">Download PDF</a>"),

        ("H1 + subtitle + meta + caption block",
         '''<h1 class="report-title">Outstanding Items</h1>
<div class="report-subtitle">Power Park Student Housing &mdash; Phase 3</div>
<div class="report-meta">Live data &middot; {{ snapshot_label }} &middot; Scope: dwelling units only</div>
<div class="report-meta" style="margin-top: 4px;">Items still open on units in active de-snag. Snag carryovers and latent findings combined.</div>''',
         '''<h1 class="report-title">De-snag Report &mdash; {{ batch_name }}</h1>
<div class="report-subtitle">Power Park Student Housing &mdash; Phase 3</div>
<div class="report-meta">Created {{ batch_created }} &middot; Live data &middot; {{ snapshot_label }}</div>
<div class="report-meta" style="margin-top: 4px;">Open snag carryovers and latent findings on this batch's de-snagged units. Live.</div>'''),

        ("back-link HTML before report-header",
         '<div class="report-header">',
         '''<div class="no-print" style="margin-bottom: 8px;">
    <a href="{{ url_for('analytics.batch_reports_picker') }}" class="back-link">&larr; Batch Reports</a>
</div>
<div class="report-header">'''),

        ("back-link CSS after .meta .sub rule",
         '.report-header .meta .sub { color: #9A9A9A; }',
         '''.report-header .meta .sub { color: #9A9A9A; }
.back-link { display: inline-block; font-size: 9pt; color: #4A4A4A; text-decoration: none; }
.back-link:hover { color: #1A1A1A; }'''),
    ]

    with open(NEW_TEMPLATE, 'r') as f:
        tpl = f.read()

    baseline_picker = tpl.count('analytics.batch_reports_picker')
    print("[OK] Baseline 'batch_reports_picker' refs: {}".format(baseline_picker))

    for label, old, new in template_edits:
        count = tpl.count(old)
        if count != 1:
            sys.exit("[FAIL] Template edit '{}': anchor count = {} (expected 1)".format(label, count))
        tpl = tpl.replace(old, new, 1)
        print("[OK] Template edit applied: {}".format(label))

    if tpl.count('De-snag Report &mdash; {{ batch_name }}') != 1:
        sys.exit("[FAIL] H1 not exactly once after edits")
    if tpl.count('analytics.batch_desnag_pdf') != 1:
        sys.exit("[FAIL] PDF URL ref not exactly once after edits")
    expected_picker = baseline_picker + 1
    actual_picker = tpl.count('analytics.batch_reports_picker')
    if actual_picker != expected_picker:
        sys.exit("[FAIL] Expected {} picker refs (baseline {} + 1), got {}".format(
            expected_picker, baseline_picker, actual_picker))
    if tpl.count('.back-link {') != 1:
        sys.exit("[FAIL] Back-link CSS rule not exactly once after edits")
    print("[OK] Template post-asserts passed")

    with open(NEW_TEMPLATE, 'w') as f:
        f.write(tpl)
    print("[OK] Wrote batch_desnag.html ({} bytes)".format(len(tpl)))

    with open(ROUTES_FILE, 'r') as f:
        routes = f.read()

    view_old = """def batch_desnag_view(batch_id):
    \"\"\"De-snag Report - HTML view (per-batch, live).\"\"\"
    import datetime as _dt, base64 as _b64, os as _os
    from flask import current_app as _ca, abort
    _tenant = session.get('tenant_id', 'MONOGRAPH')
    data = _build_batch_desnag_data(_tenant, batch_id)
    if data is None:
        abort(404)
    data['is_pdf'] = False
    data['report_date'] = _dt.datetime.now().strftime('%d %B %Y')
    logo_path = _os.path.join(_ca.static_folder, 'monograph_logo.jpg')
    if _os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            data['logo_b64'] = _b64.b64encode(f.read()).decode()
    else:
        data['logo_b64'] = ''
    return render_template('analytics/outstanding_items.html', **data)"""

    view_new = view_old.replace(
        "return render_template('analytics/outstanding_items.html', **data)",
        "return render_template('analytics/batch_desnag.html', batch_id=batch_id, **data)"
    )

    pdf_old = """def batch_desnag_pdf(batch_id):
    \"\"\"De-snag Report - PDF download (per-batch, live).\"\"\"
    from app.services.pdf_playwright import html_to_pdf
    import datetime as _dt, base64 as _b64, os as _os
    from flask import current_app as _ca, abort
    _tenant = session.get('tenant_id', 'MONOGRAPH')
    data = _build_batch_desnag_data(_tenant, batch_id)
    if data is None:
        abort(404)
    data['is_pdf'] = True
    data['report_date'] = _dt.datetime.now().strftime('%d %B %Y')
    logo_path = _os.path.join(_ca.static_folder, 'monograph_logo.jpg')
    if _os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            data['logo_b64'] = _b64.b64encode(f.read()).decode()
    else:
        data['logo_b64'] = ''
    html_str = render_template('analytics/outstanding_items.html', **data)"""

    pdf_new = pdf_old.replace(
        "html_str = render_template('analytics/outstanding_items.html', **data)",
        "html_str = render_template('analytics/batch_desnag.html', batch_id=batch_id, **data)"
    )

    for label, old, new in [("view route", view_old, view_new), ("pdf route", pdf_old, pdf_new)]:
        count = routes.count(old)
        if count != 1:
            sys.exit("[FAIL] Route edit '{}': anchor count = {} (expected 1)".format(label, count))
        routes = routes.replace(old, new, 1)
        print("[OK] Route edit applied: {}".format(label))

    if routes.count("'analytics/batch_desnag.html'") != 2:
        sys.exit("[FAIL] batch_desnag.html should appear 2x in routes, got {}".format(
            routes.count("'analytics/batch_desnag.html'")))
    if routes.count("'analytics/outstanding_items.html'") != 2:
        sys.exit("[FAIL] outstanding_items.html should still appear 2x (for OI routes), got {}".format(
            routes.count("'analytics/outstanding_items.html'")))
    print("[OK] Route post-asserts passed")

    with open(ROUTES_FILE, 'w') as f:
        f.write(routes)
    print("[OK] Wrote analytics.py ({} bytes)".format(len(routes)))

    print("")
    print("=== Commit 2 complete ===")


if __name__ == '__main__':
    main()
