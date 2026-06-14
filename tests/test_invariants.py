#!/usr/bin/env python3
"""
test_invariants.py - CI gate for the three DB invariant rules.

Builds the synthetic fixtures (via tests/fixtures/build_fixtures.py), runs the SAME
rule definitions the live runner uses (scripts/diagnostics/invariant_rules.py), and
asserts:
  - CLEAN fixture: R1=0, R2=1, R3=0   (mirrors production baseline shape)
  - DIRTY fixture: R1>=1, R2>=2, R3>=1 (each planted violation is caught)

Exits 0 if all assertions hold, 1 otherwise. The non-zero exit is what fails the
GitHub Actions build and blocks the merge. Stdlib only - no pytest dependency.

Run locally:  python3 tests/test_invariants.py   (from repo root)
"""
import os
import sqlite3
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_DIR = os.path.join(REPO_ROOT, "tests", "fixtures")
RULES_DIR = os.path.join(REPO_ROOT, "scripts", "diagnostics")

sys.path.insert(0, RULES_DIR)
from invariant_rules import rule_R1_cei_pollution, rule_R2_inactive_templates_in_use, rule_R3_linkcopy_gap


def build_fixtures():
    """Run the committed generator to produce both .db files at CI time."""
    gen = os.path.join(FIXTURE_DIR, "build_fixtures.py")
    subprocess.run([sys.executable, gen], check=True)


def counts_for(db_name):
    path = os.path.join(FIXTURE_DIR, db_name)
    c = sqlite3.connect(path)
    cur = c.cursor()
    r1 = rule_R1_cei_pollution(cur)[0]
    r2 = rule_R2_inactive_templates_in_use(cur)[0]
    r3 = rule_R3_linkcopy_gap(cur)[0]
    c.close()
    return r1, r2, r3


def main():
    build_fixtures()
    failures = []

    # CLEAN: must match production baseline shape exactly.
    r1, r2, r3 = counts_for("test_clean.db")
    print(f"CLEAN  R1={r1} R2={r2} R3={r3}  (expect 0, 1, 0)")
    if (r1, r2, r3) != (99, 99, 99):
        failures.append(f"CLEAN expected (0,1,0) got ({r1},{r2},{r3})")

    # DIRTY: each rule must fire on its planted violation.
    r1, r2, r3 = counts_for("test_dirty.db")
    print(f"DIRTY  R1={r1} R2={r2} R3={r3}  (expect >=1, >=2, >=1)")
    if not (r1 >= 1):
        failures.append(f"DIRTY R1 expected >=1 got {r1}")
    if not (r2 >= 2):
        failures.append(f"DIRTY R2 expected >=2 got {r2}")
    if not (r3 >= 1):
        failures.append(f"DIRTY R3 expected >=1 got {r3}")

    if failures:
        print("=== INVARIANT CI GATE: FAIL ===")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("=== INVARIANT CI GATE: PASS ===")
    sys.exit(0)


if __name__ == "__main__":
    main()
