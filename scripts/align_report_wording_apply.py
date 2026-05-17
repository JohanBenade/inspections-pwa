#!/usr/bin/env python3
"""
Align wording on Site Briefing and De-snag Report.

Three changes in one commit:
1. briefing.html  H1: flip word order to "Site Briefing - {batch.name}"
2. briefing.html  caption: replace placeholder "Fortnightly..." with batch-status overview
3. batch_desnag.html  caption: replace with outstanding-items-per-unit wording

Idempotent via assert-guards. Aborts cleanly if state diverges from expected.
Run from repo root: python3 scripts/align_report_wording_apply.py
"""

from pathlib import Path

BRIEFING = Path("app/templates/analytics/briefing.html")
DESNAG = Path("app/templates/analytics/batch_desnag.html")


def replace_once(path, old, new, label):
    text = path.read_text()
    count = text.count(old)
    assert count == 1, f"{label}: expected 1 match in {path}, found {count}"
    path.write_text(text.replace(old, new))
    after = path.read_text()
    assert after.count(new) == 1, f"{label}: post-write missing new string"
    assert after.count(old) == 0, f"{label}: old string still present after write"
    print(f"OK  {label}")


# 1. Briefing H1 word order flip
replace_once(
    BRIEFING,
    '<h1 class="report-title">{{ batch.name }} Site Briefing</h1>',
    '<h1 class="report-title">Site Briefing &mdash; {{ batch.name }}</h1>',
    "briefing H1 flip",
)

# 2. Briefing caption (replace prev placeholder)
replace_once(
    BRIEFING,
    '<div class="report-meta" style="margin-top: 4px;">Fortnightly status briefing for Raubex site team.</div>',
    '<div class="report-meta" style="margin-top: 4px;">Batch status overview &mdash; defects raised, cleared, and still open. Live.</div>',
    "briefing caption",
)

# 3. De-snag caption (note apostrophe in "batch's" -> string uses double quotes)
replace_once(
    DESNAG,
    "<div class=\"report-meta\" style=\"margin-top: 4px;\">Open snag carryovers and latent findings on this batch's de-snagged units. Live.</div>",
    "<div class=\"report-meta\" style=\"margin-top: 4px;\">Outstanding items by unit &mdash; for contractor rectification. Live.</div>",
    "de-snag caption",
)

print("\nAll three changes applied. Verify with grep, then commit.")
