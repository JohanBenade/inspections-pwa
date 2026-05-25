"""Patch v309 BUG #2: On reset, clear addressed_cycle_number for b/fwd
open defects marked 'Still Open' during this cycle.

Without this, a defect carried forward from an earlier cycle that the
current de-snag inspector marked 'Still Open' keeps its
addressed_cycle_number set to the current cycle even after a reset.
The next inspector inherits a stale 'addressed at this cycle' marker.

Run from repo root, AFTER patch_v309_bug1:
    python3 patch_v309_bug2_defect_still_open.py
"""
import sys

PATH = 'app/routes/batches.py'

OLD = '''        # Delete defects raised during this cycle (C1 rollback)
        db.execute("""
            DELETE FROM defect
            WHERE unit_id = ? AND raised_cycle_id = ? AND tenant_id = ?
        """, [bu['unit_id'], bu['cycle_id'], tenant_id])'''

NEW = '''        # Delete defects raised during this cycle (C1 rollback)
        db.execute("""
            DELETE FROM defect
            WHERE unit_id = ? AND raised_cycle_id = ? AND tenant_id = ?
        """, [bu['unit_id'], bu['cycle_id'], tenant_id])
        # Clear "Still Open" addressed marker on b/fwd defects (de-snag rollback)
        db.execute("""
            UPDATE defect
            SET addressed_cycle_number = NULL,
                updated_at = ?
            WHERE unit_id = ? AND tenant_id = ?
              AND raised_cycle_number < ?
              AND status = 'open'
              AND addressed_cycle_number = ?
        """, [now, bu['unit_id'], tenant_id, bu['cycle_number'], bu['cycle_number']])'''

with open(PATH, 'r') as f:
    content = f.read()

if NEW in content:
    print('SKIP: BUG #2 already applied to', PATH)
    sys.exit(0)

count = content.count(OLD)
assert count == 1, f'BUG #2: OLD string found {count} times (expected 1) in {PATH}'

content = content.replace(OLD, NEW)
assert NEW in content, 'BUG #2: NEW string missing after replace'

with open(PATH, 'w') as f:
    f.write(content)

print('OK: BUG #2 patch applied to', PATH)
