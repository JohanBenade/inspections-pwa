#!/usr/bin/env python3
"""
check_invariants_live.py - read-only live DB invariant checks for the Inspections PWA.

Run ON RENDER (CI cannot reach /var/data). Read-only: SELECT/COUNT only, no writes.
Exits 0 if all rules PASS their baseline, 1 if any rule FAILs. Suitable as a
post-deploy gate run from the Render console.

The three rules encode signatures PROVEN against live data (handovers v425/v426 +
this thread). Each rule returns (count, offenders) and is compared to a fixed
BASELINE. Drift = count != baseline.

Source of truth = this script against the live DB, NOT any handover prose.

Tables/columns used were confirmed by PRAGMA this session. batch_unit subqueries
filter removed_at IS NULL to read only the live row (avoids the cycle_id fan-out
trap: a unit may hold multiple batch_unit rows per cycle if one was removed).
"""
import sqlite3
import sys

DB_PATH = "/var/data/inspections.db"

# Known-good baselines. A rule PASSES iff its count == baseline.
# R1: residual CEI pollution after the v421/v426 repairs. Proven 0 this thread.
# R2: distinct inactive item_templates in use. Ghost 1161cc67 is the 1 known-inert.
# R3: NULL-link inspections with a non-ground_only, not-in-list skipped item.
#     Proven 0 this thread (every NOLIST skip was ground_only).
BASELINES = {"R1": 0, "R2": 1, "R3": 0}


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


def main():
    c = sqlite3.connect(DB_PATH)
    cur = c.cursor()
    any_fail = False
    print("=== INVARIANT CHECK (live, read-only) ===")
    for code, name, fn in RULES:
        count, offenders = fn(cur)
        base = BASELINES[code]
        ok = count == base
        if not ok:
            any_fail = True
        tag = "PASS" if ok else "FAIL"
        print(f"[{tag}] {code} {name}: count={count} baseline={base}")
        if offenders:
            shown = offenders if len(offenders) <= 20 else offenders[:20] + ["..."]
            print(f"        offenders: {shown}")
    c.close()
    print("=== RESULT:", "ALL PASS" if not any_fail else "FAILURES PRESENT", "===")
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
