#!/usr/bin/env python3
"""
Patch 2 of this commit: align _desnag_area_progress item count with leaf-only.

Target file : app/routes/inspection.py
Target func : _desnag_area_progress  (def at L2914)
Target query: i_row  (L2939-2953)

Why: commit 8e60ab3 made the unit-level _desnag_progress count leaves only.
This area-level sibling still counts parents, so per-area item counts would
disagree with the unit total. Same structural-parent reasoning applies.

This query joins item_template aliased as `it`, so the EXISTS references it.id.

Run on: MACBOOK
"""

import io

PATH = "app/routes/inspection.py"

# Exact current i_row WHERE block of _desnag_area_progress, from L2948-2953.
OLD = """        WHERE i.unit_id = ? AND i.tenant_id = ? AND i.cycle_number = ?
          AND ii.status != 'skipped'
          AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL)
          AND COALESCE(ii.has_prior_defects, 0) = 0
          AND at2.area_name = ?
    \"\"\", [unit_id, tenant_id, cycle_number, area_name], one=True)"""

NEW = """        WHERE i.unit_id = ? AND i.tenant_id = ? AND i.cycle_number = ?
          AND ii.status != 'skipped'
          AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL)
          AND COALESCE(ii.has_prior_defects, 0) = 0
          AND NOT EXISTS (SELECT 1 FROM item_template ch
                          WHERE ch.parent_item_id = it.id)
          AND at2.area_name = ?
    \"\"\", [unit_id, tenant_id, cycle_number, area_name], one=True)"""

with io.open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

assert OLD in content, "MATCH FAILED: _desnag_area_progress i_row WHERE block not found verbatim — aborting."
assert content.count(OLD) == 1, "MATCH NOT UNIQUE: block appears more than once — aborting."

content = content.replace(OLD, NEW)

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

assert "WHERE ch.parent_item_id = it.id)\n          AND at2.area_name = ?" in content, "VERIFY FAILED: new clause not positioned correctly."
print("OK: leaf-only clause added to _desnag_area_progress i_row query.")
