#!/usr/bin/env python3
"""
Step 8b: Replace the failed Step 8a orphan fix.

Step 8a added page-break-after: avoid to the addendum title + intro
paragraph. In practice this didn't keep the title with the first note --
instead Chromium broke INSIDE the intro paragraph (between '...for
rectification' and 'during the contract period.'), leaving the KITCHEN
note still on page 4 and the intro split across pages 3 and 4.

Fix: force the entire addendum onto a fresh page via page-break-before:
always on the outer wrapper. Clean section break, no orphan risk, no
mid-paragraph splits. Trade-off: some whitespace at bottom of page 3
below Kevin's signature -- acceptable for a formal Raubex document.

Also reverts the Step 8a inline page-break-after styles since they're
now redundant (and were the wrong tool for the job).

Idempotent.
"""
import sys
from pathlib import Path

TPL = Path("app/templates/pdf/defects_list.html")
if not TPL.exists():
    print(f"ERROR: {TPL} not found. Run from repo root.")
    sys.exit(1)

content = TPL.read_text()

if 'page-break-before: always;">' in content and 'class="defects-header-title"><span>Addendum: Latent' in content:
    # Both: outer wrapper has page-break-before: always AND title has no
    # inline style (Step 8a reverted). Already applied.
    print("Already applied. No-op.")
    sys.exit(0)

# ---- Edit 1: Outer wrapper -- flip page-break-before from auto to always ----
# NOTE: the existing Excluded Items addendum uses an identical inline style,
# so we must anchor on the preceding {% if latent_notes_list %} line to
# target only the Latent addendum.
old_wrapper = '''    {% if latent_notes_list %}
    <div style="margin-top: 30px; page-break-before: auto;">'''
new_wrapper = '''    {% if latent_notes_list %}
    <div style="margin-top: 30px; page-break-before: always;">'''
assert old_wrapper in content, "Wrapper anchor not found"
assert content.count(old_wrapper) == 1, f"Wrapper anchor count != 1 (got {content.count(old_wrapper)})"
content = content.replace(old_wrapper, new_wrapper)
print("  [1/3] Latent addendum wrapper -> page-break-before: always")

# ---- Edit 2: Revert Step 8a's inline style on title ----
old_title = '<div class="defects-header-title" style="page-break-after: avoid;"><span>Addendum: Latent Defects Identified ({{ latent_summary.total }})</span></div>'
new_title = '<div class="defects-header-title"><span>Addendum: Latent Defects Identified ({{ latent_summary.total }})</span></div>'
assert old_title in content, "Title anchor not found (Step 8a not applied?)"
assert content.count(old_title) == 1, f"Title anchor count != 1 (got {content.count(old_title)})"
content = content.replace(old_title, new_title)
print("  [2/3] Title -- reverted Step 8a inline style")

# ---- Edit 3: Revert Step 8a's inline addition to intro paragraph ----
old_intro = '<p style="font-size: 8pt; font-style: italic; color: #666; margin: 4px 0 12px 0; page-break-after: avoid;">Defects identified by the team lead during cycle reviews. These fall outside the inspection scope but are recorded for rectification during the contract period.</p>'
new_intro = '<p style="font-size: 8pt; font-style: italic; color: #666; margin: 4px 0 12px 0;">Defects identified by the team lead during cycle reviews. These fall outside the inspection scope but are recorded for rectification during the contract period.</p>'
assert old_intro in content, "Intro anchor not found (Step 8a not applied?)"
assert content.count(old_intro) == 1, f"Intro anchor count != 1 (got {content.count(old_intro)})"
content = content.replace(old_intro, new_intro)
print("  [3/3] Intro -- reverted Step 8a inline addition")

TPL.write_text(content)
print(f"\n[OK] {TPL} updated.")
print("\nVerify with:")
print(f'  grep "page-break-before: always" {TPL}')
print(f'  grep -c "page-break-after: avoid" {TPL}    # should not include the two we reverted')
