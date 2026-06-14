#!/usr/bin/env python3
"""
Installer for the "Top 10 Defects per Area" report.
RUN ON: MACBOOK, from repo root (~/Documents/GitHub/inspections-pwa).

What it does (idempotent, assert-guarded):
  1. Appends _build_top10_per_area_data() + the two routes to
     app/routes/analytics.py  (only if not already present).
  2. Writes the template to app/templates/analytics/top_10_per_area.html.

It does NOT touch nav (base.html) - that is a separate, manual step once
base.html structure is confirmed.

After running: review `git diff`, then commit + push.
"""
import os, sys

ANALYTICS = 'app/routes/analytics.py'
TEMPLATE_DIR = 'app/templates/analytics'
TEMPLATE = os.path.join(TEMPLATE_DIR, 'top_10_per_area.html')

# --- sanity: must run from repo root ---
assert os.path.exists(ANALYTICS), "Run from repo root; %s not found" % ANALYTICS
assert os.path.isdir(TEMPLATE_DIR), "%s not found" % TEMPLATE_DIR

# --- payloads (read from sidecar files placed next to this script) ---
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, 'build_top10_per_area.py')) as f:
    builder_src = f.read()
with open(os.path.join(here, 'routes_top10_per_area.py')) as f:
    routes_src = f.read()
with open(os.path.join(here, 'top_10_per_area.html')) as f:
    template_src = f.read()

MARKER = 'def _build_top10_per_area_data('

# --- 1. append builder + routes to analytics.py (idempotent) ---
with open(ANALYTICS) as f:
    content = f.read()

if MARKER in content:
    print("SKIP analytics.py: _build_top10_per_area_data already present.")
else:
    block = "\n\n# === Top 10 Defects per Area (C1 build-quality brief) ===\n\n" \
            + builder_src.rstrip() + "\n\n\n" + routes_src.rstrip() + "\n"
    with open(ANALYTICS, 'a') as f:
        f.write(block)
    # verify
    with open(ANALYTICS) as f:
        after = f.read()
    assert MARKER in after, "append failed: builder marker not found after write"
    assert "@analytics_bp.route('/build-quality')" in after, "view route missing after write"
    assert "@analytics_bp.route('/build-quality/pdf')" in after, "pdf route missing after write"
    print("OK analytics.py: appended builder + 2 routes.")

# --- 2. write template (overwrite is safe; it is a standalone file) ---
with open(TEMPLATE, 'w') as f:
    f.write(template_src)
with open(TEMPLATE) as f:
    t = f.read()
assert 'Top 10 Defects per Area' in t, "template write verify failed"
assert 'top10_per_area_pdf' in t, "template missing pdf url_for"
print("OK template: wrote %s (%d bytes)." % (TEMPLATE, len(t)))

print("\nDONE. Next:")
print("  git diff --stat")
print("  git add app/routes/analytics.py app/templates/analytics/top_10_per_area.html")
print("  git commit -m 'feat: Top 10 Defects per Area C1 build-quality brief'")
print("  git push")
print("\nNav link is NOT installed - separate step after base.html is confirmed.")
