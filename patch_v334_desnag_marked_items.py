#!/usr/bin/env python3
"""
patch_v334_desnag_marked_items.py

BUG: desnag_view (app/routes/inspection.py) builds the "Items to inspect"
section only for categories containing a PENDING item (pending_cats query).
Once a team lead marks every newly-visible (un-excluded) item in a category
(NTS / OK / N-I), no item is left 'pending', so the whole category drops out
of pending_cats and vanishes from the de-snag screen -- even though the count
queries (which use 'pending OR marked_at IS NOT NULL') still count those items,
producing area totals that disagree with the rendered checklist.

FIX: Widen the pending_cats WHERE clause to the SAME criterion already used by
the grand-total and per-area item queries in this function:
    AND ii.status = 'pending'
becomes
    AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL)

Single logical change. Nothing downstream changes -- items_raw load,
checklist build, is_carried_ok filter and counts already handle marked items.

Assert-guarded find/replace. Aborts if the anchor is not found exactly once.
"""

import io

PATH = "app/routes/inspection.py"

OLD = """        WHERE ii.inspection_id = ? AND ii.tenant_id = ?
          AND ii.status = 'pending'
          AND COALESCE(ii.has_prior_defects, 0) = 0
        ORDER BY at2.area_order, ct.category_order
    \"\"\", [inspection_id, tenant_id])"""

NEW = """        WHERE ii.inspection_id = ? AND ii.tenant_id = ?
          AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL)
          AND COALESCE(ii.has_prior_defects, 0) = 0
        ORDER BY at2.area_order, ct.category_order
    \"\"\", [inspection_id, tenant_id])"""

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

count = src.count(OLD)
assert count == 1, (
    "ABORT: expected exactly 1 occurrence of the pending_cats anchor, found %d. "
    "No changes written." % count
)

src = src.replace(OLD, NEW)

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

# Verify the new text is present exactly once and the old gate is gone
with io.open(PATH, "r", encoding="utf-8") as f:
    after = f.read()

assert "(ii.status = 'pending' OR ii.marked_at IS NOT NULL)\n          AND COALESCE(ii.has_prior_defects, 0) = 0\n        ORDER BY at2.area_order, ct.category_order" in after, \
    "ABORT: new clause not found after write."

print("OK: pending_cats gate widened to include marked newly-visible items.")
print("Changed file:", PATH)
