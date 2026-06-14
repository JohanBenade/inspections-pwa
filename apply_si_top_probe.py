#!/usr/bin/env python3
# Probe: inject SI_TOP marker as the first rendered output of _single_item.html,
# ABOVE the {% if not is_skipped %} wrapper, so it prints for EVERY item that
# reaches this template (skipped or not). Splits hypothesis (i) include-entered
# -but-wrapper-fails vs (ii) loop-body-skipped for the 4 LOUNGE pending items.
# ASCII only. One logical change. Assert-guarded.

import io

PATH = "app/templates/inspection/_single_item.html"

ANCHOR = "{% if not is_skipped %}"

MARKER = (
    "<!-- SI_TOP id={{ item.id|default('NOITEM') }} "
    "status={{ item.status|default('NOSTATUS') }} "
    "skipped={{ is_skipped|default('NOVAR') }} "
    "pid={{ item.parent_item_id|default('NONE') }} "
    "cc={{ item.child_count|default('NOCC') }} -->\n"
)

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# Guard 1: anchor must exist exactly once.
n = src.count(ANCHOR)
assert n == 1, "EXPECTED 1 occurrence of wrapper anchor, found %d" % n

# Guard 2: probe must not already be present (idempotency / no double-apply).
assert "SI_TOP" not in src, "SI_TOP marker already present - aborting"

new = src.replace(ANCHOR, MARKER + ANCHOR, 1)

# Guard 3: exactly one marker inserted; length grew by len(MARKER).
assert new.count("SI_TOP") == 1, "post-edit SI_TOP count != 1"
assert len(new) == len(src) + len(MARKER), "unexpected length delta"

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(new)

print("OK: SI_TOP marker inserted above is_skipped wrapper in", PATH)
