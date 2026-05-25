#!/usr/bin/env python3
"""v315 (v2) -- my-inspections canonical 3-cohort total_items / completed_items.

(v2: corrected indentation. The my_inspections SQL uses 15-space indent
before (SELECT and 16-space before WHERE/AND; the prior attempt used
19/20 which mismatched.)

certification.py:my_inspections() computed total_items and completed_items
as items-only counts. For C2+ units this under-counted because the
canonical work-cohort includes open b/fwd latents and b/fwd defects
needing action this cycle. e.g. unit 023 C3 showed 0/55 instead of 0/56
(missing the 1 open KITCHEN latent).

Fix: replace each subquery alias with a parenthesised sum of three
subqueries, one per cohort, matching v314b's batch-detail formulas.

  total_items     = items_action + lan_open + defect_bfwd_action
  completed_items = items_action_marked + lan_addressed + defect_bfwd_addressed

The template (inspector_home.html) keeps reading insp.total_items /
insp.completed_items unchanged -- the values are now canonical.

Single-file change in certification.py.

Idempotent: re-running is a no-op once applied.
"""
from pathlib import Path
import ast

FILE = Path('app/routes/certification.py')
content = FILE.read_text()
original = content


# === OP 1: my_inspections total_items -- canonical 3-cohort sum ===
# Whitespace: 15-space indent before (SELECT, 16-space before WHERE/AND.
OLD_1 = '''               (SELECT COUNT(*) FROM inspection_item ii
                WHERE ii.inspection_id = i.id
                AND ii.status != 'skipped' AND NOT (ii.status = 'ok' AND ii.marked_at IS NULL AND COALESCE(ii.has_prior_defects, 0) = 0)) AS total_items,'''

NEW_1 = '''               ((SELECT COUNT(*) FROM inspection_item ii
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
                     AND (d4.status = 'open' OR d4.cleared_cycle_number = i.cycle_number))) AS total_items,'''

if 'FROM latent_area_note lan\n                   WHERE' in content:
    print('OP 1 (total_items canonical): already applied (idempotent skip)')
else:
    n = content.count(OLD_1)
    assert n == 1, f'OP 1: expected 1 match, got {n}'
    content = content.replace(OLD_1, NEW_1)
    print('OP 1 (total_items canonical): replaced 1 occurrence')


# === OP 2: my_inspections completed_items -- canonical 3-cohort sum ===
OLD_2 = '''               (SELECT COUNT(*) FROM inspection_item ii
                WHERE ii.inspection_id = i.id
                AND ii.status NOT IN ('skipped', 'pending') AND NOT (ii.status = 'ok' AND ii.marked_at IS NULL AND COALESCE(ii.has_prior_defects, 0) = 0)) AS completed_items,'''

NEW_2 = '''               ((SELECT COUNT(*) FROM inspection_item ii
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
                     AND d5.addressed_cycle_number = i.cycle_number)) AS completed_items,'''

if 'FROM latent_area_note lan2\n                   WHERE' in content:
    print('OP 2 (completed_items canonical): already applied (idempotent skip)')
else:
    n = content.count(OLD_2)
    assert n == 1, f'OP 2: expected 1 match, got {n}'
    content = content.replace(OLD_2, NEW_2)
    print('OP 2 (completed_items canonical): replaced 1 occurrence')


# === Python syntax (AST) check ===
try:
    ast.parse(content)
    print('python syntax: OK')
except SyntaxError as e:
    print(f'SYNTAX ERROR (file NOT written): {e}')
    raise SystemExit(1)


# === write file ===
if content != original:
    FILE.write_text(content)
    print(f'wrote {FILE} ({len(content)} chars)')
else:
    print('no changes (all ops were no-ops)')
