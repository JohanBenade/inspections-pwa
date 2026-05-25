#!/usr/bin/env python3
"""
patch_v330.py - Pipeline dashboard Certified KPI unifies formally-certified
and functionally-certified units.

Per business rule: a unit counts as "certified" on the dashboard if EITHER
  (1) unit.certified_at is set (formally certified by Kevin), OR
  (2) inspection.status in ('reviewed', 'approved', 'pending_followup')
      AND open defect count = 0 (functionally certified / handover-ready)

This unifies two previously-separate metrics:
  - L5613 certified_count (criterion 1)
  - L5615 handover_ready_count (criterion 2, introduced in v322)

Set-union avoids double-counting units that satisfy both.

handover_ready_count is retained for downstream consumers (L6405 export),
but the headline Certified KPI now reports the unified count.

Edge case: inspection.status of 'certified' or 'closed' is NOT in the
unit_max_completed filter, but units at those statuses always have
unit.certified_at set in practice, so they're captured by criterion (1).

unit_max_completed query unchanged (3 consumers untouched).
Template unchanged (already reads kpi.certified).
"""

import sys

FILE = 'app/routes/analytics.py'

with open(FILE, 'r') as f:
    content = f.read()

old = '''    # Headline metrics
    units_inspected = len(unit_max_completed)
    certified_count = sum(1 for u in all_units if u['certified_at'])
    # v322: HANDOVER-READY = inspected units with zero open defects (loose certification)
    handover_ready_count = sum(
        1 for uid in unit_max_completed.keys()
        if unit_open.get(uid, 0) == 0
    )'''

new = '''    # Headline metrics
    units_inspected = len(unit_max_completed)
    # v330: certified KPI unifies formally certified (unit.certified_at) and
    # functionally certified (reviewed-or-higher inspections with zero open defects).
    # Set-union avoids double-counting units that satisfy both criteria.
    _formal_certified_ids = set(u['id'] for u in all_units if u['certified_at'])
    _handover_ready_ids = set(
        uid for uid in unit_max_completed.keys() if unit_open.get(uid, 0) == 0
    )
    certified_count = len(_formal_certified_ids | _handover_ready_ids)
    handover_ready_count = len(_handover_ready_ids)'''

occ = content.count(old)
assert occ == 1, f"FAIL: expected exactly 1 match, found {occ}"

content = content.replace(old, new, 1)

with open(FILE, 'w') as f:
    f.write(content)

print("v330 complete: 1 edit to app/routes/analytics.py")
print("Next: grep verify, then git add/commit/push.")
