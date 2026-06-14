#!/usr/bin/env python3
# Fix: de-snag items gate over-suppresses pending childless leaves whose ONLY
# prior defect is CLEARED. Clause 4 used has_prior_defects (any prior, open or
# cleared); it must use has_open_prior (prior still shown in defects section).
# A cleared-only prior appears nowhere else, so the item must render so the
# inspector can MS/NTS it. One operand change. ASCII only. Assert-guarded.

import io

PATH = "app/templates/inspection/_desnag_items.html"

OLD = "and not (item.status == 'pending' and item.has_prior_defects|default(false))"
NEW = "and not (item.status == 'pending' and item.has_open_prior|default(false))"

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# Guard 1: target clause present exactly once.
n = src.count(OLD)
assert n == 1, "EXPECTED 1 occurrence of clause-4 target, found %d" % n

# Guard 2: replacement not already present (idempotency).
assert NEW not in src, "replacement clause already present - aborting"

new = src.replace(OLD, NEW, 1)

# Guard 3: exactly one replacement, length delta is the operand-name diff.
assert new.count(NEW) == 1, "post-edit replacement count != 1"
assert new.count(OLD) == 0, "old clause still present after edit"
delta = len(NEW) - len(OLD)
assert len(new) == len(src) + delta, "unexpected length delta"

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(new)

print("OK: gate clause 4 now keys on has_open_prior in", PATH)
