#!/usr/bin/env python3
"""
Align Site Briefing + De-snag Report headers — bundled.

5 sub-changes across 3 files, one commit:
  1a. analytics.py: insert report_date computation in _build_batch_desnag_data
  1b. analytics.py: add 'report_date': report_date to its return dict
  2.  batch_desnag.html: meta line uses {date} . Live data (drops snapshot_label)
  3.  briefing.html: .doc gets padding-top: 14mm (matches De-snag's report-wrap)
  4.  briefing.html: body background #EFEEE9 -> #FFFFFF (white)

Idempotent via assert-guards. Aborts cleanly if state diverges.
Run from repo root: python3 scripts/align_report_headers_apply.py
"""

from pathlib import Path

ANALYTICS = Path("app/routes/analytics.py")
DESNAG_TPL = Path("app/templates/analytics/batch_desnag.html")
BRIEFING_TPL = Path("app/templates/analytics/briefing.html")


def replace_once(path, old, new, label):
    text = path.read_text()
    count = text.count(old)
    assert count == 1, f"{label}: expected 1 match in {path}, found {count}"
    path.write_text(text.replace(old, new))
    after = path.read_text()
    assert after.count(new) == 1, f"{label}: post-write missing new string"
    assert after.count(old) == 0, f"{label}: old string still present"
    print(f"OK  {label}")


# 1a. analytics.py: insert report_date computation right before the return dict.
#     Uses datetime.now() which works because the existing line 7635 uses
#     datetime.strptime() in the same scope (confirms `datetime` is the class).
replace_once(
    ANALYTICS,
    "            batch_created = batch_row['created_at']\n\n    return {\n        'snapshot_label': snapshot_label,",
    "            batch_created = batch_row['created_at']\n\n    report_date = datetime.now().strftime('%d %B %Y')\n\n    return {\n        'snapshot_label': snapshot_label,",
    "analytics.py: insert report_date computation",
)

# 1b. analytics.py: add 'report_date': report_date to the return dict
replace_once(
    ANALYTICS,
    "        'batch_created': batch_created,\n        'totals': {",
    "        'batch_created': batch_created,\n        'report_date': report_date,\n        'totals': {",
    "analytics.py: add report_date to return dict",
)

# 2. batch_desnag.html: meta line uses {date} . Live data
replace_once(
    DESNAG_TPL,
    '<div class="report-meta">Live data &middot; {{ snapshot_label }}</div>',
    '<div class="report-meta">{{ report_date }} &middot; Live data</div>',
    "desnag template: meta line",
)

# 3. briefing.html: .doc gets padding-top to match De-snag's report-wrap (14mm)
replace_once(
    BRIEFING_TPL,
    ".doc { max-width: 820px; margin: 0 auto; }",
    ".doc { max-width: 820px; margin: 0 auto; padding-top: 14mm; }",
    "briefing template: .doc padding-top",
)

# 4. briefing.html: body background cream -> white
replace_once(
    BRIEFING_TPL,
    "  background: #EFEEE9; color: #1A1A1A; line-height: 1.55;",
    "  background: #FFFFFF; color: #1A1A1A; line-height: 1.55;",
    "briefing template: body background white",
)

print("\nAll 5 sub-changes applied. Verify with grep, then commit.")
