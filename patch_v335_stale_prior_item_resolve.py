#!/usr/bin/env python3
"""
patch_v335_stale_prior_item_resolve.py

BUG (the stale prior-defect orphan, traced from source this thread):
When a C1 prior defect is cleared during a C2+ de-snag via desnag_address
(action='cleared'), the code updates only the `defect` row. The matching
`inspection_item` row stays status='pending'. Because the de-snag render
path keeps any item whose status == 'pending' (is_pending is an include
condition), the now-resolved item keeps rendering as an UNMARKED, tappable
MS/NTS row -- even though its only prior defect is cleared. Those are the
unmarked items on screen.

WHY THE COLUMN IS NOT TOUCHED:
inspection_item.has_prior_defects (the stored column) is read ONLY by the
progress/count queries (e.g. _desnag_progress i_row, L2845: filter
has_prior_defects=0). The RENDER path never reads the column -- it recomputes
has_open_prior / has_prior_defects live from the defect rows. So:
  - Resetting the column to 0 would PULL the item into the progress item
    bucket as an unmarked pending item -> drops the unit below 100% ->
    REGRESSION. Do NOT reset the column.
  - The fix is to set the ITEM's status so the render path stops treating it
    as pending. The defect bucket already counts the clear; progress stays
    correct; column stays 1 so the item stays out of the item bucket.

FIX (two-sided, mirrored):
  desnag_address, action='cleared':
    After clearing the defect, if the item has NO remaining OPEN prior defect,
    resolve its inspection_item row for THIS inspection:
        status='ok', marked_at=now.
  desnag_undo, re-open branch (status was 'cleared' this cycle):
    After re-opening the defect, the item has an open prior again -> revert
    its inspection_item row: status='pending', marked_at=NULL.

GUARD: both updates are scoped to the exact inspection_id (route arg) and the
defect's item_template_id, and the 'ok' set fires only when zero open priors
remain for that item/unit. Newly-visible (has_prior_defects=0) items are never
touched by either branch because they have no prior defect to clear/undo.

Assert-guarded find/replace. Two anchors. Aborts if either is not found
exactly once. ASCII only.
"""

import io

PATH = "app/routes/inspection.py"

# ---- Anchor 1: the action=='cleared' branch in desnag_address ----
OLD_CLEAR = """    if action == 'cleared':
        db.execute(\"\"\"UPDATE defect SET status='cleared',
            cleared_cycle_id=?, cleared_cycle_number=?, cleared_at=?,
            addressed_cycle_number=?, clearance_note='rectified', updated_at=?
            WHERE id=? AND status='open' AND tenant_id=?\"\"\",
            [inspection['cycle_id'], inspection['cycle_number'], now,
             inspection['cycle_number'], now, defect_id, tenant_id])
    elif action == 'still_open':"""

NEW_CLEAR = """    if action == 'cleared':
        db.execute(\"\"\"UPDATE defect SET status='cleared',
            cleared_cycle_id=?, cleared_cycle_number=?, cleared_at=?,
            addressed_cycle_number=?, clearance_note='rectified', updated_at=?
            WHERE id=? AND status='open' AND tenant_id=?\"\"\",
            [inspection['cycle_id'], inspection['cycle_number'], now,
             inspection['cycle_number'], now, defect_id, tenant_id])
        # v335: resolve the stale prior-defect orphan. If this item now has no
        # remaining OPEN prior defect, set its inspection_item row to ok so the
        # de-snag render path stops showing it as an unmarked pending row.
        # has_prior_defects column is intentionally LEFT AS-IS (read only by the
        # progress item bucket; resetting it would regress the percentage).
        _itpl = query_db(
            "SELECT item_template_id FROM defect WHERE id=? AND tenant_id=?",
            [defect_id, tenant_id], one=True)
        if _itpl:
            _open_left = query_db(
                \"\"\"SELECT COUNT(*) AS c FROM defect
                   WHERE unit_id=? AND tenant_id=? AND item_template_id=?
                   AND status='open' AND raised_cycle_number < ?\"\"\",
                [inspection['unit_id'], tenant_id, _itpl['item_template_id'],
                 inspection['cycle_number']], one=True)
            if _open_left and _open_left['c'] == 0:
                db.execute(
                    \"\"\"UPDATE inspection_item SET status='ok', marked_at=?
                       WHERE inspection_id=? AND item_template_id=? AND tenant_id=?
                       AND status='pending'\"\"\",
                    [now, inspection_id, _itpl['item_template_id'], tenant_id])
    elif action == 'still_open':"""

# ---- Anchor 2: the re-open branch in desnag_undo ----
OLD_UNDO = """    if defect['status'] == 'cleared' and defect['cleared_cycle_number'] == cycle_number:
        db.execute(\"\"\"UPDATE defect SET status='open',
            cleared_cycle_id=NULL, cleared_cycle_number=NULL, cleared_at=NULL,
            addressed_cycle_number=NULL, clearance_note=NULL, updated_at=?
            WHERE id=? AND tenant_id=?\"\"\", [now, defect_id, tenant_id])
    elif defect['status'] == 'open' and defect['addressed_cycle_number'] == cycle_number:"""

NEW_UNDO = """    if defect['status'] == 'cleared' and defect['cleared_cycle_number'] == cycle_number:
        db.execute(\"\"\"UPDATE defect SET status='open',
            cleared_cycle_id=NULL, cleared_cycle_number=NULL, cleared_at=NULL,
            addressed_cycle_number=NULL, clearance_note=NULL, updated_at=?
            WHERE id=? AND tenant_id=?\"\"\", [now, defect_id, tenant_id])
        # v335: mirror of the cleared-branch resolve. The defect is open again,
        # so the item has an open prior once more -> revert its inspection_item
        # row to pending so it re-surfaces for marking.
        _itpl = query_db(
            "SELECT item_template_id FROM defect WHERE id=? AND tenant_id=?",
            [defect_id, tenant_id], one=True)
        if _itpl:
            db.execute(
                \"\"\"UPDATE inspection_item SET status='pending', marked_at=NULL
                   WHERE inspection_id=? AND item_template_id=? AND tenant_id=?
                   AND status='ok' AND marked_at IS NOT NULL\"\"\",
                [inspection_id, _itpl['item_template_id'], tenant_id])
    elif defect['status'] == 'open' and defect['addressed_cycle_number'] == cycle_number:"""

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

c1 = src.count(OLD_CLEAR)
assert c1 == 1, "ABORT: cleared-branch anchor found %d times (expected 1). No changes written." % c1
c2 = src.count(OLD_UNDO)
assert c2 == 1, "ABORT: undo-branch anchor found %d times (expected 1). No changes written." % c2

src = src.replace(OLD_CLEAR, NEW_CLEAR)
src = src.replace(OLD_UNDO, NEW_UNDO)

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

with io.open(PATH, "r", encoding="utf-8") as f:
    after = f.read()

assert "v335: resolve the stale prior-defect orphan" in after, "ABORT: cleared-branch new text missing after write."
assert "v335: mirror of the cleared-branch resolve" in after, "ABORT: undo-branch new text missing after write."

print("OK: v335 applied. desnag_address resolves item on last-prior clear; desnag_undo reverts on re-open.")
print("Changed file:", PATH)
