#!/usr/bin/env python3
"""
patch_v328.py - Inspector home shows desnag-aligned numbers for C2+ inspections.

Per UX rule: inspector home progress + defect indicator must match what the
inspector will see on the desnag screen they click into.

Adds a post-query override loop in app/__init__.py home() route:
  - For any row with cycle_number > 1, call _desnag_progress() and overwrite
    total_items, completed_items, defect_count, prior_open_defects with the
    desnag-cohort equivalents.
  - C1 rows untouched (no desnag flow at C1; carried_ok cohort stays correct).

Expected on unit 011 (C2):
  - Items progress bar: 123/125  (was 111/121)
  - Defect indicator:    5       (was 22)

The 22 = 17 new defects raised at C2 + 5 open priors. Under the new
alignment, the indicator surfaces only "still open" defects (matching
desnag's header pill) - the new defects raised this cycle are implicit
in the 125 total.

Single-edit script. Uses deferred import (inside the function) to avoid
any circular-import risk between __init__.py and app.routes.inspection.
"""

import sys

FILE = 'app/__init__.py'

with open(FILE, 'r') as f:
    content = f.read()

old = '''            inspections = [dict(r) for r in inspections]

            return render_template('inspector_home.html', inspections=inspections)'''

new = '''            inspections = [dict(r) for r in inspections]

            # v328: For C2+ inspections, override carried_ok cohort numbers with
            # desnag-cohort totals (defects + latents + newly-visible items) so
            # this card matches batch detail, live view, and the desnag screen.
            # C1 rows keep carried_ok cohort (no desnag flow at C1).
            from app.routes.inspection import _desnag_progress
            for insp in inspections:
                if (insp.get('cycle_number') or 0) > 1:
                    p = _desnag_progress(insp['unit_id'], tenant_id, insp['cycle_number'])
                    insp['total_items'] = p['total']
                    insp['completed_items'] = p['addressed']
                    insp['defect_count'] = p['still_open']
                    insp['prior_open_defects'] = 0

            return render_template('inspector_home.html', inspections=inspections)'''

occ = content.count(old)
assert occ == 1, f"FAIL: expected exactly 1 match, found {occ}"

content = content.replace(old, new, 1)

with open(FILE, 'w') as f:
    f.write(content)

print("v328 complete: 1 edit to app/__init__.py")
print("Next: grep verify import + git add/commit/push.")
