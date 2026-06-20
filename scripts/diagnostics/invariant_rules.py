#!/usr/bin/env python3
"""
invariant_rules.py - the invariant rule queries, extracted so BOTH the live
runner (check_invariants_live.py, against /var/data/inspections.db) and the CI gate
(tests/test_invariants.py, against committed fixtures) import the SAME definitions.

Each rule takes an open sqlite3 cursor and returns (count, offenders). Query bodies
are copied verbatim from the proven check_invariants_live.py - no logic change.

Production baselines live in the live runner. Fixture-expected counts live in the CI
test. This module holds ONLY the rule logic, so adding a rule later touches one file.
"""

# Production baselines (used by the live runner). The CI test asserts its own
# fixture-specific expected counts and does NOT use these.
LIVE_BASELINES = {"R1": 0, "R2": 1, "R3": 0, "R4": 0, "R5": 0}


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


def rule_R4_cycle_number_gap(cur):
    """AF-016 regression guard. A unit's inspection.cycle_number values must form a
    contiguous run (min..max with no hole). A gap is exactly the condition under
    which the old 'cycle_number - 1' carry-forward lookup diverges from the
    'most-recent prior' fix: the predecessor row is missing, every item silently
    carries as pending, and the item layer disagrees with the defect layer (which
    keys on raised_cycle_id identity). Zero gaps => the two definitions agree.
    Counts distinct units whose cycle_number sequence has at least one hole.
    NULL cycle_number is also a violation (cannot be ordered)."""
    cur.execute(
        """
        SELECT u.unit_number,
               COUNT(DISTINCT insp.cycle_number) AS distinct_cycles,
               MIN(insp.cycle_number) AS lo,
               MAX(insp.cycle_number) AS hi,
               SUM(CASE WHEN insp.cycle_number IS NULL THEN 1 ELSE 0 END) AS nulls
        FROM inspection insp
        JOIN unit u ON insp.unit_id = u.id
        GROUP BY insp.unit_id, u.unit_number
        HAVING nulls > 0
            OR distinct_cycles <> (hi - lo + 1)
        ORDER BY u.unit_number
        """
    )
    rows = cur.fetchall()
    offenders = []
    for un, dc, lo, hi, nulls in rows:
        if nulls and nulls > 0:
            offenders.append(f"{un}(NULL cycle_number)")
        else:
            offenders.append(f"{un}(cycles {lo}..{hi}, only {dc} present)")
    return len(rows), offenders


def rule_R5_clearance_atomicity(cur):
    """AF-018 / SR-019 strip-bug guard. A defect's clearance state is ONE fact
    spread across four columns that must move together:
      status='cleared'  => cleared_cycle_id, cleared_cycle_number, cleared_at
                           all NON-NULL (a real, attributable clearance).
      status='open'     => all three NULL (no stale clearance residue).
    A partial state (cleared with a NULL anchor, or open with a clearance field
    still set) is the exact fingerprint of an unguarded write path stripping or
    half-writing clearance fields - the SR-019 'C3 strip bug' class. Counts
    DISTINCT defect ids in either broken direction.

    Deliberately EXCLUDED from the rule:
      - clearance_note: legitimately NULL on many cleared defects (proven 253
        cleared rows with NULL note on live), so it is optional, not part of the
        atomic quartet.
      - addressed_cycle_number: a de-snag working marker that can validly be set
        on an OPEN defect (addressed-this-cycle) - NOT a clearance field.
    Only 'cleared' and 'open' are real defect.status values (proven live)."""
    cur.execute(
        """
        SELECT id, unit_id, status,
               cleared_cycle_id, cleared_cycle_number, cleared_at
        FROM defect
        WHERE (status = 'cleared'
               AND (cleared_cycle_id IS NULL
                    OR cleared_cycle_number IS NULL
                    OR cleared_at IS NULL))
           OR (status = 'open'
               AND (cleared_cycle_id IS NOT NULL
                    OR cleared_cycle_number IS NOT NULL
                    OR cleared_at IS NOT NULL))
        ORDER BY unit_id, id
        """
    )
    rows = cur.fetchall()
    offenders = []
    for did, uid, status, ccid, ccn, cat in rows:
        if status == 'cleared':
            offenders.append(f"{did}(u={uid}: cleared but anchor incomplete)")
        else:
            offenders.append(f"{did}(u={uid}: open but clearance fields set)")
    return len(rows), offenders


RULES = [
    ("R1", "CEI skip pollution residual", rule_R1_cei_pollution),
    ("R2", "Inactive templates in use", rule_R2_inactive_templates_in_use),
    ("R3", "Link-copy gap (non-list non-ground skips)", rule_R3_linkcopy_gap),
    ("R4", "Cycle-number sequence gap (AF-016 regression guard)", rule_R4_cycle_number_gap),
    ("R5", "Clearance atomicity (AF-018/SR-019 strip-bug guard)", rule_R5_clearance_atomicity),
]
