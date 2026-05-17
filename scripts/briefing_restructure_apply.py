#!/usr/bin/env python3
"""
Site Briefing header restructure (workstream B per HANDOVER_v299.md).

Direction A + Option X (locked decisions, no re-asking):
  - Strip outer .briefing-header block
  - Insert in-card header (back-link, letterhead, action-row, title) at top
    of <div class="doc">, matching the De-snag Report pattern
  - Add new CSS rules for in-card header components
  - Skip MONOGRAPH letterhead rendering for now (logo_b64 not yet in context;
    deferred to workstream D); the <img> tag is wrapped in {% if logo_b64 %}
    so it silently omits until the helper is updated.
  - Leave orphaned .briefing-header* CSS rules in place (dead code,
    cleanup deferred to a later commit)

Target: app/templates/analytics/briefing.html

Run from repo root:  python3 scripts/briefing_restructure_apply.py
"""
from pathlib import Path

TEMPLATE = Path("app/templates/analytics/briefing.html")
src = TEMPLATE.read_text(encoding="utf-8")
original = src

# ============================================================================
# EDIT 1: Strip outer .briefing-header block (lines ~386-396 + trailing blank)
# ============================================================================
OLD_OUTER_HEADER = """{% if not is_pdf %}
<div class="briefing-header">
  <a href="{{ url_for('analytics.batch_reports_picker') }}" class="back-link">&larr; Batch Reports</a>
  <h1 class="briefing-title">{{ batch.name }} Site Briefing</h1>
  <p class="briefing-subtitle">{{ report_date }} &middot; Power Park Student Housing Phase 3</p>
  <div class="briefing-actions">
    <button onclick="window.print()" class="btn btn-print">Print</button>
    <a href="{{ url_for('analytics.batch_briefing_pdf', batch_id=batch.id) }}" class="btn btn-pdf" onclick="var b=this; b.textContent='Preparing...'; b.style.opacity='0.7'; b.style.pointerEvents='none'; setTimeout(function(){ b.textContent='Download PDF'; b.style.opacity='1'; b.style.pointerEvents='auto'; }, 5000);">Download PDF</a>
  </div>
</div>
{% endif %}

"""

count1 = src.count(OLD_OUTER_HEADER)
assert count1 == 1, f"EDIT 1 anchor: expected 1 match, found {count1}"
src = src.replace(OLD_OUTER_HEADER, "")

# ============================================================================
# EDIT 2: Insert in-card header inside <div class="doc">
# ============================================================================
OLD_DOC_OPEN = """<div class="doc">

{% set FL = {0: 'Ground', 1: '1st Floor', 2: '2nd Floor'} %}"""

NEW_DOC_OPEN = """<div class="doc">

<div class="no-print" style="margin-bottom: 2px;">
  <a href="{{ url_for('analytics.batch_reports_picker') }}" class="back-link">&larr; Batch Reports</a>
</div>
<div class="report-header">
  <div>
    {% if logo_b64 %}<img src="data:image/jpeg;base64,{{ logo_b64 }}" alt="Monograph">{% endif %}
  </div>
  <div class="meta">
    {{ report_date }}<br>
    <span class="sub">Site Briefing</span><br>
    <span class="sub">{{ batch.name }}</span>
  </div>
</div>

<div class="action-row no-print">
  <button onclick="window.print()" class="btn-print">Print</button>
  <a href="{{ url_for('analytics.batch_briefing_pdf', batch_id=batch.id) }}" class="btn-pdf" onclick="this.textContent='Preparing...'">Download PDF</a>
</div>

<h1 class="report-title">{{ batch.name }} Site Briefing</h1>
<div class="report-subtitle">Power Park Student Housing &mdash; Phase 3</div>
<div class="report-meta">{{ report_date }} &middot; Live data</div>
<div class="report-meta" style="margin-top: 4px;">Fortnightly status briefing for Raubex site team.</div>

{% set FL = {0: 'Ground', 1: '1st Floor', 2: '2nd Floor'} %}"""

count2 = src.count(OLD_DOC_OPEN)
assert count2 == 1, f"EDIT 2 anchor: expected 1 match, found {count2}"
src = src.replace(OLD_DOC_OPEN, NEW_DOC_OPEN)

# ============================================================================
# EDIT 3: Insert new CSS rules in <style> block
# ============================================================================
OLD_CSS_ANCHOR = """.briefing-actions .btn-pdf {
  background: #C8963E;
  color: white;
  border: 1px solid #C8963E;
}

.intro {"""

NEW_CSS_INSERT = """.briefing-actions .btn-pdf {
  background: #C8963E;
  color: white;
  border: 1px solid #C8963E;
}

/* In-card header (Direction A restructure, matches De-snag pattern) */
.back-link { display: inline-block; font-size: 9pt; color: #4A4A4A; text-decoration: none; }
.back-link:hover { color: #1A1A1A; }
.report-header {
  display: flex; justify-content: space-between; align-items: flex-end;
  border-bottom: 2px solid #1A1A1A;
  padding-bottom: 8px; margin-bottom: 14px;
}
.report-header img { height: 32px; width: auto; }
.report-header .meta {
  text-align: right; font-size: 8pt; color: #6B6B6B;
  letter-spacing: 1.5px; text-transform: uppercase; line-height: 1.4;
}
.report-header .meta .sub { color: #9A9A9A; }
.report-title {
  font-family: 'DM Sans', system-ui, sans-serif;
  font-weight: 600; font-size: 26pt; line-height: 1.1;
  margin: 0 0 4px 0; letter-spacing: -0.02em;
}
.report-subtitle { font-size: 11pt; color: #1A1A1A; margin: 0 0 2px 0; }
.report-meta { font-size: 9pt; color: #6B6B6B; font-style: italic; margin: 0 0 4px 0; }
.action-row { margin: 8px 0 14px 0; display: flex; gap: 8px; justify-content: flex-end; }
.btn-pdf {
  background: #C8963E; color: #FFF;
  padding: 7px 14px; border-radius: 4px;
  text-decoration: none; font-size: 9pt; font-weight: 600;
  letter-spacing: 0.3px;
}
.btn-pdf:hover { background: #B0822F; }
.btn-print {
  background: #F5F3EE; color: #1A1A1A;
  padding: 7px 14px; border: 1px solid #E5E5E5; border-radius: 4px;
  font-family: 'DM Sans', system-ui, sans-serif;
  font-size: 9pt; font-weight: 600; letter-spacing: 0.3px; cursor: pointer;
}
.btn-print:hover { background: #EAE7DD; }
@media print { .no-print { display: none !important; } }

.intro {"""

count3 = src.count(OLD_CSS_ANCHOR)
assert count3 == 1, f"EDIT 3 anchor: expected 1 match, found {count3}"
src = src.replace(OLD_CSS_ANCHOR, NEW_CSS_INSERT)

# ============================================================================
# Verify + write
# ============================================================================
assert src != original, "No changes made to file"

# Post-check: the new top-level classes must be present
for tok in [
    'class="report-header"',
    'class="action-row no-print"',
    'class="report-title"',
    '.report-header {',
    '.report-title {',
    '@media print { .no-print { display: none !important; } }',
]:
    assert tok in src, f"Post-check failed: missing token {tok!r}"

# Post-check: the old outer block must be gone
assert '<div class="briefing-header">' not in src, "Old briefing-header block still present"
assert 'class="btn btn-print"' not in src, "Old btn-print class still present"
assert 'class="btn btn-pdf"' not in src, "Old btn-pdf class still present"

TEMPLATE.write_text(src, encoding="utf-8")

print("OK: briefing.html restructured.")
print(f"  Original size: {len(original):,} chars")
print(f"  New size:      {len(src):,} chars")
print(f"  Delta:         {len(src) - len(original):+,} chars")
