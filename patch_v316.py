#!/usr/bin/env python3
"""
v316 - Canonical 3-cohort total_items/completed_items on team lead approvals dashboard.

Replaces raw COUNT(*) subqueries in dashboard() with the canonical 3-cohort sum
already used in my_inspections (v315), batch detail (v314+v314b), and live monitor (v313).

Targets:
- app/routes/certification.py
  - OP1: IF-branch total_items subquery (cycle_filter present)
  - OP2: IF-branch completed_items subquery
  - OP3: ELSE-branch total_items subquery (default view, latest cycle per unit)
  - OP4: ELSE-branch completed_items subquery
- app/templates/certification/dashboard.html
  - TPL OP: drop excluded_items subtraction in both progress blocks
              (new SQL already excludes skipped items)

All ops assertion-guarded. Aborts on any mismatch.
Run from repo root:  python3 patch_v316.py
"""

from pathlib import Path
import sys

ROUTE_PATH = Path("app/routes/certification.py")
TPL_PATH = Path("app/templates/certification/dashboard.html")

# ============================================================
# OP1: IF-branch total_items
# ============================================================

op1_old = """                (SELECT COUNT(*) FROM inspection_item ii 
                 WHERE ii.inspection_id = i.id
                ) AS total_items,"""

op1_new = """                ((SELECT COUNT(*) FROM inspection_item ii
                  WHERE ii.inspection_id = i.id
                    AND ii.status != 'skipped'
                    AND COALESCE(ii.has_prior_defects, 0) = 0
                    AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL))
                + (SELECT COUNT(*) FROM latent_area_note lan
                   WHERE lan.unit_id = u.id
                     AND lan.tenant_id = i.tenant_id
                     AND lan.cycle_number < i.cycle_number
                     AND (lan.rectified_at IS NULL OR lan.rectified_at_cycle_number = i.cycle_number))
                + (SELECT COUNT(*) FROM defect d4
                   WHERE d4.unit_id = u.id
                     AND d4.tenant_id = i.tenant_id
                     AND d4.raised_cycle_number < i.cycle_number
                     AND (d4.status = 'open' OR d4.cleared_cycle_number = i.cycle_number))) AS total_items,"""

# ============================================================
# OP2: IF-branch completed_items
# ============================================================

op2_old = """                (SELECT COUNT(*) FROM inspection_item ii 
                 WHERE ii.inspection_id = i.id AND ii.status != 'pending'
                ) AS completed_items,"""

op2_new = """                ((SELECT COUNT(*) FROM inspection_item ii
                  WHERE ii.inspection_id = i.id
                    AND ii.status NOT IN ('pending', 'skipped')
                    AND COALESCE(ii.has_prior_defects, 0) = 0
                    AND ii.marked_at IS NOT NULL)
                + (SELECT COUNT(*) FROM latent_area_note lan2
                   WHERE lan2.unit_id = u.id
                     AND lan2.tenant_id = i.tenant_id
                     AND lan2.cycle_number < i.cycle_number
                     AND (lan2.rectified_at_cycle_number = i.cycle_number
                          OR (lan2.addressed_cycle_number = i.cycle_number AND lan2.rectified_at IS NULL)))
                + (SELECT COUNT(*) FROM defect d5
                   WHERE d5.unit_id = u.id
                     AND d5.tenant_id = i.tenant_id
                     AND d5.raised_cycle_number < i.cycle_number
                     AND d5.addressed_cycle_number = i.cycle_number)) AS completed_items,"""

# ============================================================
# OP3: ELSE-branch total_items
# ============================================================

op3_old = """                (SELECT COUNT(*) FROM inspection_item ii 
                 WHERE ii.inspection_id = latest.inspection_id
                ) AS total_items,"""

op3_new = """                ((SELECT COUNT(*) FROM inspection_item ii
                  WHERE ii.inspection_id = latest.inspection_id
                    AND ii.status != 'skipped'
                    AND COALESCE(ii.has_prior_defects, 0) = 0
                    AND (ii.status = 'pending' OR ii.marked_at IS NOT NULL))
                + (SELECT COUNT(*) FROM latent_area_note lan
                   WHERE lan.unit_id = u.id
                     AND lan.tenant_id = u.tenant_id
                     AND lan.cycle_number < latest.cycle_number
                     AND (lan.rectified_at IS NULL OR lan.rectified_at_cycle_number = latest.cycle_number))
                + (SELECT COUNT(*) FROM defect d4
                   WHERE d4.unit_id = u.id
                     AND d4.tenant_id = u.tenant_id
                     AND d4.raised_cycle_number < latest.cycle_number
                     AND (d4.status = 'open' OR d4.cleared_cycle_number = latest.cycle_number))) AS total_items,"""

# ============================================================
# OP4: ELSE-branch completed_items
# ============================================================

op4_old = """                (SELECT COUNT(*) FROM inspection_item ii 
                 WHERE ii.inspection_id = latest.inspection_id AND ii.status != 'pending'
                ) AS completed_items,"""

op4_new = """                ((SELECT COUNT(*) FROM inspection_item ii
                  WHERE ii.inspection_id = latest.inspection_id
                    AND ii.status NOT IN ('pending', 'skipped')
                    AND COALESCE(ii.has_prior_defects, 0) = 0
                    AND ii.marked_at IS NOT NULL)
                + (SELECT COUNT(*) FROM latent_area_note lan2
                   WHERE lan2.unit_id = u.id
                     AND lan2.tenant_id = u.tenant_id
                     AND lan2.cycle_number < latest.cycle_number
                     AND (lan2.rectified_at_cycle_number = latest.cycle_number
                          OR (lan2.addressed_cycle_number = latest.cycle_number AND lan2.rectified_at IS NULL)))
                + (SELECT COUNT(*) FROM defect d5
                   WHERE d5.unit_id = u.id
                     AND d5.tenant_id = u.tenant_id
                     AND d5.raised_cycle_number < latest.cycle_number
                     AND d5.addressed_cycle_number = latest.cycle_number)) AS completed_items,"""

# ============================================================
# TPL OP: drop excluded_items subtraction in BOTH progress blocks
# ============================================================

tpl_old = """                                            {% set checkable = unit.total_items - (unit.excluded_items or 0) %}
                                            {% set done = (unit.completed_items or 0) - (unit.excluded_items or 0) %}"""

tpl_new = """                                            {% set checkable = unit.total_items %}
                                            {% set done = (unit.completed_items or 0) %}"""

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
            print(f"    Diagnose with: grep -nA2 'AS {label.split()[-1]}' {path}")
            sys.exit(1)
        content = content.replace(old, new)
        print(f"  {label}: applied ({cnt} match{'es' if cnt > 1 else ''})")
    if content == original:
        print(f"  WARNING: no changes to {path}")
        sys.exit(1)
    path.write_text(content)
    print(f"Wrote {path}")

apply_ops(ROUTE_PATH, [
    ("OP1 IF total_items",         op1_old, op1_new, 1),
    ("OP2 IF completed_items",     op2_old, op2_new, 1),
    ("OP3 ELSE total_items",       op3_old, op3_new, 1),
    ("OP4 ELSE completed_items",   op4_old, op4_new, 1),
])

print()

apply_ops(TPL_PATH, [
    ("TPL OP excluded_items drop", tpl_old, tpl_new, 2),
])

print()
print("v316 patch complete.")
print()
print("Next:")
print("  python3 -c \"import ast; ast.parse(open('app/routes/certification.py').read()); print('AST OK')\"")
print("  git --no-pager diff --stat")
print("  git --no-pager diff app/routes/certification.py | head -120")
print("  git --no-pager diff app/templates/certification/dashboard.html")
