#!/usr/bin/env python3
"""
v373 fix: three reopen/un-address paths in inspection.py null the structural
clear-fields but leave clearance_note='rectified' stale. Align them to the
proven-correct desnag_undo cleared-branch (which already nulls clearance_note).

Paths fixed:
  L1350  reopen_prior_defect      (ISO-format handler)
  L1678  submit-loop reopen       (CURRENT_TIMESTAMP handler)
  L2701  desnag_undo elif (un-address)
"""
import io, sys

PATH = "app/routes/inspection.py"

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# --- Edit 1: reopen_prior_defect (L1350) -------------------------------------
old1 = ("        UPDATE defect SET status = 'open', cleared_cycle_id = NULL, "
        "cleared_cycle_number = NULL, cleared_at = NULL, updated_at = ?\n"
        "        WHERE id = ?\n")
new1 = ("        UPDATE defect SET status = 'open', cleared_cycle_id = NULL, "
        "cleared_cycle_number = NULL, cleared_at = NULL, clearance_note = NULL, "
        "updated_at = ?\n"
        "        WHERE id = ?\n")
assert src.count(old1) == 1, f"Edit1: expected 1 match, found {src.count(old1)}"
src = src.replace(old1, new1)

# --- Edit 2: submit-loop reopen (L1678) --------------------------------------
old2 = ("db.execute(\"UPDATE defect SET status = 'open', cleared_cycle_id = NULL, "
        "cleared_cycle_number = NULL, cleared_at = NULL, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?\", [existing['id']])")
new2 = ("db.execute(\"UPDATE defect SET status = 'open', cleared_cycle_id = NULL, "
        "cleared_cycle_number = NULL, cleared_at = NULL, clearance_note = NULL, "
        "updated_at = CURRENT_TIMESTAMP WHERE id = ?\", [existing['id']])")
assert src.count(old2) == 1, f"Edit2: expected 1 match, found {src.count(old2)}"
src = src.replace(old2, new2)

# --- Edit 3: desnag_undo elif un-address (L2701) -----------------------------
old3 = ("        db.execute(\"\"\"UPDATE defect SET addressed_cycle_number=NULL, "
        "updated_at=?\n"
        "            WHERE id=? AND tenant_id=?\"\"\", [now, defect_id, tenant_id])")
new3 = ("        db.execute(\"\"\"UPDATE defect SET addressed_cycle_number=NULL, "
        "clearance_note=NULL, updated_at=?\n"
        "            WHERE id=? AND tenant_id=?\"\"\", [now, defect_id, tenant_id])")
assert src.count(old3) == 1, f"Edit3: expected 1 match, found {src.count(old3)}"
src = src.replace(old3, new3)

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("OK: 3 edits applied to", PATH)
