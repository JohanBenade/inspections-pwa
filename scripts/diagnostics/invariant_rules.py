#!/usr/bin/env python3
"""
invariant_rules.py - the three invariant rule queries, extracted so BOTH the live
runner (check_invariants_live.py, against /var/data/inspections.db) and the CI gate
(tests/test_invariants.py, against committed fixtures) import the SAME definitions.

Each rule takes an open sqlite3 cursor and returns (count, offenders). Query bodies
are copied verbatim from the proven check_invariants_live.py - no logic change.

Production baselines live in the live runner. Fixture-expected counts live in the CI
test. This module holds ONLY the rule logic, so adding R4 later touches one file.
"""

# Production baselines (used by the live runner). The CI test asserts its own
# fixture-specific expected counts and does NOT use these.
LIVE_BASELINES = {"R1": 0, "R2": 1, "R3": 0}


def rule_R1_cei_pollution(cur):
    """Skipped inspection_item on a NULL-link inspection whose CEI row is
    NULL/cleanup reason AND the item is neither in the live cycle-matched
    batch_unit exclusion list NOR ground_only. That is genuine skip pollution."""
    cur.execute(
        """
        SELECT u.unit_number, insp.cycle_number, COUNT(*)
        FROM inspection_item ii
        JOIN inspection insp ON ii.inspection_id = insp.id
        JOIN unit u ON insp.unit_id = u.id
        JOIN item_template it ON ii.item_template_id = it.id
        WHERE ii.status = 'skipped'
          AND insp.exclusion_list_id IS NULL
          AND it.floor_condition != 'ground_only'
          AND EXISTS (
              SELECT 1 FROM cycle_excluded_item cei
              WHERE cei.cycle_id = insp.cycle_id
                AND cei.item_template_id = ii.item_template_id
                AND (cei.reason IS NULL OR cei.reason = 'Excluded via cleanup')
          )
          AND NOT EXISTS (
              SELECT 1 FROM batch_unit bu
              JOIN exclusion_list_item eli
                   ON eli.exclusion_list_id = bu.exclusion_list_id
              WHERE bu.unit_id = insp.unit_id
                AND bu.cycle_id = insp.cycle_id
                AND bu.removed_at IS NULL
                AND eli.item_template_id = ii.item_template_id
          )
        GROUP BY u.unit_number, insp.cycle_number
        ORDER BY u.unit_number
        """
    )
    rows = cur.fetchall()
    offenders = [f"{un}(C{cy}):{n}" for un, cy, n in rows]
    return len(rows), offenders


def rule_R2_inactive_templates_in_use(cur):
    """Count DISTINCT inactive item_templates that are actually referenced by any
    inspection_item. Baseline 1 = the known inert ghost (1161cc67). >1 = drift:
    a new inactive template has leaked into live inspection data."""
    cur.execute(
        """
        SELECT DISTINCT it.id
        FROM item_template it
        WHERE it.active = 0
          AND EXISTS (SELECT 1 FROM inspection_item ii
                      WHERE ii.item_template_id = it.id)
        """
    )
    rows = cur.fetchall()
    offenders = [r[0] for r in rows]
    return len(rows), offenders


def rule_R3_linkcopy_gap(cur):
    """A NULL-link inspection is a violation ONLY if it has >=1 skipped item that
    is neither ground_only NOR in the live cycle-matched batch_unit list. (A bare
    NULL exclusion_list_id is NORMAL and is NOT flagged.) Counts distinct units."""
    cur.execute(
        """
        SELECT DISTINCT u.unit_number, insp.cycle_number
        FROM inspection_item ii
        JOIN inspection insp ON ii.inspection_id = insp.id
        JOIN unit u ON insp.unit_id = u.id
        JOIN item_template it ON ii.item_template_id = it.id
        WHERE ii.status = 'skipped'
          AND insp.exclusion_list_id IS NULL
          AND it.floor_condition != 'ground_only'
          AND NOT EXISTS (
              SELECT 1 FROM batch_unit bu
              JOIN exclusion_list_item eli
                   ON eli.exclusion_list_id = bu.exclusion_list_id
              WHERE bu.unit_id = insp.unit_id
                AND bu.cycle_id = insp.cycle_id
                AND bu.removed_at IS NULL
                AND eli.item_template_id = ii.item_template_id
          )
        ORDER BY u.unit_number
        """
    )
    rows = cur.fetchall()
    offenders = [f"{un}(C{cy})" for un, cy in rows]
    return len(rows), offenders


RULES = [
    ("R1", "CEI skip pollution residual", rule_R1_cei_pollution),
    ("R2", "Inactive templates in use", rule_R2_inactive_templates_in_use),
    ("R3", "Link-copy gap (non-list non-ground skips)", rule_R3_linkcopy_gap),
]
