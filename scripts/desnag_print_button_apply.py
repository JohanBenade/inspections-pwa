#!/usr/bin/env python3
"""
De-snag Report: add Print button alongside Download PDF.
- Inserts .btn-print CSS rule (light #F5F3EE, matches .btn-pdf dimensions).
- Inserts <button onclick="window.print()"> before the existing PDF link.

Per memory rule: Print = light #F5F3EE, Download PDF = gold #C8963E.

Run from repo root: python3 scripts/desnag_print_button_apply.py
"""
from pathlib import Path

TARGET = Path("app/templates/analytics/batch_desnag.html")
assert TARGET.exists(), f"Template not found: {TARGET}"
content = TARGET.read_text()

# --- 1. Insert .btn-print CSS rule after .btn-pdf:hover ---
old_css_anchor = ".btn-pdf:hover { background: #B0822F; }"
new_css_block = (
    ".btn-pdf:hover { background: #B0822F; }\n"
    ".btn-print {\n"
    "    background: #F5F3EE; color: #1A1A1A; padding: 7px 14px;\n"
    "    border: 1px solid #E5E5E5; border-radius: 4px;\n"
    "    font-family: 'DM Sans', system-ui, sans-serif;\n"
    "    font-size: 9pt; font-weight: 600; letter-spacing: 0.3px;\n"
    "    cursor: pointer;\n"
    "}\n"
    ".btn-print:hover { background: #EAE7DD; }"
)
n = content.count(old_css_anchor)
assert n == 1, f"Expected 1 match for .btn-pdf:hover anchor, found {n}"
content = content.replace(old_css_anchor, new_css_block)

# --- 2. Insert <button> before <a class="btn-pdf"> in action-row ---
old_action = (
    '<div class="action-row no-print">\n'
    '    <a href="{{ url_for(\'analytics.batch_desnag_pdf\', batch_id=batch_id) }}" '
    'class="btn-pdf" onclick="this.textContent=\'Preparing...\'">Download PDF</a>\n'
    '</div>'
)
new_action = (
    '<div class="action-row no-print">\n'
    '    <button onclick="window.print()" class="btn-print">Print</button>\n'
    '    <a href="{{ url_for(\'analytics.batch_desnag_pdf\', batch_id=batch_id) }}" '
    'class="btn-pdf" onclick="this.textContent=\'Preparing...\'">Download PDF</a>\n'
    '</div>'
)
n = content.count(old_action)
assert n == 1, f"Expected 1 match for action-row block, found {n}"
content = content.replace(old_action, new_action)

# --- Post-checks ---
assert ".btn-print {" in content, ".btn-print CSS not added"
assert 'class="btn-print"' in content, "Print button HTML not added"

TARGET.write_text(content)
print("De-snag: Print button added.")
print("  - .btn-print CSS rule inserted after .btn-pdf:hover")
print("  - <button>Print</button> inserted before <a>Download PDF</a> in action-row")
