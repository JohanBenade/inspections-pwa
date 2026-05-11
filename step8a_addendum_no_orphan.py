#!/usr/bin/env python3
"""
Step 8a: Fix orphaned 'Addendum: Latent Defects Identified' title in PDF.

After Step 8 deployed, the addendum title can land at the very bottom of
a page (right after Kevin's signature), with the first latent note pushed
to the next page. Title and first note get visually separated.

Fix: add page-break-after: avoid to:
  1. The title <div class="defects-header-title">  -> keeps title with intro
  2. The intro paragraph                            -> keeps intro with first note
The first note already has class="no-break" (page-break-inside: avoid), so
title + intro + first note now form a unit that Chromium won't split.

No other elements affected -- inline style scoped to this one title/intro.
Idempotent.
"""
import sys
from pathlib import Path

TPL = Path("app/templates/pdf/defects_list.html")
if not TPL.exists():
    print(f"ERROR: {TPL} not found. Run from repo root.")
    sys.exit(1)

content = TPL.read_text()

if 'class="defects-header-title" style="page-break-after: avoid;"' in content:
    print("Already applied. No-op.")
    sys.exit(0)

# Anchor: the addendum title + intro paragraph as inserted by Step 8
old = '''        <div class="defects-header-title"><span>Addendum: Latent Defects Identified ({{ latent_summary.total }})</span></div>
        <p style="font-size: 8pt; font-style: italic; color: #666; margin: 4px 0 12px 0;">Defects identified by the team lead during cycle reviews. These fall outside the inspection scope but are recorded for rectification during the contract period.</p>'''

new = '''        <div class="defects-header-title" style="page-break-after: avoid;"><span>Addendum: Latent Defects Identified ({{ latent_summary.total }})</span></div>
        <p style="font-size: 8pt; font-style: italic; color: #666; margin: 4px 0 12px 0; page-break-after: avoid;">Defects identified by the team lead during cycle reviews. These fall outside the inspection scope but are recorded for rectification during the contract period.</p>'''

assert old in content, "Anchor not found in defects_list.html"
assert content.count(old) == 1, f"Anchor count != 1 (got {content.count(old)})"

content = content.replace(old, new)
TPL.write_text(content)
print(f"[OK] {TPL} updated.")
print("page-break-after: avoid added to addendum title + intro paragraph.")
print("\nVerify with:")
print(f'  grep -c "page-break-after: avoid" {TPL}')
print("  (expect at least 2 new occurrences; could be higher if other rules already use it)")
