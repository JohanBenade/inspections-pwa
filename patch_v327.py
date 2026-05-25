#!/usr/bin/env python3
"""
patch_v327.py - Restrict desnag (C2+) items cohort to newly-visible only.

Per HANDOVER_v316 rule correction:
  De-snag screen shows ONLY:
    (1) defects b/fwd
    (2) latent defects b/fwd
    (3) items previously excluded but now ready for inspection
        (truly newly-visible: pending AND has_prior_defects=0)
  Items with priors (cleared OR open) belong entirely to the defect track.

Reverts the direction of v325/v326b. Adds
  AND COALESCE(ii.has_prior_defects, 0) = 0
to 5 desnag SQL sites in app/routes/inspection.py:

  1. pending_cats          ~L2270  - items section render (Bug 1 root)
  2. items_row             ~L2449  - grand totals denominator
  3. items_per_area        ~L2462  - per-area denominator
  4. _desnag_progress      ~L2790  - i_row helper (after defect action)
  5. _desnag_area_progress ~L2832  - i_row helper (after defect action)

Expected result on unit 011 desnag (3 cleared priors + 33 cleared this cycle
+ 2 unactioned + 0 latents + 0 newly-visible items remaining):
  - Items section empty
  - Progress reads N addressed / N+2 total, 2 outstanding (the 2 unactioned)
  - Per-area counts no longer inflated by carried-over items
"""

import sys

FILE = 'app/routes/inspection.py'

with open(FILE, 'r') as f:
    content = f.read()

# (name, old, new) - one logical change, 5 file edits.
# Each `old` is verified unique against the file before any write.
edits = []

# ---- Edit 1: pending_cats (items-section category lookup) ----
old1 = """          AND ii.status = 'pending'
        ORDER BY at2.area_order, ct.category_order"""
new1 = """          AND ii.status = 'pending'
          AND COALESCE(ii.has_prior_defects, 0) = 0
        ORDER BY at2.area_order, ct.category_order"""
edits.append(('pending_cats', old1, new1))

# ---- Edit 2: items_row (grand totals) ----
old2 = '''          AND ii.status != 'skipped'
          AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL)
    """, [inspection_id, tenant_id], one=True)'''
new2 = '''          AND ii.status != 'skipped'
          AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL)
          AND COALESCE(ii.has_prior_defects, 0) = 0
    """, [inspection_id, tenant_id], one=True)'''
edits.append(('items_row', old2, new2))

# ---- Edit 3: items_per_area ----
old3 = """          AND ii.status != 'skipped'
          AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL)
        GROUP BY at2.area_name"""
new3 = """          AND ii.status != 'skipped'
          AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL)
          AND COALESCE(ii.has_prior_defects, 0) = 0
        GROUP BY at2.area_name"""
edits.append(('items_per_area', old3, new3))

# ---- Edit 4: _desnag_progress.i_row ----
old4 = '''          AND ii.status != 'skipped'
          AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL)
    """, [unit_id, tenant_id, cycle_number], one=True)'''
new4 = '''          AND ii.status != 'skipped'
          AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL)
          AND COALESCE(ii.has_prior_defects, 0) = 0
    """, [unit_id, tenant_id, cycle_number], one=True)'''
edits.append(('_desnag_progress.i_row', old4, new4))

# ---- Edit 5: _desnag_area_progress.i_row ----
old5 = '''          AND ii.status != 'skipped'
          AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL)
          AND at2.area_name = ?
    """, [unit_id, tenant_id, cycle_number, area_name], one=True)'''
new5 = '''          AND ii.status != 'skipped'
          AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL)
          AND COALESCE(ii.has_prior_defects, 0) = 0
          AND at2.area_name = ?
    """, [unit_id, tenant_id, cycle_number, area_name], one=True)'''
edits.append(('_desnag_area_progress.i_row', old5, new5))

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

print(f"\nv327 complete: 5 edits to {FILE}")
print("Next: grep verify, then git add/commit/push.")
