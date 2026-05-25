#!/usr/bin/env python3
"""
patch_v329.py - latent_still_open mirrors v326a (defect_still_open) fix.

Two sites in app/routes/inspection.py compute "still open" latents using
the broken pattern (require addressed_cycle_number = current cycle, which
excludes unactioned latents where addressed_cycle_number IS NULL):

  1. L2510 Python: latent_still_open in desnag_view function
  2. L2811 SQL:    still_open SUM inside _desnag_progress.l_row

Mirror of v326a: drop the addressed_cycle_number gate. After v329 both
sites count all open latents (actioned-still-open + unactioned), matching
how defects are counted post-v326a.

Unit 011 has zero latents so zero visible impact today. Fix lands for
completeness so units with mixed-state latents render correctly.
"""

import sys

FILE = 'app/routes/inspection.py'

with open(FILE, 'r') as f:
    content = f.read()

edits = []

# ---- Edit 1: Python latent_still_open ----
old1 = "    latent_still_open = sum(1 for l in latents if l['addressed_cycle_number'] == cycle_number and l['rectified_at'] is None)"
new1 = "    latent_still_open = sum(1 for l in latents if l['rectified_at'] is None)  # v329: all open latents (actioned + unactioned)"
edits.append(('python latent_still_open', old1, new1))

# ---- Edit 2: SQL still_open inside _desnag_progress.l_row ----
# Drop the cycle-bound CASE filter; drop the corresponding parameter from binding list.
old2 = '''            SUM(CASE WHEN addressed_cycle_number = ? AND rectified_at IS NULL THEN 1 ELSE 0 END) as still_open
        FROM latent_area_note
        WHERE unit_id = ? AND tenant_id = ?
        AND (rectified_at IS NULL OR rectified_at_cycle_number = ?)
    """, [cycle_number, cycle_number, cycle_number, unit_id, tenant_id, cycle_number], one=True)'''
new2 = '''            SUM(CASE WHEN rectified_at IS NULL THEN 1 ELSE 0 END) as still_open
        FROM latent_area_note
        WHERE unit_id = ? AND tenant_id = ?
        AND (rectified_at IS NULL OR rectified_at_cycle_number = ?)
    """, [cycle_number, cycle_number, unit_id, tenant_id, cycle_number], one=True)'''
edits.append(('_desnag_progress.l_row.still_open', old2, new2))

# ---- Verify ALL matches unique BEFORE any write ----
print("Verifying matches...")
for name, old, new in edits:
    occ = content.count(old)
    assert occ == 1, f"FAIL: {name}: expected exactly 1 match, found {occ}"
    print(f"  ok: {name}")

# ---- Apply ----
print("\nApplying edits...")
for name, old, new in edits:
    content = content.replace(old, new, 1)
    print(f"  done: {name}")

with open(FILE, 'w') as f:
    f.write(content)

print(f"\nv329 complete: 2 edits to {FILE}")
print("Next: grep verify, then git add/commit/push.")
