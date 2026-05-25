"""Patch v312: Surface paused inspections on /certification/my-inspections.

The route's WHERE clause filtered by `i.status IN ('not_started', 'in_progress')`,
hiding inspections that the inspector themselves paused mid-cycle. Their
work then can't be reached from the list view even though they're still
the inspector on the record.

Fix: add 'paused' to the status IN clause.

Notes:
- Paused inspections that came from reset_unit Outcome B (unassign+keep)
  have inspector_id cleared, so they won't surface here anyway -- only
  inspector-self-paused inspections will, which is the intent.
- The function comment notes 'same view as inspector home' -- there
  may be an inspector-home route elsewhere with the same bug pattern.
  NOT fixing that here; logged for follow-up.

Run from repo root:
    python3 patch_v312_my_inspections_paused.py
"""
import sys

PATH = 'app/routes/certification.py'

OLD = "        AND i.status IN ('not_started', 'in_progress')"
NEW = "        AND i.status IN ('not_started', 'in_progress', 'paused')"

with open(PATH, 'r') as f:
    content = f.read()

if NEW in content:
    print('SKIP: v312 already applied to', PATH)
    sys.exit(0)

count = content.count(OLD)
assert count == 1, f'v312: OLD found {count} times in {PATH} (expected 1)'

content = content.replace(OLD, NEW)
assert NEW in content, 'v312: NEW missing after replace'

with open(PATH, 'w') as f:
    f.write(content)

print(f'OK: v312 patch applied to {PATH}')
