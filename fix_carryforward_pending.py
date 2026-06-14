#!/usr/bin/env python3
"""
Fix: never-inspected items carry forward as 'pending' not 'ok'.

Root cause (app/routes/inspection.py, cycle carry-forward branch):
a never-inspected item (no prior row, or prior status 'pending') was
flipped to 'ok' with NULL marked_at on new-cycle creation, then filtered
out of worklists as "carried-ok" -> inspector never sees it.

Fix: set status = 'pending' (+ honest comment) so the item stays visible.
C1 / no-prior-inspection branch (the `else:` at L197-205) is untouched.

Assert-guarded, single unique anchor. ASCII only.
"""

PATH = "app/routes/inspection.py"

OLD = """            if not prev or prev['status'] == 'pending':
                # No previous data or import bug (never marked) - treat as ok
                status = 'ok'
                comment = None"""

NEW = """            if not prev or prev['status'] == 'pending':
                # No previous data or never inspected - carry as pending so
                # the item stays visible and gets inspected this cycle
                status = 'pending'
                comment = None"""

with open(PATH, "r") as f:
    src = f.read()

assert src.count(OLD) == 1, (
    "Anchor not found exactly once (found %d) - aborting, no write."
    % src.count(OLD)
)

src = src.replace(OLD, NEW)

with open(PATH, "w") as f:
    f.write(src)

# verify the write
with open(PATH, "r") as f:
    check = f.read()
assert check.count(NEW) == 1, "Post-write verify failed - NEW block not present."
assert check.count(OLD) == 0, "Post-write verify failed - OLD block still present."

print("OK: carry-forward never-inspected -> 'pending' (was 'ok').")
