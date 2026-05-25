#!/usr/bin/env python3
"""
v317 - Soft-archive infrastructure for item_template.

DB MIGRATION (run on Render console BEFORE this patch):
    ALTER TABLE item_template ADD COLUMN active INTEGER DEFAULT 1;
    UPDATE item_template SET active=0 WHERE id='1161cc67';

This script patches the CODE side:
- OP1: app/routes/inspection.py line 119 - add `AND active = 1` to inspection-creation template loop
- OP2: app/routes/cycles.py line 507 area - add `AND it.active = 1` to cycle-exclusion admin UI query

Read paths (display of historical inspection_items joined to templates) are intentionally
NOT filtered - historical inspection_items must still resolve to their template names/descriptions
even after the template is archived.

Layer 2 (batches.py count queries computing items_per_unit denominator) deferred per scope decision.

All ops assertion-guarded. Aborts on any mismatch.
Run from repo root:  python3 patch_v317.py
"""

from pathlib import Path
import sys

INSP_PATH = Path("app/routes/inspection.py")
CYCLES_PATH = Path("app/routes/cycles.py")

# ============================================================
# OP1: inspection.py line 119 - creation path filter
# ============================================================

op1_old = '''        "SELECT id, floor_condition FROM item_template WHERE tenant_id = ?", [tenant_id]
'''

op1_new = '''        "SELECT id, floor_condition FROM item_template WHERE tenant_id = ? AND active = 1", [tenant_id]
'''

# ============================================================
# OP2: cycles.py line 507 area - admin UI display filter
# ============================================================

op2_old = '''                LEFT JOIN cycle_excluded_item cei ON cei.item_template_id = it.id AND cei.cycle_id = ?
                WHERE it.category_id = ?
                ORDER BY it.item_order
'''

op2_new = '''                LEFT JOIN cycle_excluded_item cei ON cei.item_template_id = it.id AND cei.cycle_id = ?
                WHERE it.category_id = ? AND it.active = 1
                ORDER BY it.item_order
'''

# ============================================================
# APPLY
# ============================================================

def apply_ops(path, ops):
    """ops is list of (label, old, new, expected_count) tuples."""
    print(f"Reading {path} ...")
    if not path.exists():
        print(f"ERROR: file not found: {path}")
        sys.exit(1)
    content = path.read_text()
    original = content
    for label, old, new, expected in ops:
        cnt = content.count(old)
        if cnt != expected:
            print(f"  {label}: FAILED - expected {expected} matches, got {cnt}")
            sys.exit(1)
        content = content.replace(old, new)
        print(f"  {label}: applied ({cnt} match)")
    if content == original:
        print(f"  WARNING: no changes to {path}")
        sys.exit(1)
    path.write_text(content)
    print(f"Wrote {path}")

apply_ops(INSP_PATH,   [("OP1 inspection.py line 119", op1_old, op1_new, 1)])
print()
apply_ops(CYCLES_PATH, [("OP2 cycles.py line 507 area", op2_old, op2_new, 1)])

print()
print("v317 patch complete.")
print()
print("Next:")
print("  python3 -c \"import ast; ast.parse(open('app/routes/inspection.py').read()); ast.parse(open('app/routes/cycles.py').read()); print('AST OK')\"")
print("  git --no-pager diff --stat")
print("  git --no-pager diff app/routes/inspection.py app/routes/cycles.py")
