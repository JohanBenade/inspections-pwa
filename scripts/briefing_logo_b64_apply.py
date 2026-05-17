#!/usr/bin/env python3
"""
Briefing helper: pass logo_b64 to render context (workstream D, scope:
Briefing only -- SMB excluded per operator).

Adds MONOGRAPH letterhead JPEG loading to both batch_briefing_view and
batch_briefing_pdf, mirroring the pattern already used in batch_desnag_view
and batch_desnag_pdf. After this commit, Site Briefing's letterhead will
render the same JPEG that De-snag Report renders -- closing the visual gap
between the two report headers.

Target: app/routes/analytics.py

Run from repo root:  python3 scripts/briefing_logo_b64_apply.py
"""
from pathlib import Path

TARGET = Path("app/routes/analytics.py")
src = TARGET.read_text(encoding="utf-8")
original = src

# ============================================================================
# EDIT 1: batch_briefing_view (around line 4779) -- add logo_b64 loading
# ============================================================================
OLD_VIEW = '''def batch_briefing_view(batch_id):
    """Batch site briefing - HTML view."""
    data = _build_briefing_data(batch_id)
    if data is None:
        return "Batch not found or no data.", 404
    data['is_pdf'] = False
    return render_template('analytics/briefing.html', **data)'''

NEW_VIEW = '''def batch_briefing_view(batch_id):
    """Batch site briefing - HTML view."""
    import base64 as _b64, os as _os
    from flask import current_app as _ca
    data = _build_briefing_data(batch_id)
    if data is None:
        return "Batch not found or no data.", 404
    data['is_pdf'] = False
    logo_path = _os.path.join(_ca.static_folder, 'monograph_logo.jpg')
    if _os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            data['logo_b64'] = _b64.b64encode(f.read()).decode()
    else:
        data['logo_b64'] = ''
    return render_template('analytics/briefing.html', **data)'''

count1 = src.count(OLD_VIEW)
assert count1 == 1, f"EDIT 1 anchor: expected 1 match, found {count1}"
src = src.replace(OLD_VIEW, NEW_VIEW)


# ============================================================================
# EDIT 2: batch_briefing_pdf (around line 4790) -- add logo_b64 loading
# ============================================================================
OLD_PDF = '''def batch_briefing_pdf(batch_id):
    """Batch site briefing - PDF download via Playwright."""
    from app.services.pdf_playwright import html_to_pdf
    data = _build_briefing_data(batch_id)
    if data is None:
        return "Batch not found or no data.", 404
    data['is_pdf'] = True
    html_str = render_template('analytics/briefing.html', **data)'''

NEW_PDF = '''def batch_briefing_pdf(batch_id):
    """Batch site briefing - PDF download via Playwright."""
    from app.services.pdf_playwright import html_to_pdf
    import base64 as _b64, os as _os
    from flask import current_app as _ca
    data = _build_briefing_data(batch_id)
    if data is None:
        return "Batch not found or no data.", 404
    data['is_pdf'] = True
    logo_path = _os.path.join(_ca.static_folder, 'monograph_logo.jpg')
    if _os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            data['logo_b64'] = _b64.b64encode(f.read()).decode()
    else:
        data['logo_b64'] = ''
    html_str = render_template('analytics/briefing.html', **data)'''

count2 = src.count(OLD_PDF)
assert count2 == 1, f"EDIT 2 anchor: expected 1 match, found {count2}"
src = src.replace(OLD_PDF, NEW_PDF)


# ============================================================================
# Verify + write
# ============================================================================
assert src != original, "No changes made to file"

# Post-checks: 2 new logo_path lookups, 4 new data['logo_b64'] assignments
assert src.count("monograph_logo.jpg") - original.count("monograph_logo.jpg") == 2, \
    "Expected 2 new monograph_logo.jpg references (one per briefing function)"

TARGET.write_text(src, encoding="utf-8")

print("OK: analytics.py patched.")
print(f"  Original size: {len(original):,} chars")
print(f"  New size:      {len(src):,} chars")
print(f"  Delta:         {len(src) - len(original):+,} chars")
