#!/usr/bin/env python3
"""
Batch Report font sweep: drop unused Cormorant Garamond from @import.
Template is already 100% on DM Sans; Cormorant was loaded but never used.
No selector changes (style harmonisation deferred per §2.3).

Run from repo root: python3 scripts/font_sweep_02_batch_report_apply.py
"""
from pathlib import Path

TARGET = Path("app/templates/analytics/report_batch.html")
assert TARGET.exists(), f"Template not found: {TARGET}"
content = TARGET.read_text()

# --- Drop Cormorant Garamond from @import url() ---
old_import = "@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=DM+Sans:wght@400;500;600;700&display=swap');"
new_import = "@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');"
n = content.count(old_import)
assert n == 1, f"Expected 1 match for @import, found {n}"
content = content.replace(old_import, new_import)

# --- Post-check: no Cormorant references remain in this file ---
assert "Cormorant" not in content, "Cormorant still present after swap"

TARGET.write_text(content)
print("Batch Report font sweep applied.")
print("  - @import: Cormorant dropped (was unused dead code)")
print("  - No selector changes; existing DM Sans styling untouched per §2.3 deferral")
