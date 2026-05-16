#!/usr/bin/env python3
"""De-snag Report - Commit 2.5: polish + font fixes (7 items).

Items addressed (per operator's discrepancy list):
  5. Back-link spacing tightened
  6. Date format normalised (ISO -> "13 May 2026")
  7. Batch identifier added to eyebrow as third line
  1, 4. .report-title font: Cormorant Garamond -> DM Sans (tuned size/weight)
  2, 3. .cover-stat .num font: Cormorant Garamond -> DM Sans + lining-nums

Scope: batch_desnag.html template + _build_batch_desnag_data helper in
analytics.py. Outstanding Items template and other reports are NOT touched.
The broader font sweep across all 7 surfaces is a separate later program.

Run from repo root:
    python3 scripts/desnag_commit25_apply.py
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(REPO_ROOT, 'app', 'templates', 'analytics', 'batch_desnag.html')
ROUTES = os.path.join(REPO_ROOT, 'app', 'routes', 'analytics.py')


def main():
    if not os.path.exists(TEMPLATE):
        sys.exit("[FAIL] Template not found: {}".format(TEMPLATE))
    if not os.path.exists(ROUTES):
        sys.exit("[FAIL] Routes file not found: {}".format(ROUTES))

    # === Template edits ===
    template_edits = [
        # Item 5: back-link wrapper margin 8px -> 2px
        ("back-link spacing",
         '<div class="no-print" style="margin-bottom: 8px;">\n    <a href="{{ url_for(\'analytics.batch_reports_picker\') }}" class="back-link">&larr; Batch Reports</a>',
         '<div class="no-print" style="margin-bottom: 2px;">\n    <a href="{{ url_for(\'analytics.batch_reports_picker\') }}" class="back-link">&larr; Batch Reports</a>'),

        # Item 7: add batch_name as third eyebrow line
        ("eyebrow batch ID line",
         '        {{ report_date }}<br>\n        <span class="sub">De-snag Report</span>',
         '        {{ report_date }}<br>\n        <span class="sub">De-snag Report</span><br>\n        <span class="sub">{{ batch_name }}</span>'),

        # Items 1+4: .report-title font swap
        ("report-title font",
         ".report-title {\n    font-family: 'Cormorant Garamond', serif;\n    font-weight: 500;\n    font-size: 30pt;\n    line-height: 1;\n    margin: 0 0 4px 0;\n    letter-spacing: -0.01em;\n}",
         ".report-title {\n    font-family: 'DM Sans', system-ui, sans-serif;\n    font-weight: 600;\n    font-size: 26pt;\n    line-height: 1.1;\n    margin: 0 0 4px 0;\n    letter-spacing: -0.02em;\n}"),

        # Items 2+3: .cover-stat .num font swap + lining-nums
        ("cover-stat .num font",
         ".cover-stat .num {\n    font-family: 'Cormorant Garamond', serif;\n    font-size: 28pt; font-weight: 600; line-height: 1;\n    color: #C44D3F;\n}",
         ".cover-stat .num {\n    font-family: 'DM Sans', system-ui, sans-serif;\n    font-size: 24pt; font-weight: 700; line-height: 1;\n    color: #C44D3F;\n    font-variant-numeric: lining-nums;\n}"),
    ]

    with open(TEMPLATE, 'r') as f:
        tpl = f.read()

    # Pre-asserts: every anchor exists exactly once
    for label, old, new in template_edits:
        count = tpl.count(old)
        if count != 1:
            sys.exit("[FAIL] Template anchor '{}': count = {} (expected 1)".format(label, count))
    print("[OK] All 4 template anchors verified unique")

    # Apply edits
    for label, old, new in template_edits:
        tpl = tpl.replace(old, new, 1)
        print("[OK] Template edit applied: {}".format(label))

    # Post-asserts on final template state
    if "Cormorant Garamond" in tpl:
        sys.exit("[FAIL] Cormorant Garamond still present in template after edits")
    if "font-variant-numeric: lining-nums" not in tpl:
        sys.exit("[FAIL] lining-nums declaration missing")
    if 'margin-bottom: 2px' not in tpl:
        sys.exit("[FAIL] back-link tightened margin missing")
    if tpl.count('<span class="sub">{{ batch_name }}</span>') != 1:
        sys.exit("[FAIL] eyebrow batch_name line not present exactly once")
    print("[OK] Template post-asserts passed")

    with open(TEMPLATE, 'w') as f:
        f.write(tpl)
    print("[OK] Wrote batch_desnag.html ({} bytes)".format(len(tpl)))

    # === Helper edit (date format) in analytics.py ===
    with open(ROUTES, 'r') as f:
        routes = f.read()

    helper_old = "    batch_created_raw = batch_row['created_at'] or ''\n    batch_created = batch_created_raw.split('T')[0].split(' ')[0] if batch_created_raw else ''"
    helper_new = """    batch_created = ''
    if batch_row['created_at']:
        try:
            _d = datetime.strptime(batch_row['created_at'].split('T')[0].split(' ')[0], '%Y-%m-%d')
            batch_created = '{} {} {}'.format(_d.day, _d.strftime('%B'), _d.year)
        except Exception:
            batch_created = batch_row['created_at']"""

    count = routes.count(helper_old)
    if count != 1:
        sys.exit("[FAIL] Helper date-format anchor: count = {} (expected 1)".format(count))
    print("[OK] Helper anchor verified unique")

    routes = routes.replace(helper_old, helper_new, 1)
    print("[OK] Helper edit applied: date format -> human readable")

    # Post-assert: new code present, old removed
    if "batch_created_raw" in routes:
        sys.exit("[FAIL] Old date-format code still present (batch_created_raw)")
    if "_d.strftime('%B')" not in routes:
        sys.exit("[FAIL] New date-format code not present")

    # Syntax check via compile
    try:
        compile(routes, ROUTES, 'exec')
    except SyntaxError as e:
        sys.exit("[FAIL] Modified routes file has syntax error: {}".format(e))
    print("[OK] Routes post-asserts passed (syntax compiles)")

    with open(ROUTES, 'w') as f:
        f.write(routes)
    print("[OK] Wrote analytics.py ({} bytes)".format(len(routes)))

    print("")
    print("=== Commit 2.5 complete ===")
    print("Items addressed: 5 (spacing), 6 (date format), 7 (eyebrow batch ID),")
    print("                 1+4 (.report-title font), 2+3 (.cover-stat .num font)")


if __name__ == '__main__':
    main()
