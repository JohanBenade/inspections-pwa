#!/usr/bin/env python3
"""
Patch: align desnag_submit's unaddressed_items guard with the leaf-only count.

Target file : app/routes/inspection.py
Target func : desnag_submit  (def at L2826)
Target query: unaddressed_items  (L2846-2849)

Why: commit 8e60ab3 made _desnag_progress count leaves only, so the inspector
home screen shows Unit 028 as 82/82 (complete). But this submit guard still
counts parent items as 'pending' work, so it returns >0 and aborts(400) on
submit. Proven on Unit 028 (inspection 09923c49): all 11 blocking 'pending'
items have child_count>0 — every one is a structural parent, zero leaves.

Fix: add the same leaf-only clause used in _desnag_progress so the guard and
the display agree. Parents are structural (auto-resolved elsewhere), not
inspector-actionable checkpoints.

Note: this query uses the bare table name `inspection_item` (no alias), so the
EXISTS subquery references `inspection_item.item_template_id` explicitly.

Run on: MACBOOK
"""

import io

PATH = "app/routes/inspection.py"

# Exact current unaddressed_items query, copied verbatim from L2846-2849.
OLD = """    unaddressed_items = query_db(\"\"\"
        SELECT COUNT(*) as cnt FROM inspection_item
        WHERE inspection_id = ? AND tenant_id = ? AND status = 'pending'
        AND COALESCE(has_prior_defects, 0) = 0
    \"\"\", [inspection_id, tenant_id], one=True)['cnt']"""

NEW = """    unaddressed_items = query_db(\"\"\"
        SELECT COUNT(*) as cnt FROM inspection_item
        WHERE inspection_id = ? AND tenant_id = ? AND status = 'pending'
        AND COALESCE(has_prior_defects, 0) = 0
        AND NOT EXISTS (SELECT 1 FROM item_template ch
                        WHERE ch.parent_item_id = inspection_item.item_template_id)
    \"\"\", [inspection_id, tenant_id], one=True)['cnt']"""

with io.open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

assert OLD in content, "MATCH FAILED: unaddressed_items query not found verbatim — aborting, no write."
assert content.count(OLD) == 1, "MATCH NOT UNIQUE: unaddressed_items query appears more than once — aborting."

content = content.replace(OLD, NEW)

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

assert "WHERE ch.parent_item_id = inspection_item.item_template_id" in content, "VERIFY FAILED: new clause not present after write."
print("OK: leaf-only clause added to desnag_submit unaddressed_items guard.")
print("Next: git add/commit/push, then re-submit Unit 028 — expect redirect to home, no 400.")
