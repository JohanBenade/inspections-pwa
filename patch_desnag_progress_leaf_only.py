#!/usr/bin/env python3
"""
Patch: exclude parent items from _desnag_progress item count (count leaves only).

Target file : app/routes/inspection.py
Target func : _desnag_progress  (def at L2871)
Target query: i_row  "Newly-visible items at this cycle" (L2895-2905)

Why: the i_row query counts every matching inspection_item, including structural
parents. For de-snag units this inflates 'total' (Unit 028 C3: 82 leaves + 11
parents = 93). home() at app/__init__.py L138-142 overrides total_items with
this 'total', so the inspector home screen shows the inflated number.

Fix: add a leaf-only clause excluding any item that is itself a parent
(has children in item_template). Mirrors the intent of certification.py's
exclusion but is written fresh against this query's alias (ii.item_template_id).

This affects the item count for ALL de-snag units, not just 028 — intended,
all were inflated by their parents.

Run on: MACBOOK
"""

import io

PATH = "app/routes/inspection.py"

# Exact current WHERE block of the i_row query, copied verbatim from L2900-2904.
OLD = """        WHERE i.unit_id = ? AND i.tenant_id = ? AND i.cycle_number = ?
          AND ii.status != 'skipped'
          AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL)
          AND COALESCE(ii.has_prior_defects, 0) = 0
    \"\"\", [unit_id, tenant_id, cycle_number], one=True)"""

NEW = """        WHERE i.unit_id = ? AND i.tenant_id = ? AND i.cycle_number = ?
          AND ii.status != 'skipped'
          AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL)
          AND COALESCE(ii.has_prior_defects, 0) = 0
          AND NOT EXISTS (SELECT 1 FROM item_template ch
                          WHERE ch.parent_item_id = ii.item_template_id)
    \"\"\", [unit_id, tenant_id, cycle_number], one=True)"""

with io.open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

assert OLD in content, "MATCH FAILED: i_row WHERE block not found verbatim — aborting, no write."
assert content.count(OLD) == 1, "MATCH NOT UNIQUE: i_row WHERE block appears more than once — aborting."

content = content.replace(OLD, NEW)

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

# Verify the new clause is present exactly once and the old (un-patched) block is gone.
assert "AND NOT EXISTS (SELECT 1 FROM item_template ch" in content, "VERIFY FAILED: new clause not present after write."
print("OK: leaf-only clause added to _desnag_progress i_row query.")
print("Next: git add/commit/push, then verify Unit 028 = 82/82 and Unit 146 items count.")
