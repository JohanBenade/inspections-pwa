#!/usr/bin/env python3
"""
Site Briefing font sweep (Option B):
- Add Google Fonts <link> to actually load DM Sans (was not loaded)
- Swap .briefing-title font-family from Cormorant Garamond -> DM Sans

Body remains Inter-declared (renders as system fallback since Inter
also isn't loaded). Style harmonisation beyond title deferred per §2.3.

Run from repo root: python3 scripts/font_sweep_04_briefing_apply.py
"""
from pathlib import Path

TARGET = Path("app/templates/analytics/briefing.html")
assert TARGET.exists(), f"Template not found: {TARGET}"
content = TARGET.read_text()

# --- 1. Insert Google Fonts <link> for DM Sans, between <title> and <style> ---
old_head = '<title>{{ batch.name }} Site Briefing &mdash; {{ report_date }}</title>\n<style>'
new_head = (
    '<title>{{ batch.name }} Site Briefing &mdash; {{ report_date }}</title>\n'
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">\n'
    '<style>'
)
n = content.count(old_head)
assert n == 1, f"Expected 1 match for <title>+<style> anchor, found {n}"
content = content.replace(old_head, new_head)

# --- 2. Swap .briefing-title font-family ---
old_ff = "font-family: 'Cormorant Garamond', Georgia, serif;"
new_ff = "font-family: 'DM Sans', system-ui, sans-serif;"
n = content.count(old_ff)
assert n == 1, f"Expected 1 match for .briefing-title font-family, found {n}"
content = content.replace(old_ff, new_ff)

# --- Post-check: no Cormorant references remain in this file ---
assert "Cormorant" not in content, "Cormorant still present after swap"

TARGET.write_text(content)
print("Site Briefing font sweep applied.")
print("  - <link> added: Google Fonts DM Sans 400-700 now loaded")
print("  - .briefing-title: Cormorant -> DM Sans (existing weight/size untouched)")
