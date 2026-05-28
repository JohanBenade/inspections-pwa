#!/usr/bin/env python3
"""
Patch A v2 — update_item route exception for missed-items remediation (path B).

v2 fixes: original OLD block matched TWO routes — update_item (L933) and
category_cascade_ni (L2008) — because both share the same Lock + Auto-resume
shape. v2 disambiguates using `if not item:` pre-context (unique to
update_item; category_cascade_ni uses `if not inspection:`).

Also tolerates both blank-line whitespace variants (`\\n` vs `    \\n`) since
the file has inconsistent trailing whitespace on blank lines.

Allows inspectors to mark `has_prior_defects=0` items inside `pending_followup`
inspections WITHOUT changing inspection.status.

Side effects verified safe:
- paused auto-resume: gated to status='paused'
- parent cascade: only fires for marked parents; cascade behaviour is correct
- clear_ni_defects: only fires with explicit form flag
- not_started -> in_progress auto-transition: gated to status='not_started'
- No inspection.status change for our pending_followup cohort

Idempotent: safe to re-run.
"""

import os
import sys

PATH = os.path.expanduser('~/Documents/GitHub/inspections-pwa/app/routes/inspection.py')

# Two possible OLD variants depending on blank-line whitespace.
# Variant 1: blank line has 4 trailing spaces.
OLD_V1 = """    if not item:
        abort(404)
    
    # Lock: no edits after sign-off
    if inspection['status'] in ('pending_followup', 'approved', 'certified'):
        abort(403)

    # Auto-resume if inspection is paused"""

# Variant 2: blank line is empty.
OLD_V2 = """    if not item:
        abort(404)

    # Lock: no edits after sign-off
    if inspection['status'] in ('pending_followup', 'approved', 'certified'):
        abort(403)

    # Auto-resume if inspection is paused"""

# NEW always normalizes the first blank line to empty (no trailing whitespace).
NEW = """    if not item:
        abort(404)

    # Lock: no edits after sign-off, except missed-items remediation in pending_followup.
    # Items with no prior defects (excluded in C1 via exclusion list / floor_condition)
    # can be marked freely so inspectors can clean up the residual gap from the
    # pre-21-May display bug. Inspection.status does not change.
    if inspection['status'] in ('pending_followup', 'approved', 'certified'):
        is_missed_item_remediation = (
            inspection['status'] == 'pending_followup'
            and item['status'] in ('pending', 'ok', 'not_to_standard', 'not_installed')
            and not (item['has_prior_defects'] or 0)
        )
        if not is_missed_item_remediation:
            abort(403)

    # Auto-resume if inspection is paused"""


def main():
    with open(PATH, 'r') as f:
        content = f.read()

    # Idempotency check — already applied
    if NEW in content and OLD_V1 not in content and OLD_V2 not in content:
        print("PATCH A: already applied (idempotent), nothing to do.")
        return

    # Try variant 1 first, then variant 2
    if OLD_V1 in content:
        old = OLD_V1
        variant = "V1 (blank line has 4 trailing spaces)"
    elif OLD_V2 in content:
        old = OLD_V2
        variant = "V2 (blank line empty)"
    else:
        print("MATCH FAILED: neither blank-line variant of OLD block found.", file=sys.stderr)
        print("File may have been edited since the read. Re-read and retry.", file=sys.stderr)
        sys.exit(1)

    count = content.count(old)
    assert count == 1, f"MATCH FAILED: {variant} matched {count} times (expected exactly 1)"

    new_content = content.replace(old, NEW)
    assert new_content != content, "REPLACE FAILED: content unchanged"
    assert new_content.count(NEW) == 1, "INTEGRITY FAILED: NEW block count != 1 after replace"

    # Confirm category_cascade_ni's lock is still intact (paranoid check)
    cascade_lock = """    if not inspection:
        abort(404)

    # Lock: no edits after sign-off
    if inspection['status'] in ('pending_followup', 'approved', 'certified'):
        abort(403)

    # Auto-resume if inspection is paused"""
    assert cascade_lock in new_content, \
        "PARANOID FAIL: category_cascade_ni lock no longer present (unintended edit)"

    with open(PATH, 'w') as f:
        f.write(new_content)

    print(f"PATCH A applied to update_item route (matched {variant}).")
    print(f"  Old block:  {len(old)} chars")
    print(f"  New block:  {len(NEW)} chars")
    print(f"  Diff:       +{len(NEW) - len(old)} chars")
    print(f"  category_cascade_ni lock preserved.")


if __name__ == '__main__':
    main()
