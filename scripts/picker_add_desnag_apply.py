#!/usr/bin/env python3
"""
Picker UI restructure (Commit 3):
- Adds De-snag Report as second View option alongside existing Site Briefing.
- Folds in Cormorant -> DM Sans H1 swap (missed in Phase 1; picker is a
  user-facing screen, even if not a "live report" template).

Run from repo root: python3 scripts/picker_add_desnag_apply.py
"""
from pathlib import Path

TARGET = Path("app/templates/analytics/batch_reports_picker.html")
assert TARGET.exists(), f"Template not found: {TARGET}"
content = TARGET.read_text()

# --- 1. H1: Cormorant -> DM Sans (inline style on <h1>) ---
old_h1_ff = "font-family: 'Cormorant Garamond', Georgia, serif;"
new_h1_ff = "font-family: 'DM Sans', system-ui, sans-serif;"
n = content.count(old_h1_ff)
assert n == 1, f"Expected 1 match for H1 font-family, found {n}"
content = content.replace(old_h1_ff, new_h1_ff)

# --- 2. Button cell: single [View] -> [Site Briefing] [De-snag Report] ---
old_btn = '<a href="{{ url_for(\'analytics.batch_briefing_view\', batch_id=b.id) }}" style="padding:0.35rem 0.8rem; font-size:0.8rem; font-weight:600; border-radius:6px; background:#F5F3EE; color:#1A1A1A; border:1px solid #e5e5e5; text-decoration:none;">View</a>'

new_btn = (
    '<a href="{{ url_for(\'analytics.batch_briefing_view\', batch_id=b.id) }}" '
    'style="padding:0.35rem 0.8rem; font-size:0.8rem; font-weight:600; border-radius:6px; '
    'background:#F5F3EE; color:#1A1A1A; border:1px solid #e5e5e5; text-decoration:none; '
    'margin-right:0.4rem;">Site Briefing</a>'
    '<a href="{{ url_for(\'analytics.batch_desnag_view\', batch_id=b.id) }}" '
    'style="padding:0.35rem 0.8rem; font-size:0.8rem; font-weight:600; border-radius:6px; '
    'background:#F5F3EE; color:#1A1A1A; border:1px solid #e5e5e5; text-decoration:none;">De-snag Report</a>'
)

n = content.count(old_btn)
assert n == 1, f"Expected 1 match for old button, found {n}"
content = content.replace(old_btn, new_btn)

# --- Post-checks ---
assert "Cormorant" not in content, "Cormorant still present after swap"
assert "analytics.batch_briefing_view" in content, "Site Briefing endpoint missing"
assert "analytics.batch_desnag_view" in content, "De-snag endpoint missing"

TARGET.write_text(content)
print("Picker UI: De-snag option added.")
print("  - H1: Cormorant -> DM Sans")
print("  - Report column: [Site Briefing] [De-snag Report] (was single [View])")
