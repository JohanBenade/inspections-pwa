#!/usr/bin/env python3
"""AF-016: fix split definition of 'prior'. Carry-forward must find the
MOST RECENT prior inspection, not strictly cycle_number-1. Mirrors the
engine's top_inspection pattern (ORDER BY cycle_number DESC LIMIT 1).
One logical change. Assert-guarded."""
import sys

PATH = "app/routes/inspection.py"

OLD = '''        prev_inspection = query_db("""
            SELECT i.id FROM inspection i
            WHERE i.unit_id = ? AND i.cycle_number = ?
            AND i.tenant_id = ?
        """, [unit_id, cycle['cycle_number'] - 1, tenant_id], one=True)'''

NEW = '''        prev_inspection = query_db("""
            SELECT i.id FROM inspection i
            WHERE i.unit_id = ? AND i.cycle_number < ?
            AND i.tenant_id = ?
            ORDER BY i.cycle_number DESC LIMIT 1
        """, [unit_id, cycle['cycle_number'], tenant_id], one=True)'''

with open(PATH, "r") as f:
    content = f.read()

assert OLD in content, "MATCH FAILED - prev_inspection lookup not found verbatim"
assert content.count(OLD) == 1, "MATCH NOT UNIQUE - found %d times" % content.count(OLD)

content = content.replace(OLD, NEW)

with open(PATH, "w") as f:
    f.write(content)

assert NEW in content, "WRITE FAILED"
print("AF-016 PATCH APPLIED OK - 1 occurrence replaced")
