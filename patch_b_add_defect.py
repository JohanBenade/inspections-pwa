#!/usr/bin/env python3
"""
Patch B — add_defect route exception for missed-items remediation (path B).

Two coupled changes in one block (so the find/replace is atomic):

  1. Narrow exception to the abort lock, mirroring Patch A's filter so the
     same cohort (pending_followup + no prior defects) can have defects
     raised on previously-excluded items.

  2. Extend `is_submitted` to include 'pending_followup' so the defect
     writes directly to the `defect` table (not the `inspection_defect`
     scratchpad, which has already been flushed at submit time).

A2 (relaxed) filter to match Patch A: allows status in
('pending', 'ok', 'not_to_standard', 'not_installed') so multi-defect raises
and undo flows work end-to-end.

Idempotent: safe to re-run. Asserts on exactly one match.
"""

import os

PATH = os.path.expanduser('~/Documents/GitHub/inspections-pwa/app/routes/inspection.py')

OLD = """    # Lock: no edits after sign-off
    if inspection['status'] in ('pending_followup', 'approved', 'certified'):
        abort(403)

    is_submitted = inspection['status'] in ('submitted', 'reviewed', 'approved')"""

NEW = """    # Lock: no edits after sign-off, except missed-items remediation in pending_followup.
    # Items with no prior defects (excluded in C1) can have defects raised here, even
    # after submit. is_submitted is extended below so the defect writes directly to
    # the defect table (not the scratchpad, which has already been flushed).
    if inspection['status'] in ('pending_followup', 'approved', 'certified'):
        is_missed_item_remediation = (
            inspection['status'] == 'pending_followup'
            and item['status'] in ('pending', 'ok', 'not_to_standard', 'not_installed')
            and not (item['has_prior_defects'] or 0)
        )
        if not is_missed_item_remediation:
            abort(403)

    is_submitted = inspection['status'] in ('submitted', 'reviewed', 'approved', 'pending_followup')"""


def main():
    with open(PATH, 'r') as f:
        content = f.read()

    if NEW in content and OLD not in content:
        print("PATCH B: already applied (idempotent), nothing to do.")
        return

    count = content.count(OLD)
    assert count == 1, f"MATCH FAILED: found {count} occurrences of OLD block (expected exactly 1)"

    new_content = content.replace(OLD, NEW)
    assert new_content != content, "REPLACE FAILED: content unchanged"
    assert new_content.count(NEW) == 1, "INTEGRITY FAILED: NEW block count != 1 after replace"

    with open(PATH, 'w') as f:
        f.write(new_content)

    print("PATCH B applied to add_defect route.")
    print(f"  Old block:  {len(OLD)} chars")
    print(f"  New block:  {len(NEW)} chars")
    print(f"  Diff:       +{len(NEW) - len(OLD)} chars")


if __name__ == '__main__':
    main()
