#!/usr/bin/env python3
"""
Site Meeting Brief font sweep:
- Drop Cormorant Garamond from @import (DM Sans stays)
- Swap .report-title font-family Cormorant -> DM Sans

Existing size/weight/letter-spacing on .report-title left untouched
(style harmonisation deferred per §2.3, matching Batch Report Option A).

Run from repo root: python3 scripts/font_sweep_05_smb_apply.py
"""
from pathlib import Path

TARGET = Path("app/templates/analytics/site_meeting_brief.html")
assert TARGET.exists(), f"Template not found: {TARGET}"
content = TARGET.read_text()

# --- 1. Drop Cormorant from @import ---
old_import = "@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=DM+Sans:wght@400;500;600;700&display=swap');"
new_import = "@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');"
n = content.count(old_import)
assert n == 1, f"Expected 1 match for @import, found {n}"
content = content.replace(old_import, new_import)

# --- 2. Swap .report-title font-family ---
old_ff = 'font-family: "Cormorant Garamond", Georgia, serif;'
new_ff = "font-family: 'DM Sans', system-ui, sans-serif;"
n = content.count(old_ff)
assert n == 1, f"Expected 1 match for .report-title font-family, found {n}"
content = content.replace(old_ff, new_ff)

# --- Post-check: no Cormorant references remain in this file ---
assert "Cormorant" not in content, "Cormorant still present after swap"

TARGET.write_text(content)
print("SMB font sweep applied.")
print("  - @import: Cormorant dropped")
print("  - .report-title: font-family Cormorant -> DM Sans (size/weight untouched)")
