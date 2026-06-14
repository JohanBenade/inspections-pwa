#!/usr/bin/env python3
"""
patch_v335b_use_canonical_helper.py

WHY: v335 (already committed) hand-rolled the "resolve item when last prior
clears" logic inline in desnag_address / desnag_undo. That inline logic only
checked OPEN PRIOR defects. The codebase already has the canonical helper
_update_item_status_from_priors (L1465) which checks THREE sources:
  1. open prior defects (other cycles)
  2. current-cycle defects (raised_cycle_id = this cycle)
  3. inspection_defect chips
...and sets not_to_standard if ANY exist, else ok, always stamping marked_at.

The inline v335 logic would WRONGLY set an item to 'ok' if its last prior was
cleared but it still had a current-cycle defect or a chip. This patch removes
the inline blocks and calls the canonical helper instead -- making desnag
identical to clear_prior_defect / reopen_prior_defect (the proven paths).

Helper signature:
  _update_item_status_from_priors(db, inspection_id, item_id,
      item_template_id, unit_id, cycle_id, tenant_id, now)

desnag_address has: inspection['cycle_id'], inspection['unit_id'],
inspection['cycle_number'], inspection_id, defect_id, now, tenant_id.
We look up the inspection_item id by (inspection_id, item_template_id).

Assert-guarded. Two anchors (the v335 inline blocks). Aborts if either anchor
is not found exactly once. ASCII only.
"""

import io

PATH = "app/routes/inspection.py"

# ---- Anchor 1: v335 inline block in desnag_address (cleared branch) ----
OLD_CLEAR = """        # v335: resolve the stale prior-defect orphan. If this item now has no
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
                    [now, inspection_id, _itpl['item_template_id'], tenant_id])"""

NEW_CLEAR = """        # v335b: route through the canonical helper (same as clear_prior_defect)
        # so item status reflects ALL defect sources (open priors, current-cycle
        # defects, chips), not just open priors. has_prior_defects column is
        # left as-is (read only by the progress item bucket).
        _d = query_db(
            "SELECT item_template_id FROM defect WHERE id=? AND tenant_id=?",
            [defect_id, tenant_id], one=True)
        if _d:
            _ii = query_db(
                "SELECT id FROM inspection_item WHERE inspection_id=? AND item_template_id=? AND tenant_id=?",
                [inspection_id, _d['item_template_id'], tenant_id], one=True)
            if _ii:
                _update_item_status_from_priors(
                    db, inspection_id, _ii['id'], _d['item_template_id'],
                    inspection['unit_id'], inspection['cycle_id'], tenant_id, now)"""

# ---- Anchor 2: v335 inline block in desnag_undo (reopen branch) ----
OLD_UNDO = """        # v335: mirror of the cleared-branch resolve. The defect is open again,
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
                [inspection_id, _itpl['item_template_id'], tenant_id])"""

NEW_UNDO = """        # v335b: route through the canonical helper (same as reopen_prior_defect).
        # Defect is open again -> helper re-derives status (will be NTS due to the
        # now-open prior) and stamps marked_at.
        _d = query_db(
            "SELECT item_template_id FROM defect WHERE id=? AND tenant_id=?",
            [defect_id, tenant_id], one=True)
        if _d:
            _ii = query_db(
                "SELECT id FROM inspection_item WHERE inspection_id=? AND item_template_id=? AND tenant_id=?",
                [inspection_id, _d['item_template_id'], tenant_id], one=True)
            if _ii:
                _update_item_status_from_priors(
                    db, inspection_id, _ii['id'], _d['item_template_id'],
                    inspection['unit_id'], inspection['cycle_id'], tenant_id, now)"""

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

c1 = src.count(OLD_CLEAR)
assert c1 == 1, "ABORT: v335 cleared-branch inline block found %d times (expected 1). No changes written." % c1
c2 = src.count(OLD_UNDO)
assert c2 == 1, "ABORT: v335 undo-branch inline block found %d times (expected 1). No changes written." % c2

src = src.replace(OLD_CLEAR, NEW_CLEAR)
src = src.replace(OLD_UNDO, NEW_UNDO)

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

with io.open(PATH, "r", encoding="utf-8") as f:
    after = f.read()

assert "v335b: route through the canonical helper (same as clear_prior_defect)" in after, "ABORT: cleared-branch refactor text missing after write."
assert "v335b: route through the canonical helper (same as reopen_prior_defect)" in after, "ABORT: undo-branch refactor text missing after write."
assert OLD_CLEAR not in after and OLD_UNDO not in after, "ABORT: old v335 inline blocks still present."

print("OK: v335b applied. desnag now uses _update_item_status_from_priors (3-source canonical logic).")
print("Changed file:", PATH)
