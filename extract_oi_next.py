#!/usr/bin/env python3
"""
Bundle extraction for the next build step:

  1. The CURRENT outstanding_items.html template (so header anchors are accurate)
  2. site_meeting_brief_pdf route from analytics.py (PDF pattern to mirror)
  3. site_meeting_brief_view route from analytics.py (for context)
  4. The main nav template (so I can place the nav link consistently)

Writes everything to /tmp/oi_next_dump.txt.
"""
import re
from pathlib import Path

OUT = Path("/tmp/oi_next_dump.txt")
chunks = []

def section(title, body):
    chunks.append(f"\n\n========== {title} ==========\n{body}\n")

# 1. Current outstanding_items.html
tpl = Path("app/templates/analytics/outstanding_items.html")
if tpl.exists():
    section("FILE: app/templates/analytics/outstanding_items.html", tpl.read_text())
else:
    section("FILE: outstanding_items.html", "NOT FOUND")

# 2 + 3. SMB routes from analytics.py
ana = Path("app/routes/analytics.py").read_text()

for name in ("site_meeting_brief_pdf", "site_meeting_brief_view",
             "outstanding_items_view", "_build_outstanding_items_data"):
    m = re.search(rf'\n(?:@[^\n]*\n)*def {name}\b.*?(?=\n(?:@[^\n]*\n)*def |\Z)',
                  ana, re.DOTALL)
    if m:
        section(f"FUNCTION: {name}", m.group(0))
    else:
        section(f"FUNCTION: {name}", "NOT FOUND")

# 4. Nav templates - try common locations
nav_candidates = [
    "app/templates/base.html",
    "app/templates/_nav.html",
    "app/templates/nav.html",
    "app/templates/layout.html",
    "app/templates/_base.html",
    "app/templates/_header.html",
    "app/templates/partials/nav.html",
    "app/templates/partials/_nav.html",
]
for path in nav_candidates:
    p = Path(path)
    if p.exists():
        section(f"FILE: {path}", p.read_text())

# 5. List anything in templates/ that mentions analytics nav items (best-effort)
hits = []
for p in Path("app/templates").rglob("*.html"):
    try:
        text = p.read_text()
    except Exception:
        continue
    if ('site-meeting-brief' in text or 'pipeline_dashboard' in text
            or 'inspector_audit' in text or "url_for('analytics" in text):
        hits.append(str(p))
section("CANDIDATE TEMPLATES referencing analytics URLs",
        "\n".join(sorted(set(hits))) or "none found")

OUT.write_text("".join(chunks))
print(f"[OK] Wrote {len(''.join(chunks))} chars to {OUT}")
print(f"Copy to Desktop: cp {OUT} ~/Desktop/")
