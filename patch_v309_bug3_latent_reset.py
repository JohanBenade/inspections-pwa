"""Patch v309 BUG #3: On reset, also unwind latent_area_note changes
made during this cycle.

Before this patch, the reset block in reset_unit never touched
latent_area_note at all. Two consequences:
  - Latents marked Rectified this cycle stayed Rectified after reset.
  - Latents marked 'Still Open' this cycle kept addressed_cycle_number
    pointing at the current cycle.

The 'Delete all captured work' UI promise was therefore broken.

This patch adds two UPDATE statements:
  1. Undo Rectified-this-cycle: clear rectified_at, rectified_at_cycle_id,
     rectified_at_cycle_number, rectified_by, rectified_by_role,
     addressed_cycle_number, refresh last_edited_at.
  2. Clear addressed_cycle_number on unrectified latents marked
     'Still Open' this cycle.

Run from repo root, AFTER patch_v309_bug2 (anchors on the BUG #2 block):
    python3 patch_v309_bug3_latent_reset.py
"""
import sys

PATH = 'app/routes/batches.py'

OLD = '''        # Clear "Still Open" addressed marker on b/fwd defects (de-snag rollback)
        db.execute("""
            UPDATE defect
            SET addressed_cycle_number = NULL,
                updated_at = ?
            WHERE unit_id = ? AND tenant_id = ?
              AND raised_cycle_number < ?
              AND status = 'open'
              AND addressed_cycle_number = ?
        """, [now, bu['unit_id'], tenant_id, bu['cycle_number'], bu['cycle_number']])'''

NEW = '''        # Clear "Still Open" addressed marker on b/fwd defects (de-snag rollback)
        db.execute("""
            UPDATE defect
            SET addressed_cycle_number = NULL,
                updated_at = ?
            WHERE unit_id = ? AND tenant_id = ?
              AND raised_cycle_number < ?
              AND status = 'open'
              AND addressed_cycle_number = ?
        """, [now, bu['unit_id'], tenant_id, bu['cycle_number'], bu['cycle_number']])
        # Undo latents marked Rectified this cycle (de-snag rollback)
        db.execute("""
            UPDATE latent_area_note
            SET rectified_at = NULL,
                rectified_at_cycle_id = NULL,
                rectified_at_cycle_number = NULL,
                rectified_by = NULL,
                rectified_by_role = NULL,
                addressed_cycle_number = NULL,
                last_edited_at = ?
            WHERE unit_id = ? AND tenant_id = ?
              AND rectified_at_cycle_number = ?
        """, [now, bu['unit_id'], tenant_id, bu['cycle_number']])
        # Clear "Still Open" addressed marker on b/fwd unrectified latents
        db.execute("""
            UPDATE latent_area_note
            SET addressed_cycle_number = NULL,
                last_edited_at = ?
            WHERE unit_id = ? AND tenant_id = ?
              AND rectified_at IS NULL
              AND addressed_cycle_number = ?
        """, [now, bu['unit_id'], tenant_id, bu['cycle_number']])'''

MARKER = 'Undo latents marked Rectified this cycle'

with open(PATH, 'r') as f:
    content = f.read()

if MARKER in content:
    print('SKIP: BUG #3 already applied to', PATH)
    sys.exit(0)

count = content.count(OLD)
assert count == 1, (
    f'BUG #3: OLD string found {count} times (expected 1) in {PATH} '
    f'-- has patch_v309_bug2 been applied first?'
)

content = content.replace(OLD, NEW)
assert MARKER in content, 'BUG #3: marker missing after replace'

with open(PATH, 'w') as f:
    f.write(content)

print('OK: BUG #3 patch applied to', PATH)
