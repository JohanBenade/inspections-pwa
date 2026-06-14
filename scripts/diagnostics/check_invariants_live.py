#!/usr/bin/env python3
"""
check_invariants_live.py - read-only live DB invariant checks for the Inspections PWA.

Run ON RENDER (CI cannot reach /var/data). Read-only: SELECT/COUNT only, no writes.
Exits 0 if all rules PASS their baseline, 1 if any rule FAILs. Suitable as a
post-deploy gate run from the Render console.

The three rule queries now live in scripts/diagnostics/invariant_rules.py so that
this live runner AND the CI gate (tests/test_invariants.py) share ONE definition.
This file owns the live DB path and the production baselines; it does not redefine
rule logic.

Source of truth = these rules against the live DB, NOT any handover prose.
"""
import os
import sqlite3
import sys

# Import the shared rule definitions. Works whether run from /app (Render) or repo
# root: add this file's own directory to the path so the sibling module resolves.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from invariant_rules import RULES

DB_PATH = "/var/data/inspections.db"

# Known-good baselines. A rule PASSES iff its count == baseline.
# R1: residual CEI pollution after the v421/v426 repairs. Proven 0.
# R2: distinct inactive item_templates in use. Ghost 1161cc67 is the 1 known-inert.
# R3: NULL-link inspections with a non-ground_only, not-in-list skipped item. Proven 0.
BASELINES = {"R1": 0, "R2": 1, "R3": 0}


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
