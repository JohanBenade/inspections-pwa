#!/usr/bin/env python3
"""
Outstanding Items font sweep: Cormorant Garamond -> DM Sans
- Drops Cormorant from Google Fonts <link>
- .report-title: DM Sans 26pt/600
- .cover-stat .num: DM Sans 24pt/700 + lining-nums

Mirrors De-snag Report Commit 2.5 visual spec.
Run from repo root: python3 scripts/font_sweep_01_oi_apply.py
"""
from pathlib import Path

TARGET = Path("app/templates/analytics/outstanding_items.html")
assert TARGET.exists(), f"Template not found: {TARGET}"
content = TARGET.read_text()

# --- 1. Google Fonts <link>: drop Cormorant Garamond ---
old_link = '<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600;700&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">'
new_link = '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">'
n = content.count(old_link)
assert n == 1, f"Expected 1 match for font <link>, found {n}"
content = content.replace(old_link, new_link)

# --- 2. .report-title block ---
old_title = """.report-title {
    font-family: 'Cormorant Garamond', serif;
    font-weight: 500;
    font-size: 30pt;
    line-height: 1;
    margin: 0 0 4px 0;
    letter-spacing: -0.01em;
}"""
new_title = """.report-title {
    font-family: 'DM Sans', system-ui, sans-serif;
    font-weight: 600;
    font-size: 26pt;
    line-height: 1.1;
    margin: 0 0 4px 0;
    letter-spacing: -0.02em;
}"""
n = content.count(old_title)
assert n == 1, f"Expected 1 match for .report-title, found {n}"
content = content.replace(old_title, new_title)

# --- 3. .cover-stat .num block ---
old_num = """.cover-stat .num {
    font-family: 'Cormorant Garamond', serif;
    font-size: 28pt; font-weight: 600; line-height: 1;
    color: #C44D3F;
}"""
new_num = """.cover-stat .num {
    font-family: 'DM Sans', system-ui, sans-serif;
    font-size: 24pt;
    font-weight: 700;
    line-height: 1;
    color: #C44D3F;
    font-variant-numeric: lining-nums;
}"""
n = content.count(old_num)
assert n == 1, f"Expected 1 match for .cover-stat .num, found {n}"
content = content.replace(old_num, new_num)

# --- Post-check: no Cormorant references remain in this file ---
assert "Cormorant" not in content, "Cormorant still present after swap"

TARGET.write_text(content)
print("OI font sweep applied.")
print("  - Font <link>: Cormorant dropped")
print("  - .report-title: DM Sans 26pt/600, letter-spacing -0.02em, line-height 1.1")
print("  - .cover-stat .num: DM Sans 24pt/700 + lining-nums")
