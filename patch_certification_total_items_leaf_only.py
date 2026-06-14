#!/usr/bin/env python3
"""
Patch: align certification.py dashboard() item counts with the leaf-only rule.

Target file : app/routes/certification.py
Target func : dashboard()  (def L109)
Targets     : 4 inspection_item sub-counts -
              A-total     (~L153), A-completed (~L168)  [cycle-filter branch, i.id]
              B-total     (~L217), B-completed (~L232)  [else branch, latest.inspection_id]

Why: 8e60ab3/570a0b9 made the de-snag counts leaf-only. These dashboard
total_items/completed_items still count structural parents, so the team-lead /
manager unit list shows inflated totals (the 82/93 problem on a different page).
Clause added to BOTH total and completed in BOTH branches so the ratio stays
consistent (parents drop from numerator and denominator together).

Clause (alias ii): AND NOT EXISTS (SELECT 1 FROM item_template ch
                                   WHERE ch.parent_item_id = ii.item_template_id)

Each of the 4 item sub-counts is matched by its full, unique WHERE block.

Run on: MACBOOK
"""

import io

PATH = "app/routes/certification.py"
LEAF = ("\n                    AND NOT EXISTS (SELECT 1 FROM item_template ch "
        "WHERE ch.parent_item_id = ii.item_template_id)")

# --- A-total: i.id, status != 'skipped', pending OR marked_at ---
A_TOTAL_OLD = """                ((SELECT COUNT(*) FROM inspection_item ii
                  WHERE ii.inspection_id = i.id
                    AND ii.status != 'skipped'
                    AND COALESCE(ii.has_prior_defects, 0) = 0
                    AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL))"""

# --- A-completed: i.id, status NOT IN (pending,skipped), marked_at IS NOT NULL ---
A_DONE_OLD = """                ((SELECT COUNT(*) FROM inspection_item ii
                  WHERE ii.inspection_id = i.id
                    AND ii.status NOT IN ('pending', 'skipped')
                    AND COALESCE(ii.has_prior_defects, 0) = 0
                    AND ii.marked_at IS NOT NULL)"""

# --- B-total: latest.inspection_id, status != 'skipped', pending OR marked_at ---
B_TOTAL_OLD = """                ((SELECT COUNT(*) FROM inspection_item ii
                  WHERE ii.inspection_id = latest.inspection_id
                    AND ii.status != 'skipped'
                    AND COALESCE(ii.has_prior_defects, 0) = 0
                    AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL))"""

# --- B-completed: latest.inspection_id, status NOT IN (pending,skipped), marked_at IS NOT NULL ---
B_DONE_OLD = """                ((SELECT COUNT(*) FROM inspection_item ii
                  WHERE ii.inspection_id = latest.inspection_id
                    AND ii.status NOT IN ('pending', 'skipped')
                    AND COALESCE(ii.has_prior_defects, 0) = 0
                    AND ii.marked_at IS NOT NULL)"""


def add_clause(block):
    # Insert LEAF immediately before the closing ")" of the inner SELECT.
    # The inner SELECT ends with the last condition line then "))".
    # Find the final ")" that closes the COUNT subquery: it is the char before
    # the trailing ")" group. Simplest robust approach: insert after the last
    # condition, which is the substring ending the block minus its closing ")".
    assert block.endswith(")"), "block does not end with ')'"
    return block[:-1] + LEAF + ")"


with io.open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

for name, old in [("A_TOTAL", A_TOTAL_OLD), ("A_DONE", A_DONE_OLD),
                  ("B_TOTAL", B_TOTAL_OLD), ("B_DONE", B_DONE_OLD)]:
    assert old in content, "MATCH FAILED for %s — aborting, no write." % name
    assert content.count(old) == 1, "MATCH NOT UNIQUE for %s — aborting." % name

for old in [A_TOTAL_OLD, A_DONE_OLD, B_TOTAL_OLD, B_DONE_OLD]:
    content = content.replace(old, add_clause(old))

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

n = content.count("WHERE ch.parent_item_id = ii.item_template_id")
assert n == 4, "VERIFY FAILED: expected 4 leaf clauses, found %d." % n
print("OK: leaf-only clause added to all 4 certification dashboard() item sub-counts.")
print("Next: git add/commit/push, then verify a known cert unit reads e.g. 82/82.")
