"""Patch v309 BUG #1: Filter non_pending_items count by marked_at IS NOT NULL.

Excludes carried-OK items (status='ok' but marked_at IS NULL, inherited
from a prior cycle) from the 'X items marked' label shown on the
unassign/reassign confirm panel.

Run from repo root:
    python3 patch_v309_bug1_items_marked.py
"""
import sys

PATH = 'app/routes/batches.py'

OLD = '''        row = query_db("""
            SELECT COUNT(*) AS c FROM inspection_item
            WHERE inspection_id = ? AND status NOT IN ('pending','skipped')
        """, [insp['id']], one=True)'''

NEW = '''        row = query_db("""
            SELECT COUNT(*) AS c FROM inspection_item
            WHERE inspection_id = ?
              AND status NOT IN ('pending','skipped')
              AND marked_at IS NOT NULL
        """, [insp['id']], one=True)'''

with open(PATH, 'r') as f:
    content = f.read()

if NEW in content:
    print('SKIP: BUG #1 already applied to', PATH)
    sys.exit(0)

count = content.count(OLD)
assert count == 1, f'BUG #1: OLD string found {count} times (expected 1) in {PATH}'

content = content.replace(OLD, NEW)
assert NEW in content, 'BUG #1: NEW string missing after replace'

with open(PATH, 'w') as f:
    f.write(content)

print('OK: BUG #1 patch applied to', PATH)
