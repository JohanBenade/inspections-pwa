#!/usr/bin/env python3
# Probe: emit a GATE marker for EVERY item in cat.checklist, placed INSIDE the
# {% for item in cat.checklist %} loop but BEFORE the L25 visibility {% if %}.
# This prints the 4 gate operands even for items the gate drops, so we can see
# which operand removes the pending+cc=0 leaves (LOUNGE/KITCHEN).
# ASCII only. One logical change. Assert-guarded.

import io

PATH = "app/templates/inspection/_desnag_items.html"

# Anchor: the parent-header {% if %} opener at L20. We insert the marker line
# immediately AFTER the {% for item in cat.checklist %} line (L18) and BEFORE
# the L19 comment. Use the for-line as the unique anchor.
ANCHOR = "        {% for item in cat.checklist %}\n"

MARKER = (
    "        <!-- GATE id={{ item.id|default('NOITEM') }}"
    " status={{ item.status|default('NOSTATUS') }}"
    " cc={{ item.child_count|default('NOCC') }}"
    " carried={{ item.is_carried_ok|default('NOVAR') }}"
    " chdef={{ item.children_have_defects|default('NOVAR') }}"
    " openprior={{ item.has_open_prior|default('NOVAR') }}"
    " hpd={{ item.has_prior_defects|default('NOVAR') }} -->\n"
)

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# Guard 1: anchor exists exactly once.
n = src.count(ANCHOR)
assert n == 1, "EXPECTED 1 occurrence of for-loop anchor, found %d" % n

# Guard 2: probe not already present.
assert "<!-- GATE id=" not in src, "GATE marker already present - aborting"

new = src.replace(ANCHOR, ANCHOR + MARKER, 1)

# Guard 3: exactly one marker, length grew by len(MARKER).
assert new.count("<!-- GATE id=") == 1, "post-edit GATE count != 1"
assert len(new) == len(src) + len(MARKER), "unexpected length delta"

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(new)

print("OK: GATE operand marker inserted in", PATH)
